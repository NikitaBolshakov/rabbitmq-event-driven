import asyncio
from service import RabbitMQService, ConfigModel
import logging
import os

async def main():
    # Logging
    logging.basicConfig(level=logging.INFO)

    rabbitmq_url = os.getenv('RABBITMQ_URL')
    database_url = os.getenv('DATABASE_URL')
    tasks_folder = os.getenv('TASKS_PACKAGE')

    config = ConfigModel(rabbitmq_url, database_url, tasks_folder)
    service = RabbitMQService(config)
    await service.run()

if __name__ == "__main__":
    asyncio.run(main()) 