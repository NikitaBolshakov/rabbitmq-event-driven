from pydantic import BaseModel, EmailStr, Field
from event_driven.events_driven_utils import generate_crud_classes

class User(BaseModel):
    user_id: int = Field(json_schema_extra={'event_key': True})
    username: str
    email: EmailStr
    full_name: str | None = None

UserCreate, UserRead, UserUpdate, UserDelete = generate_crud_classes(User)