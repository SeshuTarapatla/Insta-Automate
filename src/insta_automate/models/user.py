from datetime import datetime

from my_modules.datetime_utils import now
from sqlmodel import Field, SQLModel

from insta_automate.models.meta import EntityAccess


class User(SQLModel, table=True):
    id: str = Field(primary_key=True)
    root: str
    name: str
    bio: str
    posts: str
    followers: str
    following: str
    p: int
    f1: int
    f2: int
    access: EntityAccess
    added_on: datetime = Field(default_factory=now)