import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from aio_pika import connect_robust
from common_model.model.stop import Stop
from common_model.events_initialization import create_event_exchange, EventType

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
        
        # Create a test stop
        test_stop = Stop(
            id=1,
            name="Test Stop",
            latitude=55.7558,
            longitude=37.6173,
            address="Test Address, 123"
        )

        print(f"Creating stop: {test_stop}")
        
        # Send creation event
        await test_stop.on_create(events_exchange)
        print("Stop creation event sent successfully")
        await test_stop.on_update(events_exchange)
        print("Stop update event sent successfully")
        await test_stop.on_delete(events_exchange)
        print("Stop delete event sent successfully")

if __name__ == "__main__":
    asyncio.run(main()) 