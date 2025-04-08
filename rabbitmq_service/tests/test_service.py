import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from aio_pika import IncomingMessage, Message
from sqlalchemy.ext.asyncio import AsyncSession
import json

from ..service import RabbitMQService, ConfigModel
from ..models import EventStore, TaskStore, Status

@pytest.fixture
def config():
    return ConfigModel(
        rabbitmq_url="amqp://guest:guest@localhost/",
        database_url="postgresql+asyncpg://user:password@localhost/testdb"
    )

@pytest.fixture
async def service(config):
    service = RabbitMQService(config)
    # Создаем базу данных для тестов
    async with service.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return service

@pytest.mark.asyncio
async def test_store_event(service):
    async with service.async_session() as session:
        # Тестовые данные
        producer_app = "test_app"
        correlation_id = "test_correlation_id"
        headers = {"test_header": "value"}
        payload = {"test_data": "value"}

        # Сохраняем событие
        event = await service.store_event(
            session=session,
            producer_app=producer_app,
            correlation_id=correlation_id,
            headers=headers,
            payload=payload
        )

        # Проверяем, что событие сохранено корректно
        assert event.producer_app == producer_app
        assert event.correlation_id == correlation_id
        assert event.headers == headers
        assert event.payload == payload

@pytest.mark.asyncio
async def test_store_task(service):
    async with service.async_session() as session:
        # Тестовые данные
        producer_app = "test_app"
        correlation_id = "test_correlation_id"
        task_name = "test_task"
        payload = {"test_data": "value"}

        # Сохраняем задачу
        task = await service.store_task(
            session=session,
            producer_app=producer_app,
            correlation_id=correlation_id,
            task_name=task_name,
            payload=payload
        )

        # Проверяем, что задача сохранена корректно
        assert task.producer_app == producer_app
        assert task.correlation_id == correlation_id
        assert task.task_name == task_name
        assert task.payload == payload
        assert task.status == Status.PENDING

@pytest.mark.asyncio
async def test_update_task_status(service):
    async with service.async_session() as session:
        # Создаем тестовую задачу
        task = await service.store_task(
            session=session,
            producer_app="test_app",
            correlation_id="test_correlation_id",
            task_name="test_task",
            payload={"test": "data"}
        )

        # Обновляем статус задачи
        result = {"result": "success"}
        updated_task = await service.update_task_status(
            session=session,
            task_id=task.id_task,
            status=Status.COMPLETED,
            result=result
        )

        # Проверяем обновление
        assert updated_task.status == Status.COMPLETED
        assert updated_task.result == result
        assert updated_task.error is None

@pytest.mark.asyncio
async def test_process_event(service):
    # Создаем мок для IncomingMessage
    headers = {
        "producer_app": "test_app",
        "correlation_id": "test_correlation_id"
    }
    payload = {"test": "data"}
    
    message = Mock(spec=IncomingMessage)
    message.headers = headers
    message.body = str(payload).encode()
    message.correlation_id = "test_correlation_id"

    # Тестируем обработку события
    async with service.async_session() as session:
        await service._process_event(message)

        # Проверяем, что событие сохранено в БД
        stmt = select(EventStore).where(
            EventStore.correlation_id == "test_correlation_id"
        )
        result = await session.execute(stmt)
        event = result.scalar_one()
        
        assert event.producer_app == "test_app"
        assert event.payload == payload

@pytest.mark.asyncio
async def test_process_task(service):
    # Создаем мок для IncomingMessage
    headers = {
        "producer_app": "test_app",
        "correlation_id": "test_correlation_id"
    }
    payload = {
        "task_name": "test_task",
        "payload": {"test": "data"}
    }
    
    message = Mock(spec=IncomingMessage)
    message.headers = headers
    message.body = str(payload).encode()
    
    # Мокаем выполнение задачи
    with patch('common_model.tasks.test_task.execute', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = {"result": "success"}
        
        # Тестируем обработку задачи
        async with service.async_session() as session:
            await service._process_task(message)

            # Проверяем, что задача сохранена в БД
            stmt = select(TaskStore).where(
                TaskStore.correlation_id == "test_correlation_id"
            )
            result = await session.execute(stmt)
            task = result.scalar_one()
            
            assert task.producer_app == "test_app"
            assert task.task_name == "test_task"
            assert task.status == Status.COMPLETED
            assert task.result == {"result": "success"} 