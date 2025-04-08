# Event-Driven RabbitMQ Service

This project implements an event-driven microservice using RabbitMQ for message queuing, FastAPI for the web framework (in examples), and SQLAlchemy for database interactions. It includes a library (`lib/event_driven`) providing utilities for building event-driven systems.

## Project Structure

```
.
├── lib/                  # Reusable event-driven library
│   ├── event_driven/
│   │   ├── examples/     # Example usage of the library (e.g., FastAPI integration)
│   │   │   ├── fastapi_response_model_example.py
│   │   │   └── model.py
│   │   ├── message/      # Message creation and processing logic
│   │   │   ├── creation.py
│   │   │   └── processing.py
│   │   ├── events_driven_utils.py  # Core utilities for event handling, decorators, etc.
│   │   └── events_initialization.py # Functions for setting up RabbitMQ exchanges, queues, etc.
│   └── pyproject.toml    # Library packaging configuration
├── rabbitmq_service/     # The main RabbitMQ consumer service
│   ├── main.py           # Entry point for the service
│   ├── service.py        # Core RabbitMQService class handling message consumption and processing
│   ├── models.py         # SQLAlchemy database models (EventStore, TaskStore)
│   ├── tasks/            # Directory for task execution logic (dynamically imported)
│   ├── tests/            # Unit and integration tests
│   ├── Dockerfile        # Docker configuration for the service
│   ├── docker-compose.yaml # Docker Compose setup for running the service and dependencies (RabbitMQ, potentially DB)
│   ├── requirements.txt  # Python dependencies for the service
│   └── config.yaml       # Service configuration (e.g., service name)
└── README.md             # This file
```

## Core Components

### `lib/event_driven`

This library provides a set of tools and abstractions to facilitate building event-driven applications:

- **`events_initialization.py`**: Contains functions to declare RabbitMQ exchanges (event, task, dead-letter), queues (main, dead-letter, retry attempts), and define naming conventions for queues and routing keys. It handles setting up the necessary infrastructure for reliable messaging, including retry logic with exponential backoff.
- **`events_driven_utils.py`**: Offers higher-level utilities:
    - Decorators (`@event_object`, `@on_notify`) to simplify event publishing and schema definition.
    - Functions (`generate_crud_classes`) to automatically create Pydantic models for Create, Read, Update, Delete (CRUD) operations based on a base model.
    - Helper functions for publishing events (`on_create`, `on_update`, `on_delete`).
    - Subscription logic (`subscribe_to_events`).
    - Schema synchronization (`sync_schema`) to ensure RabbitMQ topology matches the code definitions.
- **`message/`**: Handles the creation (`creation.py`) and processing (`processing.py`) of standardized message formats, likely including headers for correlation IDs, producer information, and retry counts.

### `rabbitmq_service`

This service acts as a consumer for messages published via RabbitMQ.

- **`main.py`**: Initializes logging and configuration (reading environment variables for RabbitMQ URL, database URL, etc.) and starts the `RabbitMQService`.
- **`service.py`**:
    - The `RabbitMQService` class connects to RabbitMQ and the database (using SQLAlchemy async).
    - It sets up RabbitMQ exchanges and queues using functions from `lib/event_driven`.
    - It consumes messages from event and task queues.
    - **Event Processing**: Stores received events in the `EventStore` table using SQLAlchemy.
    - **Task Processing**:
        - Stores task details in the `TaskStore` table.
        - Dynamically imports and executes task logic based on the message content (from the `tasks/` directory).
        - Updates the task status (PENDING, COMPLETED, FAILED) and stores results or errors in the `TaskStore`.
- **`models.py`**: Defines SQLAlchemy models:
    - `EventStore`: Records incoming events with details like correlation ID, producer app, headers, and payload.
    - `TaskStore`: Tracks tasks to be processed, including status, payload, results, and errors.
- **`Dockerfile` & `docker-compose.yaml`**: Define how to build and run the service and its dependencies (like RabbitMQ and a database) in containers.

## Features

- **Event-Driven Architecture**: Decouples services using RabbitMQ message queues.
- **Reliable Messaging**: Implements dead-letter queues and retry mechanisms with exponential backoff for handling message processing failures.
- **Database Persistence**: Stores events and task states in a database using SQLAlchemy.
- **Dynamic Task Execution**: Loads and runs task logic dynamically based on incoming messages.
- **Configuration Management**: Uses environment variables and potentially a `config.yaml` file.
- **Containerization**: Ready to be deployed using Docker and Docker Compose.
- **Reusable Library**: Core event-driven logic is encapsulated in the `lib` directory for potential reuse in other services.

