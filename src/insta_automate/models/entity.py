from datetime import datetime
from enum import StrEnum, auto
from typing import Self
from urllib.parse import urlparse, urlunparse

from my_modules.datetime_utils import now
from pydantic import field_validator, model_validator
from sqlmodel import Field, Session, SQLModel, select

from insta_automate.exceptions import InvalidIAEntityUrl


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
    id: str = Field(default=None)
    type: EntityType = Field(default=None)
    access: EntityAccess = Field(default=EntityAccess.PRIVATE)
    added_on: datetime = Field(default_factory=now)
    updated_on: datetime = Field(
        default_factory=now, sa_column_kwargs={"onupdate": now}
    )
    scanned: int = Field(default=0, ge=0)
    scraped: int = Field(default=0, ge=0)
    status: EntityStatus = EntityStatus.QUEUED

    @field_validator("url")
    @classmethod
    def valid_entity_url(cls, value: str) -> str:
        try:
            value = value.replace("/profilecard", "")
            url = urlparse(value)
            if url.netloc != "www.instagram.com":
                raise InvalidIAEntityUrl
            return urlunparse(url._replace(query="")).removesuffix("/")
        except Exception:
            raise InvalidIAEntityUrl(f"{value} is not a valid Instagram Entity URL.")

    @model_validator(mode="before")
    def derive(self) -> Self:
        url = urlparse(self.url)
        if url.path.startswith("/p/"):
            self.type = EntityType.POST
            self.id = f"post-{url.path.removeprefix('/p/')}"
        elif url.path.startswith("/reel/"):
            self.type = EntityType.REEL
            self.id = f"reel-{url.path.removeprefix('/reel/')}"
        else:
            self.type = EntityType.PROFILE
            self.id = url.path.removeprefix("/").replace("/profilecard", "")
        self.id = self.id.removesuffix("/")
        return self

    def fetch(self: Self | str, session: Session) -> "Entity | None":
        url = self.url if isinstance(self, Entity) else self
        url = Entity.valid_entity_url(url)
        return session.exec(select(Entity).where(Entity.url == url)).one_or_none()

    @classmethod
    def from_url(cls, url: str):
        return cls.model_validate(cls(url=url))
