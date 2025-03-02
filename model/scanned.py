from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from model.base import Base


class Scanned(Base):
    """Scanned table ORM."""
    __tablename__ = "scanned"
    id          : Mapped[str]       = mapped_column(String(64), primary_key=True)
    root        : Mapped[str]       = mapped_column(String(64))
    timestamp   : Mapped[datetime]  = mapped_column(DateTime)
    