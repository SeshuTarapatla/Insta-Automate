from datetime import datetime
from typing import Literal

from my_modules.datetime_utils import now
from sqlmodel import Field, SQLModel

EntityType = Literal["profile", "post", "reel"]
EntityAccess = Literal["public", "private"]
EntityStatus = Literal["queued", "scanning", "failed", "completed"]


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