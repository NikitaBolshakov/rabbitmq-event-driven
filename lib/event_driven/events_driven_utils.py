from typing import Any, Annotated, Callable, Type
from functools import wraps
from pydantic import BaseModel, Field, ConfigDict
import re
import yaml
import asyncio
from aio_pika import Exchange, Channel
from events_initialization import (
    EventType, get_event_routing_key, MAX_RETRIES, get_event_queue_name,
    create_event, create_event_exchange, create_attempt_queues_event
)
from message.creation import (
    create_event_message, delete_event_message, notify_event_message, update_event_message
)
from pydantic import create_model
from utils import all_except_event_key_optional_overrides, event_key_optional_overrides
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
import os

class SendEventMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Read .env[SERVICE_NAME]
        service_name = os.getenv('SERVICE_NAME')
        result = await call_next(request)
        # Check if the result is base model and have __event_type__ field
        if isinstance(result, BaseModel) and hasattr(result, '__event_type__'):
            # Get event type from __event_type__ field
            event_type = result.__event_type__
            if event_type == EventType.CREATE:
                message = create_event_message(service_name, 0, result.model_dump())
            elif event_type == EventType.UPDATE:
                message = update_event_message(service_name, 0, result.model_dump())
            elif event_type == EventType.DELETE:
                message = delete_event_message(service_name, 0, result.model_dump())
                
            
        


class NotifyEvent(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str
    payload: dict

EVENT_EXCHANGE = 'event.exchange'

class EventKeyField:
    def __init__(self, field_type: Any):
        self.field_type = field_type
        
    def __get__(self, obj, objtype=None):
        return Field(..., json_schema_extra={'event_key': True})

def disable_on_update():
    def decorator(field: Any) -> Any:
        return Annotated[field, Field(json_schema_extra={'disable_update': True})]
    return decorator

def read_service_config(config_path: str):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def get_event_name_wrapper(override_name: str | None = None):
    def get_event_name(cls):
        # Return name in snake_case format
        name = override_name if override_name is not None else cls.__name__
        name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)
        return name.lower()

    return get_event_name

async def on_update(self, events_exchange: Exchange, config_path: str= "config.yaml"):       
    config = self.read_service_config(config_path)
        
    routing_key = get_event_routing_key(EventType.UPDATE, self.get_event_name())
    message_data = self.model_dump()
        
    # Add necessary headers for event_store
    message = update_event_message(config['service_name'], 0, message_data)
        
    await events_exchange.publish(
        message,
        routing_key=routing_key
    )

async def on_create(self, events_exchange: Exchange, config_path: str= "config.yaml"):
    config = self.read_service_config(config_path)
        
    routing_key = get_event_routing_key(EventType.CREATE, self.get_event_name())
    message = self.model_dump()
        
    # Add necessary headers for event_store
    message = create_event_message(config['service_name'], 0, message)
        
    await events_exchange.publish(
        message,
        routing_key=routing_key
    )

async def on_delete(self, events_exchange: Exchange, config_path: str= "config.yaml"):
    config = self.read_service_config(config_path)
        
    routing_key = get_event_routing_key(EventType.DELETE, self.get_event_name())
    message = self.model_dump()
        
    message = delete_event_message(config['service_name'], 0, message)
        
    await events_exchange.publish(
        message,
        routing_key=routing_key
    )

async def subscribe_to_events(cls, channel: Channel, events_exchange: Exchange, callback: Callable, event_type: EventType, config_path: str= "config.yaml"):
    config = cls.read_service_config(config_path)

    from common_model.message.processing import process_message

    async def process_message_wrapper(message):
        await process_message(events_exchange, message, callback, cls, config['service_name'], MAX_RETRIES)
    
    queue_name = get_event_queue_name(event_type, cls.get_event_name(), config['service_name'])
    queue = await channel.get_queue(queue_name)
    await queue.consume(process_message_wrapper)
    
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass

