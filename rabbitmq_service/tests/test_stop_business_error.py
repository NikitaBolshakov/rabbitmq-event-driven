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
from common_model.exceptions import BusinessException

async def stop_callback_with_error(stop_data: dict):
    """Callback function that will raise BusinessException"""
    print(f"Received stop event with data: {stop_data}")
    raise BusinessException("Test business error - stop cannot be processed")

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
        
        print("Waiting for stop creation events (will raise BusinessException)...")
        
        # Subscribe to creation events
        await Stop.subscribe_to_events(
            channel,
            events_exchange=events_exchange,
            callback=stop_callback_with_error,
            event_type=EventType.CREATE,
            config_path="config_receiver.yaml"
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSubscriber stopped") 