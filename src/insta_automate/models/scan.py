from insta_automate.models.meta import EntityType, ScanLimit


from my_modules.datetime_utils import Timestamp
from sqlmodel import Field, SQLModel, Session, select


from datetime import date as date_, datetime
from typing import Literal


class Scan(SQLModel, table=True):
    date: date_ = Field(primary_key=True, default_factory=lambda: Timestamp().date())
    profiles: int = Field(default=0, ge=0, le=ScanLimit.PROFILES)
    reels: int = Field(default=0, ge=0, le=ScanLimit.REELS)
    posts: int = Field(default=0, ge=0, le=ScanLimit.POSTS)
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

    def increment(
        self, entity_type: EntityType, value: int = 1, session: Session | None = None
    ):
        match entity_type:
            case EntityType.PROFILE:
                self.profiles += value
            case EntityType.REEL:
                self.reels += value
            case EntityType.POST:
                self.posts += value
        if session:
            session.merge(self)
            session.commit()

    @property
    def limit_reached(
        self,
    ) -> tuple[date_, Literal["profiles", "reels", "posts"], int] | None:
        if self.profiles >= ScanLimit.PROFILES:
            return self.date, "profiles", self.profiles
        elif self.reels >= ScanLimit.REELS:
            return self.date, "reels", self.reels
        elif self.posts >= ScanLimit.POSTS:
            return self.date, "posts", self.posts