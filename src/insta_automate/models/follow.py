from datetime import date as date_, datetime

from my_modules.datetime_utils import Timestamp
from sqlmodel import Field, SQLModel, Session, select

from insta_automate.models.meta import Limit


class Follow(SQLModel, table=True):
    date: date_ = Field(primary_key=True, default_factory=lambda: Timestamp().date())
    followed: int = Field(default=0, ge=0)
    added_on: datetime = Field(default_factory=Timestamp)
    updated_on: datetime = Field(
        default_factory=Timestamp, sa_column_kwargs={"onupdate": Timestamp}
    )

    @classmethod
    def fetch(cls, session: Session, date: date_ | None = None):
        date = date or Timestamp().date()
        if scrape := session.exec(
            select(cls)
            .where(cls.date == date)
            .execution_options(populate_existing=True)
        ).one_or_none():
            return scrape
        return cls()

    def increment(self, *, followed: int = 1, session: Session | None = None):
        self.followed += followed
        if session:
            session.merge(self)
            session.commit()

    @property
    def limit_reached(self) -> bool:
        return self.followed >= Limit.FOLLOW
