from enum import StrEnum, auto

from sqlmodel import Field, Session, SQLModel, select

from insta_automate.models.meta import Gender


class ScanList(StrEnum):
    FOLLOWERS = auto()
    FOLLOWING = auto()
    AUTO = auto()


class Scanned(SQLModel, table=True):
    id: str = Field(primary_key=True)
    root: str
    gender: Gender = Gender.UNDEF

    @classmethod
    def fetch(cls, id: str, session: Session) -> "Scanned":
        return session.exec(select(cls).where(cls.id == id)).one_or_none() or cls(
            id=id, root=id
        )
