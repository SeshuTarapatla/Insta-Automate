from model.audit import Audit
from model.base import Base, engine
from model.profiles import Profile
from utils.logger import log

# list of all tables under ORM.
tables: list[type[Base]] = [Audit, Profile]


def setup() -> None:
    """Function to setup postgres schema and tables."""
    log.info("Insta Automate: [yellow]DB SETUP[/]")
    log.info("Initializing Postgres setup")
    if not Base.setup():
        return
    log.info(f"Creating required tables: [[green]'{"', '".join(map(lambda x: x.__tablename__, tables))}'[/]]")
    Base.metadata.create_all(bind=engine)
    log.info("Database setup complete.")
