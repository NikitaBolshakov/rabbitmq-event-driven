import json
from aio_pika import IncomingMessage, Exchange, Message
from pydantic import BaseModel, ValidationError
from typing import Type, Callable
from event_driven.exceptions import BusinessException, TechnicalException, ModelException
from event_driven.events_initialization import routing_key_to_attempt_n_routing_key
import logging

async def process_message(exchange: Exchange, message: IncomingMessage, handler: Callable, model_cls: Type[BaseModel], service_name: str, max_attempts: int = 3):
    # Validate message model
    try:
        # Decode message body from bytes to dict
        message_dict = json.loads(message.body.decode())
        model = model_cls.model_validate(message_dict)
    except ValidationError as e:
        await message.ack()
        raise ModelException(f"Invalid message model: {e}")

    # Process message
    try:
        await handler(model)
        await message.ack()
    except ModelException as e:
        await message.ack()
    except BusinessException as e:
        await message.ack()
        logging.info(f"Business exception on message {message.correlation_id}: {e}")
    except TechnicalException as e:
        current_attempt = int(message.headers['x-attempt'])
        logging.info(f"Technical exception on message {message.correlation_id} (attempt {current_attempt}): {e}")

        if current_attempt >= max_attempts:
            logging.warning(f"Max attempts ({max_attempts}) reached for message {message.correlation_id}")
            await message.nack(requeue=False)
            return

        headers = dict(message.headers)
        headers['x-attempt'] = current_attempt + 1
        
        new_message = Message(
            body=message.body,
            headers=headers, 
            content_type=message.content_type,
            content_encoding=message.content_encoding,
            delivery_mode=message.delivery_mode,
            priority=message.priority,
            correlation_id=message.correlation_id,
            reply_to=message.reply_to,
            expiration=message.expiration,
            message_id=message.message_id,
            timestamp=message.timestamp,
            type=message.type,
            user_id=message.user_id,
            app_id=message.app_id
        )

        routing_key = routing_key_to_attempt_n_routing_key(message.routing_key, current_attempt, service_name)
        # Publish message to waiting queue. It will be retried after delay
        await exchange.publish(new_message, routing_key=routing_key)
        await message.ack()

    except Exception as e:
        logging.error(f"Unexpected error processing message {message.correlation_id}: {e}")
        await message.ack()