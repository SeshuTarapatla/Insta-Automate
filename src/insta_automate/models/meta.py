from datetime import datetime, date as date_
from enum import StrEnum, auto

from my_modules.datetime_utils import Timestamp
from sqlmodel import Field, SQLModel, Session, select


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


class Relation(StrEnum):
    FOLLOW = auto()
    REQUESTED = auto()
    FOLLOWING = auto()


class Gender(StrEnum):
    MALE = auto()
    FEMALE = auto()
    UNDEF = auto()


class Scan(SQLModel, table=True):
    date: date_ = Field(primary_key=True, default_factory=lambda: Timestamp().date())
    profiles: int = Field(default=0, ge=0, le=10)
    reels: int = Field(default=0, ge=0, le=30)
    posts: int = Field(default=0, ge=0, le=30)
    added_on: datetime = Field(default_factory=Timestamp)
    updated_on: datetime = Field(
        default_factory=Timestamp, sa_column_kwargs={"onupdate": Timestamp}
    )

    @classmethod
    def fetch(cls, session: Session, date: date_ | None = None):
        date = date or Timestamp().date()
        if scan := session.exec(select(cls).where(cls.date == date)).one_or_none():
            return scan
        return cls()

    def increment(self, entity_type: EntityType, session: Session):
        match entity_type:
            case EntityType.PROFILE:
                self.profiles += 1
            case EntityType.REEL:
                self.reels += 1
            case EntityType.POST:
                self.posts += 1
        session.merge(self)
        session.commit()
