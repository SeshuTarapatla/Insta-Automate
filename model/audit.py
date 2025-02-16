from datetime import datetime
from sqlalchemy import DateTime, Enum, Integer, String
from model.base import Base, schema
from sqlalchemy.orm import mapped_column, Mapped
from enum import Enum as EnumBase


class Scanned(EnumBase):
    """Enum for scanned list."""
    FOLLOWERS   = "Followers"
    FOLLOWING   = "Following"
    LIKES       = "Likes"
    SAVED       = "Saved"


class Audit(Base):
    """Audit table ORM."""
    __tablename__ = "audit"
    id          : Mapped[int]       = mapped_column(Integer, primary_key=True, autoincrement=True)
    root        : Mapped[str]       = mapped_column(String(128))
    list        : Mapped[Scanned]   = mapped_column(Enum(Scanned, schema=schema))
    count       : Mapped[int]       = mapped_column(Integer, default=0)
    timestamp   : Mapped[datetime]  = mapped_column(DateTime, default=datetime.now)