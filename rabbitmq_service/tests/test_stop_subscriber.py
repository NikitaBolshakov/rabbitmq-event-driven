import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from aio_pika import connect_robust
from common_model.model.stop import Stop
from common_model.events_initialization import (
    create_event_exchange,
    EventType
)

def stop_callback_wrapper(event_type: EventType):
    async def stop_callback(stop_data: dict):
        """Callback function that will be called when a stop event is received"""
        print(f"Received stop event ({event_type}) with data: {stop_data}")

    return stop_callback
    
async def main():
    # Connect to RabbitMQ
    connection = await connect_robust(
        "amqp://guest:guest@localhost/",
    )
    
    async with connection:
        # Creating channel
        channel = await connection.channel()
        
        # Create exchange
        events_exchange = await create_event_exchange(channel)

        await Stop.sync_schema(channel, set([EventType.CREATE, EventType.UPDATE, EventType.DELETE]), config_path="config_receiver.yaml")
        
        print("Waiting for stop creation events...")
        
        # Subscribe to creation events
        t1 = asyncio.create_task(
            Stop.subscribe_to_events(
                channel,
                events_exchange=events_exchange,
                callback=stop_callback_wrapper(EventType.CREATE),
                event_type=EventType.CREATE,
                config_path="config_receiver.yaml"
            )
        )

        t2 = asyncio.create_task(
            Stop.subscribe_to_events(
                channel,
                events_exchange=events_exchange,
                callback=stop_callback_wrapper(EventType.UPDATE),
                event_type=EventType.UPDATE,
                config_path="config_receiver.yaml"
            )
        )

        t3 = asyncio.create_task(
            Stop.subscribe_to_events(
                channel,
                events_exchange=events_exchange,
                callback=stop_callback_wrapper(EventType.DELETE),
                event_type=EventType.DELETE,
                config_path="config_receiver.yaml"
            )
        )

        await asyncio.gather(t1, t2, t3)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSubscriber stopped") 