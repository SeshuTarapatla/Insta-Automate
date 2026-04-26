from sqlmodel import Field, Session, SQLModel, select

from insta_automate.models.meta import EntityAccess, Gender


class Scanned(SQLModel, table=True):
    id: str = Field(primary_key=True)
    root: str
    access: EntityAccess = EntityAccess.UNDEF
    gender: Gender = Gender.UNDEF

    @classmethod
    def fetch(cls, id: str, session: Session) -> "Scanned":
        return session.exec(select(cls).where(cls.id == id)).one_or_none() or cls(
            id=id, root=id
        )

    def exists(self, session: Session) -> bool:
        return bool(
            session.exec(select(Scanned).where(Scanned.id == self.id)).one_or_none()
        )
