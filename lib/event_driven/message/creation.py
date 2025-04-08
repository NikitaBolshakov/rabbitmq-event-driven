from aio_pika import Message
import json
import uuid

def base_message(body: dict, producer_app: str, attempt: int, additional_headers: dict|None = None, correlation_id: str|None = None) -> Message:
    headers = {
        "x-attempt": attempt
    }
    if additional_headers:
        headers.update(additional_headers)

    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    return Message(body=json.dumps(body).encode(), app_id=producer_app, correlation_id=correlation_id, headers=headers)

def task_message(producer_app: str, attempt: int, task_name: str, arguments: dict, additional_headers: dict|None = None, correlation_id: str|None = None) -> Message:
    body = {
        "task_name": task_name,
        "arguments": arguments
    }
    return base_message(body, producer_app, attempt, additional_headers, correlation_id)

def event_message(producer_app: str, attempt: int, payload: dict, additional_headers: dict|None = None, correlation_id: str|None = None) -> Message:
    return base_message(payload, producer_app, attempt, additional_headers, correlation_id)

def notify_event_message(producer_app: str, attempt: int, event_name: str, payload: dict, additional_headers: dict|None = None, correlation_id: str|None = None) -> Message:
    payload["event_name"] = event_name
    return event_message(producer_app, attempt, payload, additional_headers, correlation_id)

def create_event_message(producer_app: str, attempt: int, payload: dict, additional_headers: dict|None = None, correlation_id: str|None = None) -> Message:
    return event_message(producer_app, attempt, payload, additional_headers, correlation_id)

def delete_event_message(producer_app: str, attempt: int, payload: dict, additional_headers: dict|None = None, correlation_id: str|None = None) -> Message:
    return event_message(producer_app, attempt, payload, additional_headers, correlation_id)

def update_event_message(producer_app: str, attempt: int, payload: dict, additional_headers: dict|None = None, correlation_id: str|None = None) -> Message:
    return event_message(producer_app, attempt, payload, additional_headers, correlation_id)



