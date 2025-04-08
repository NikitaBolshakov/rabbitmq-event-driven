import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from common_model.events_initialization import create_event_exchange
from aio_pika import connect_robust
from pathlib import Path
import sys
import uvicorn

project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)
from service import RabbitMQService, ConfigModel

# Create FastAPI
app = FastAPI()

# Initialize configuration and service
config = ConfigModel(
    rabbitmq_url="amqp://guest:guest@localhost/",
    database_url="postgresql+asyncpg://user:password@localhost/testdb"
)
rabbit_service = RabbitMQService(config)

@app.post("/api/stops/", status_code=201)
async def create_stop(name: str, latitude: float, longitude: float):
    """Эндпоинт для создания остановки"""
    try:

        stop = Stop(
            id=1,
            name="Test Stop",
            latitude=55.7558,
            longitude=37.6173,
            address="Test Address, 123"
        )

        await stop.on_create(app.state.events_exchange)

        return stop
    except Exception as e:
        return {"error": str(e)}, 500

@app.on_event("startup")
async def startup_event():
    # Event exchange
    connection = await connect_robust(
        "amqp://guest:guest@localhost/",
    )

    channel = await connection.channel()
    events_exchange = await create_event_exchange(channel)

    app.state.events_exchange = events_exchange

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)