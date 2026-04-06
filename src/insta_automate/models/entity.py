from datetime import datetime
from enum import StrEnum, auto

from my_modules.datetime_utils import now
from sqlmodel import Field, SQLModel


class EntityType(StrEnum):
    POST = auto()
    PROFILE = auto()
    REEL = auto()


class EntityAccess(StrEnum):
    PUBLIC = auto()
    PRIVATE = auto()


class EntityStatus(StrEnum):
    QUEUED = auto()
    SCANNING = auto()
    FAILED = auto()
    COMPLETED = auto()


class Entity(SQLModel, table=True):
    url: str = Field(primary_key=True)
    id: str
    type: EntityType
    access: EntityAccess
    added_on: datetime = Field(default_factory=now)
    updated_on: datetime = Field(
        default_factory=now, sa_column_kwargs={"onupdate": now}
    )
    scanned: int = Field(ge=0)
    scraped: int = Field(ge=0)
    status: EntityStatus
