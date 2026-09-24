import uuid
from datetime import datetime

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    name: str
    created_at: datetime


class UserCreate(schemas.BaseUserCreate):
    name: str


class UserUpdate(schemas.BaseUserUpdate):
    name: str | None = None
