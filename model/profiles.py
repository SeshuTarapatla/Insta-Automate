from datetime import datetime
from enum import Enum as EnumBase

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from model.base import Base, schema


class Relation(EnumBase):
    """Enum class for profile relation."""
    FOLLOW      = "Follow"
    FOLLOWING   = "Following"
    REQUESTED   = "Requested"
    RESTRICTED  = "Restricted"


class Profile(Base):
    """Profiles table ORM."""
    __tablename__ = "profiles"
    id              : Mapped[str]       = mapped_column(String(128), primary_key=True)
    name            : Mapped[str]       = mapped_column(String(256), nullable=True, default="")
    bio             : Mapped[str]       = mapped_column(Text, nullable=True, default="")
    posts           : Mapped[int]       = mapped_column(Integer)
    followers       : Mapped[int]       = mapped_column(Integer)
    following       : Mapped[int]       = mapped_column(Integer)
    root            : Mapped[str]       = mapped_column(String(128))
    posts_str       : Mapped[str]       = mapped_column(String(16))
    followers_str   : Mapped[str]       = mapped_column(String(16))
    following_str   : Mapped[str]       = mapped_column(String(16))
    private         : Mapped[bool]      = mapped_column(Boolean)
    verified        : Mapped[bool]      = mapped_column(Boolean)
    relation        : Mapped[Relation]  = mapped_column(Enum(Relation, schema=schema))
    timestamp       : Mapped[datetime]  = mapped_column(DateTime, default=datetime.now)
