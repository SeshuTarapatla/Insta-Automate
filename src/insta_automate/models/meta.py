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


class Config:
    """Live config values, read from config.env with these as fallback defaults.

    Type comes from the default's own type (bool checked before int, since
    bool is an int subclass), so a key's type is declared once, here.
    """

    _DEFAULTS: dict[str, int | float | bool | str] = {
        # Limits
        "PROFILES": 10,
        "REELS": 30,
        "POSTS": 30,
        "SCRAPE": 300,
        "SCRAPE_BATCH": 10,
        "FOLLOW": 60,
        "FOLLOW_BATCH": 5,
        "FMIN": 100,
        "FMAX": 2000,
        # Trigger timings (seconds)
        "TG_KEEPALIVE_WAIT": 1800,
        "INGEST_POLL_WAIT": 600,
        "SCAN_POLL_WAIT": 10,
        "SCAN_WAIT": 0,
        "CLASSIFY_POLL_WAIT": 10,
        "SCRAPE_WAIT": 600,
        "SCRAPE_BUFFER": 10,
        "FOLLOW_WAIT": 1200,
        "FOLLOW_BUFFER": 10,
        "DAY_CHANGE_POLL": 60,
        "TICK": 5,
        # Gates
        "SCRAPE_RESERVE_FACTOR": 3,
        "SCAN_LIST": "auto",
        # Control-center wiring
        "IA_AGENT_URL": "http://172.19.16.1:8787",
        "NOTIFY_POLICY": "app_first",
    }

    @staticmethod
    def get(key: str) -> int | float | bool | str:
        default = Config._DEFAULTS[key]
        value = get_key(CONFIG, key)
        if not value:
            return default
        if isinstance(default, bool):
            return value != "0"
        if isinstance(default, int):
            return int(value)
        if isinstance(default, float):
            return float(value)
        return value


Limit = Config


class AccessPrediction(BaseModel):
    result: EntityAccess


class GenderPrediction(BaseModel):
    result: Gender