## Getting Started (Example based on `rabbitmq_service`)

1.  **Set up Environment Variables**:
    ```bash
    export RABBITMQ_URL='amqp://guest:guest@localhost:5672/' # Adjust if needed
    export DATABASE_URL='postgresql+asyncpg://user:password@host:port/database' # Adjust for your DB
    export TASKS_PACKAGE='tasks' # Or the relevant package name
    export SERVICE_NAME='my_rabbitmq_consumer' # Example service name
    ```
2.  **Install Dependencies**:
    ```bash
    cd rabbitmq_service
    pip install -r requirements.txt
    cd ../lib
    pip install . # Install the event_driven library
    cd ..
    ```
3.  **Run Database Migrations (if applicable)**: The `init_db` function in `service.py` uses `Base.metadata.create_all`. Ensure your database exists.
4.  **Using Docker Compose**:
    ```bash
    # Ensure Docker and Docker Compose are installed
    docker-compose up -d --build
    ```

## Example Usage (`lib/event_driven/examples`)

The `fastapi_response_model_example.py` demonstrates how the `event_driven` library's concepts (like generated Pydantic models) might be used within a FastAPI application, potentially for publishing events after API operations. The `test_crud.sh` script provides example `curl` commands for interacting with this example API.

## Directories

*   `rabbitmq_service/`: Contains the main service logic related to RabbitMQ.
*   `lib/`: Contains shared libraries or utilities used by the project.

## Getting Started

(Add instructions on how to set up and run the project)

## Usage

This section describes how external services can interact with the `rabbitmq_service` and utilize the `lib/event_driven` library.

### `rabbitmq_service` Interaction

The `rabbitmq_service` acts as a central processor for events and tasks via RabbitMQ.

**1. Publishing Events:**

*   **Exchange:** Publish messages to the `event.exchange` (Topic Exchange).
*   **Routing Key:** Use a routing key following the pattern `routing.event.<event_type>.<entity>` (e.g., `routing.event.create.user`). The `lib/event_driven` library provides helpers like `get_event_routing_key`.
*   **Message Properties:** Ensure messages have `app_id` (your service name) and `correlation_id` properties set.
*   **Outcome:** The `rabbitmq_service` consumes all events via the `event.store` queue (bound with `#`) and persists them in the `EventStore` database table.

**2. Triggering Tasks:**

*   **Exchange:** Publish messages to the `task.exchange` (Direct Exchange).
*   **Routing Key:** Use a routing key following the pattern `routing.task.<action>.<entity>` (e.g., `routing.task.process.order`). The `lib/event_driven` library provides helpers like `get_task_routing_key`.
*   **Headers:** Include `producer_app` (your service name) and `correlation_id` in the message headers. The `lib/event_driven.ModelHeaders` Pydantic model can be used for validation.
*   **Payload:** The message body must be a dictionary: `{'task_name': 'name_of_task_module', 'payload': {...}}`.
*   **Outcome:** The `rabbitmq_service` consumes matching tasks via the `tasks` queue, stores them in the `TaskStore` table, dynamically executes the `execute` function within the specified `task_name` module located in its configured tasks directory (e.g., `tasks_folder.name_of_task_module.execute(payload)`), and updates the task status (PENDING, COMPLETED, FAILED) in the database.

### `lib/event_driven` Library Usage

This library provides utilities to facilitate consistent interaction with the RabbitMQ setup.

*   **Purpose:** Helps external services declare necessary queues/exchanges and format messages correctly.
*   **Features:**
    *   Constants for standard exchange names (e.g., `EVENT_EXCHANGE`, `TASK_EXCHANGE`).
    *   Functions to generate standardized queue names and routing keys (e.g., `get_event_queue_name`, `get_task_routing_key`).
    *   Async functions to declare RabbitMQ topology (`create_event`, `create_task`, `create_event_store`, etc.), including dead-lettering and retry logic setup.
    *   `ModelHeaders` Pydantic model for validating required headers.
*   **Recommendation:** Use this library when publishing events or tasks to ensure compatibility with the `rabbitmq_service` conventions.

## Contributing

(Add instructions on how to contribute to the project)