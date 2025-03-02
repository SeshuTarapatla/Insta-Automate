from datetime import datetime
from enum import Enum as EnumBase
from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from model.base import Base, schema


class ScannedList(EnumBase):
    """Enum for scanned list."""
    FOLLOWERS   = "followers"
    FOLLOWING   = "following"
    LIKES       = "likes"
    SAVED       = "saved"


class Audit(Base):
    """Audit table ORM."""
    __tablename__ = "audit"
    id          : Mapped[int]      = mapped_column(Integer, primary_key=True)
    root        : Mapped[str]      = mapped_column(String(64))
    list        : Mapped[ScannedList]  = mapped_column(Enum(ScannedList, schema=schema))
    count       : Mapped[int]      = mapped_column(Integer)
    timestamp   : Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    