def on_notify(event_name: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, events_exchange: Exchange, *args, config_path: str= "config.yaml", **kwargs):
            result = await func(self, *args, **kwargs)
            
            config = self.read_service_config(config_path)
            
            routing_key = get_event_routing_key(EventType.NOTIFY, self.get_event_name())

            message = notify_event_message(config['service_name'], 0, event_name, result)
            
            await events_exchange.publish(
                message,
                routing_key=routing_key
            )
            
            return result
        return wrapper
    return decorator

async def sync_schema(cls, channel, event_types: set[EventType] | None = None, config_path: str= "config.yaml"):
    """Creates necessary exchanges and queues for specified event types
    
    Args:
        channel: RabbitMQ channel
        service_to: Service name to send events to
        event_types: Set of event types to create. If None - all types are created
    """
    service_to = cls.read_service_config(config_path)['service_name']

    # Create exchange
    await create_event_exchange(channel)
    
    # Define event types to create
    types_to_create = event_types if event_types is not None else set(EventType)

    # For each selected event type, create queues
    for event_type in types_to_create:
        await create_event(
            channel=channel,
            entity=cls.get_event_name(),
            service_to=service_to,
            event_type=event_type
        )

        await create_attempt_queues_event(channel, event_type, cls.get_event_name(), service_to, MAX_RETRIES)

def generate_crud_classes(base_class: type[BaseModel]):
    module = base_class.__module__

    all_except_event_key_optional_overrides_res= all_except_event_key_optional_overrides(base_class)
    event_key_optional_overrides_res = event_key_optional_overrides(base_class)

    CreateModel = create_model(
        f"{base_class.__name__}Create",
        __base__=base_class,
        **event_key_optional_overrides_res,
        __event_type__ = EventType.CREATE
    )

    UpdateModel = create_model(
        f"{base_class.__name__}Update",
        __base__=base_class,
        **all_except_event_key_optional_overrides_res,
        __event_type__ = EventType.UPDATE
    )

    DeleteModel = create_model(
        f"{base_class.__name__}Delete",
        __base__=base_class,
        **all_except_event_key_optional_overrides_res,
        __event_type__ = EventType.DELETE
    )

    ReadModel = create_model(
        f"{base_class.__name__}Read",
        __base__=base_class,
        __event_type__ = EventType.READ
    )


    # Register classes in global namespace
    import sys
    module_dict = sys.modules[module].__dict__
    module_dict[CreateModel.__name__] = event_object(base_class.__name__)(CreateModel)
    module_dict[UpdateModel.__name__] = event_object(base_class.__name__)(UpdateModel)
    module_dict[DeleteModel.__name__] = event_object(base_class.__name__)(DeleteModel)
    module_dict[ReadModel.__name__] = event_object(base_class.__name__)(ReadModel)
    
    return CreateModel, UpdateModel, DeleteModel, ReadModel

def event_object(override_name: str | None = None) -> Callable[[Type[BaseModel]], Type[BaseModel]]:
    def event_object_internals(cls: Type[BaseModel]) -> Type[BaseModel]:
        """Decorator for event objects that validates they have an event key field"""
        # Add key to check event type
        cls.__annotations__['__event_type__'] = EventType
        setattr(cls, '__event_type__', Field(..., exclude=True))
        # Add methods to the class
        setattr(cls, 'read_service_config', staticmethod(read_service_config))
        setattr(cls, 'get_event_name', classmethod(get_event_name_wrapper(override_name)))
        setattr(cls, 'on_update', on_update)
        setattr(cls, 'on_create', on_create)
        setattr(cls, 'on_delete', on_delete)
        setattr(cls, 'on_notify', staticmethod(on_notify))
        setattr(cls, 'subscribe_to_events', classmethod(subscribe_to_events))
        setattr(cls, 'sync_schema', classmethod(sync_schema))

        return cls
    return event_object_internals