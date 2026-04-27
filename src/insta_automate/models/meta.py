from dataclasses import dataclass
from enum import StrEnum, auto

from pydantic import BaseModel


class EntityType(StrEnum):
    POST = auto()
    PROFILE = auto()
    REEL = auto()


class EntityAccess(StrEnum):
    PUBLIC = auto()
    PRIVATE = auto()
    UNDEF = auto()


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


class ScanList(StrEnum):
    FOLLOWERS = auto()
    FOLLOWING = auto()
    AUTO = auto()


@dataclass(frozen=True)
class Limit:
    PROFILES = 10
    REELS = 30
    POSTS = 30
    SCRAPE = 100
    SCRAPE_BATCH = 10


class AccessPrediction(BaseModel):
    result: EntityAccess


class GenderPrediction(BaseModel):
    result: Gender
