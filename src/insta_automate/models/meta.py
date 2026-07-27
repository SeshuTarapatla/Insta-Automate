from enum import StrEnum, auto

from dotenv import get_key
from pydantic import BaseModel

from insta_automate.vars import CONFIG


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


class EntityRequest(StrEnum):
    FOLLOW = "Follow"
    REQUESTED = "Requested"
    FOLLOWING = "Following"


class Limit:
    """Live limit values, read from config.env with these as fallback defaults."""

    _DEFAULTS = {
        "PROFILES": 10,
        "REELS": 30,
        "POSTS": 30,
        "SCRAPE": 300,
        "SCRAPE_BATCH": 10,
        "FOLLOW": 60,
        "FOLLOW_BATCH": 5,
        "FMIN": 100,
        "FMAX": 2000,
    }

    @staticmethod
    def get(key: str) -> int:
        value = get_key(CONFIG, key)
        return int(value) if value else Limit._DEFAULTS[key]


class AccessPrediction(BaseModel):
    result: EntityAccess


class GenderPrediction(BaseModel):
    result: Gender
