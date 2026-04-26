from datetime import date as date_, datetime

from my_modules.datetime_utils import Timestamp
from sqlmodel import Field, SQLModel, Session, select

from insta_automate.models.meta import DailyLimit


class Scrape(SQLModel, table=True):
    date: date_ = Field(primary_key=True, default_factory=lambda: Timestamp().date())
    scraped: int = Field(default=0, ge=0)
    added_on: datetime = Field(default_factory=Timestamp)
    updated_on: datetime = Field(
        default_factory=Timestamp, sa_column_kwargs={"onupdate": Timestamp}
    )

    @classmethod
    def fetch(cls, session: Session, date: date_ | None = None):
        date = date or Timestamp().date()
        if scrape := session.exec(select(cls).where(cls.date == date)).one_or_none():
            return scrape
        return cls()

    def increment(self, value: int = 1, session: Session | None = None):
        self.scraped += value
        if session:
            session.merge(self)
            session.commit()

    @property
    def limit_reached(self) -> bool:
        return self.scraped >= DailyLimit.SCRAPE
