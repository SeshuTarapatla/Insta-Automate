__all__ = ["IaPostgres", "SessionLocal"]

from my_modules.datetime_utils import now
from my_modules.logger import get_logger
from my_modules.postgres import Postgres
from sqlmodel import Session, SQLModel

from insta_automate.models.entity import Entity
from insta_automate.models.scan import Scan
from insta_automate.models.scanned import Scanned
from insta_automate.models.scrape import Scrape
from insta_automate.models.user import User
from insta_automate.vars import IA_DATABASE

log = get_logger(__name__)


class IaPostgres(Postgres):
    def __init__(self) -> None:
        super().__init__(IA_DATABASE)

    @classmethod
    def init(cls, drop: bool = False):
        started_at = now()
        ia_db = cls()
        if drop:
            if ia_db.exists:
                log.info(f"Dropping [cyan]{IA_DATABASE}[/] PostgreSQL database.")
                ia_db.drop_db(force=True)
            else:
                log.warning("No PostgreSQL database found to drop.")
        if ia_db.exists:
            log.info(f"[cyan]{IA_DATABASE}[/] PostgreSQL database already exists.")
        else:
            log.info(f"Creating a new [cyan]{IA_DATABASE}[/] PostgreSQL database.")
            ia_db.create_db()
        _ = [Entity, User, Scanned, Scan, Scrape]
        log.info(
            f"Creating required tables for [cyan]{IA_DATABASE}[/] PostgreSQL database."
        )
        SQLModel.metadata.create_all(bind=ia_db.engine)
        log.info(f"Database initialization complete. Time taken: {now() - started_at}")


engine = IaPostgres().engine


def SessionLocal() -> Session:
    return Session(bind=engine, expire_on_commit=False)
