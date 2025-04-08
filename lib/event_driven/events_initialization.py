from enum import Enum
from aio_pika import ExchangeType
from pydantic import BaseModel, ConfigDict

EVENT_EXCHANGE = 'event.exchange'
DEAD_EVENT_EXCHANGE = 'dead.event.exchange'
TASK_EXCHANGE = 'task.exchange'
DEAD_TASK_EXCHANGE = 'dead.task.exchange'
RETRY_SUFFIX = '.retry'
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 3000  # 3 seconds in milliseconds

# Max time of message in main queue (24 hours in milliseconds)
QUEUE_MESSAGE_TTL = 24 * 60 * 60 * 1000

# Max size of queue (100MB)
MAX_QUEUE_SIZE = 100 * 1024 * 1024

# Max number of messages in queue
MAX_QUEUE_LENGTH = 10000

class EventType(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    READ = "read"
    NOTIFY = "notify"

# Headers model
class ModelHeaders(BaseModel):
    model_config = ConfigDict(strict=True)
    
    producer_app: str
    correlation_id: str




def get_event_queue_name(event_type: EventType, entity: str, service_to: str):
    return f"event.{event_type.value}.{entity}.to.{service_to}"

def get_event_dead_queue_name(event_type: EventType, entity: str, service_to: str):
    return f"dead.{get_event_queue_name(event_type, entity, service_to)}"

def get_event_routing_key(event_type: EventType, entity: str):
    return f"routing.event.{event_type.value}.{entity}.#"

def get_dead_event_routing_key(event_type: EventType, entity: str, service_to: str):
    return f"dead.routing.{event_type.value}.{entity}.to.{service_to}"

def get_task_queue_name(action: str, entity: str):
    return f"task.{action}.{entity}"

def get_task_routing_key(action: str, entity: str):
    return f"routing.task.{action}.{entity}"

def get_task_dead_queue_name(action: str, entity: str):
    return f"dead.{get_task_queue_name(action, entity)}"

def get_task_dead_routing_key(action: str, entity: str):
    return f"dead.routing.{action}.{entity}"

def get_event_store_queue_name():
    return "event.store"

def get_event_store_dead_queue_name():
    return f"dead.{get_event_store_queue_name()}"

def get_event_store_routing_key():
    return "#.event.#"

def get_attempt_n_queue_name_event(n: int, event_type: EventType, entity: str, service_to: str):
    return f"attempt.{n}.{event_type.value}.{entity}.to.{service_to}"

def get_attempt_n_queue_name_task(n: int, action: str, entity: str):
    return f"attempt.{n}.{action}.{entity}"

def routing_key_to_attempt_n_routing_key(routing_key: str, n: int, service_name: str):
    return routing_key.replace("routing.event.", f"routing.attempt.{n}.").replace("routing.task.", f"routing.attempt.{n}.").replace("#", f"to.{service_name}")

def get_attempt_n_routing_key_event(n: int, event_type: EventType, entity: str, service_to: str):
    return f"routing.attempt.{n}.{event_type.value}.{entity}.to.{service_to}"

def get_attempt_n_routing_key_task(n: int, action: str, entity: str):
    return f"routing.attempt.{n}.{action}.{entity}"

async def create_event_exchange(channel):
    exchange = await channel.declare_exchange(EVENT_EXCHANGE, ExchangeType.TOPIC)
    await channel.declare_exchange(DEAD_EVENT_EXCHANGE, ExchangeType.TOPIC)
    return exchange

async def create_task_exchange(channel):
    exchange = await channel.declare_exchange(TASK_EXCHANGE, ExchangeType.DIRECT)
    await channel.declare_exchange(DEAD_TASK_EXCHANGE, ExchangeType.DIRECT)
    return exchange

async def create_event(channel, entity: str, service_to: str, event_type: EventType):
    queue_name = get_event_queue_name(event_type, entity, service_to)
    routing_key = get_event_routing_key(event_type, entity)

    dead_queue_name = get_event_dead_queue_name(event_type, entity, service_to)
    dead_routing_key = get_dead_event_routing_key(event_type, entity, service_to)

    event_exchange = await channel.get_exchange(EVENT_EXCHANGE)
    dead_event_exchange = await channel.get_exchange(DEAD_EVENT_EXCHANGE)

    dead_queue = await channel.declare_queue(
        dead_queue_name,
        durable=True
    )

    queue = await channel.declare_queue(
        queue_name,
        durable=True,
        arguments={
            'x-dead-letter-exchange': DEAD_EVENT_EXCHANGE,
            'x-dead-letter-routing-key': dead_routing_key,
            'x-max-retries': MAX_RETRIES,
            'x-message-ttl': QUEUE_MESSAGE_TTL,
            'x-max-length': MAX_QUEUE_LENGTH,
            'x-max-length-bytes': MAX_QUEUE_SIZE,
            'x-overflow': 'reject-publish'
        }
    )

    await queue.bind(event_exchange, routing_key)
    await dead_queue.bind(dead_event_exchange, dead_routing_key)

async def create_attempt_queues_event(channel, event_type: EventType, entity: str, service_to: str, attempts: int):
    event_exchange = await channel.get_exchange(EVENT_EXCHANGE)

    event_routing_key = get_event_routing_key(event_type, entity)

    for n in range(attempts):
        queue_name = get_attempt_n_queue_name_event(n, event_type, entity, service_to)
        routing_key = get_attempt_n_routing_key_event(n, event_type, entity, service_to)

        queue = await channel.declare_queue(queue_name, durable=True, arguments={
            'x-message-ttl': INITIAL_RETRY_DELAY * (2 ** n),
            'x-dead-letter-exchange': EVENT_EXCHANGE,
            'x-dead-letter-routing-key': event_routing_key
        })
        await queue.bind(event_exchange, routing_key)

async def create_attempt_queues_task(channel, action: str, entity: str, attempts: int):
    task_exchange = await channel.get_exchange(TASK_EXCHANGE)

    task_routing_key = get_task_routing_key(action, entity)

    for n in range(attempts):
        queue_name = get_attempt_n_queue_name_task(n, action, entity)
        routing_key = get_attempt_n_routing_key_task(n, action, entity)

        queue = await channel.declare_queue(queue_name, durable=True, arguments={
            'x-message-ttl': INITIAL_RETRY_DELAY * (2 ** n),
            'x-dead-letter-exchange': TASK_EXCHANGE,
            'x-dead-letter-routing-key': task_routing_key
        })
        await queue.bind(task_exchange, routing_key)

async def create_task(channel, action: str, entity: str):
    queue_name = get_task_queue_name(action, entity)
    routing_key = get_task_routing_key(action, entity)

    dead_queue_name = get_task_dead_queue_name(action, entity)
    dead_routing_key = get_task_dead_routing_key(action, entity)

    task_exchange = await channel.get_exchange(TASK_EXCHANGE)
    dead_task_exchange = await channel.get_exchange(DEAD_TASK_EXCHANGE)

    dead_queue = await channel.declare_queue(
        dead_queue_name,
        durable=True
    )

    queue = await channel.declare_queue(
        queue_name,
        durable=True,
        arguments={
            'x-dead-letter-exchange': DEAD_TASK_EXCHANGE,
            'x-dead-letter-routing-key': dead_routing_key,
            'x-message-ttl': QUEUE_MESSAGE_TTL,
            'x-max-length': MAX_QUEUE_LENGTH,
            'x-max-length-bytes': MAX_QUEUE_SIZE,
            'x-overflow': 'reject-publish'
        }
    )

    await queue.bind(task_exchange, routing_key)
    await dead_queue.bind(dead_task_exchange, dead_routing_key)

async def create_event_store(channel):
    queue_name = get_event_store_queue_name()
    dead_queue_name = get_event_store_dead_queue_name()
    routing_key = get_event_store_routing_key()

    event_exchange = await channel.get_exchange(EVENT_EXCHANGE)
    dead_event_exchange = await channel.get_exchange(DEAD_EVENT_EXCHANGE)

    queue = await channel.declare_queue(
        queue_name,
        durable=True,
        arguments={
            'x-message-ttl': QUEUE_MESSAGE_TTL,
            'x-max-length': MAX_QUEUE_LENGTH,
            'x-max-length-bytes': MAX_QUEUE_SIZE,
            'x-overflow': 'reject-publish'
        }
    )

    dead_queue = await channel.declare_queue(
        dead_queue_name,
        durable=True
    )

    await queue.bind(event_exchange, routing_key)
    await dead_queue.bind(dead_event_exchange, routing_key)

