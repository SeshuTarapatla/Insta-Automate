from typing import Self

from sqlmodel import Field, Session, SQLModel, select

from insta_automate.models.meta import Gender


class Scanned(SQLModel, table=True):
    id: str = Field(primary_key=True)
    root: str
    gender: Gender = Gender.UNDEF

    def fetch(self: Self | str, session: Session) -> "Scanned | None":
        id = self.id if isinstance(self, Scanned) else self
        return session.exec(select(Scanned).where(Scanned.id == id)).one_or_none()
    