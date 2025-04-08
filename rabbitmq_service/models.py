from datetime import datetime, timezone
import uuid
import enum
from sqlalchemy import Column, String, DateTime, JSON, UUID, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Statuses enum
class Status(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class EventStore(Base):
    __tablename__ = 'event_store'

    id_event_store = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String, nullable=False)
    producer_app = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    headers = Column(JSON, nullable=False)
    payload = Column(JSON, nullable=False)

class TaskStore(Base):
    __tablename__ = 'task_store'

    id_task = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String, nullable=False)
    producer_app = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    task_name = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(SQLEnum(Status), nullable=False)
    result = Column(JSON, nullable=True)
    error = Column(String, nullable=True) 