import asyncio
import logging
from typing import Any, Dict
from aio_pika import connect_robust, IncomingMessage
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from event_driven.events_initialization import (
    create_event_exchange, create_task_exchange,
    EVENT_EXCHANGE, TASK_EXCHANGE, get_event_store_queue_name
)
from pydantic import BaseModel
from models import Base, EventStore, TaskStore, Status


class ConfigModel(BaseModel):
    rabbitmq_url: str
    database_url: str
    tasks_folder: str

    def __init__(self, rabbitmq_url: str, database_url: str, tasks_folder: str):
        self.rabbitmq_url = rabbitmq_url
        self.database_url = database_url
        self.tasks_folder = tasks_folder



class RabbitMQService:
    def __init__(self, config: ConfigModel):
        self.config = config
        
        self.engine = create_async_engine(
            self.config.database_url,
            echo=True
        )
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def store_event(self, session: AsyncSession, producer_app: str, correlation_id: str, 
                         headers: Dict[str, Any], payload: Dict[str, Any]):
        event = EventStore(
            correlation_id=correlation_id,
            producer_app=producer_app,
            headers=headers,
            payload=payload
        )
        session.add(event)
        await session.commit()
        return event

    async def store_task(self, session: AsyncSession, producer_app: str, correlation_id: str,
                        task_name: str, payload: Dict[str, Any]):
        task = TaskStore(
            correlation_id=correlation_id,
            producer_app=producer_app,
            task_name=task_name,
            payload=payload,
            status=Status.PENDING
        )
        session.add(task)
        await session.commit()
        return task

    async def update_task_status(self, session: AsyncSession, task_id: str, 
                               status: Status, result: Dict[str, Any] | None = None, error: str | None = None):
        task = await session.get(TaskStore, task_id)
        if task:
            task.status = status
            task.result = result
            task.error = error
            await session.commit()
        return task

    async def setup_rabbitmq(self):
        connection = await connect_robust(self.config.rabbitmq_url)
        channel = await connection.channel()
        
        await create_event_exchange(channel)
        await create_task_exchange(channel)
        
        queue_name = get_event_store_queue_name()
        queue = await channel.declare_queue(queue_name, durable=True)
        await queue.bind(EVENT_EXCHANGE, "#") 
        
        async def process_event(message: AbstractIncomingMessage):
            try:
                async with self.async_session() as session:
                    if not message.app_id or not message.correlation_id:
                        raise ValueError("Message app_id or correlation_id is missing")
                    payload = eval(message.body.decode())
                await self.store_event(
                    session=session,
                    producer_app=message.app_id,
                    correlation_id=message.correlation_id,
                    headers=message.headers,
                    payload=payload
                )
                await message.ack()
            except Exception as e:
                logging.warning(f"Error processing event {message.correlation_id}")
                await message.reject(requeue=False)
        
        await queue.consume(process_event)
        
        task_queue = await channel.declare_queue("tasks", durable=True)
        await task_queue.bind(TASK_EXCHANGE, "#.task.#")
        
        async def process_task(message):
            async with message.process():
                async with self.async_session() as session:
                    data = eval(message.body.decode())
                    task = await self.store_task(
                        session=session,
                        producer_app=message.headers['producer_app'],
                        correlation_id=message.headers['correlation_id'],
                        task_name=data['task_name'],
                        payload=data['payload']
                    )
                    
                    try:
                        # TODO: import only once
                        module_path = f"{self.config.tasks_folder}.{data['task_name']}"
                        module = __import__(module_path, fromlist=['execute'])
                        result = await module.execute(data['payload'])
                        
                        await self.update_task_status(
                            session=session,
                            task_id=task.id_task,
                            status=Status.COMPLETED,
                            result=result
                        )
                    except Exception as e:
                        logging.exception(f"Error processing task {task.id_task}")
                        await self.update_task_status(
                            session=session,
                            task_id=task.id_task,
                            status=Status.FAILED,
                            error=str(e)
                        )
        
        await task_queue.consume(process_task)
        
        try:
            await asyncio.Future()  # run forever
        finally:
            await connection.close()

    async def run(self):
        await self.init_db()
        await self.setup_rabbitmq() 