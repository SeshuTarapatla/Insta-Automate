from my_modules.kubernetes import Kubernetes
from my_modules.logger import log

from model.audit import Audit
from model.base import Base, engine
from model.profiles import Profile
from model.scanned import Scanned

# list of all tables under ORM.
tables: list[type[Base]] = [Audit, Scanned, Profile]


def setup() -> None:
    """Setup required instagram schema and tables for the app."""
    log.info("Insta Automate: [yellow]Postgres DB setup[/]")
    if not Kubernetes.pod_running(app="postgres"):
        log.critical("Postgres service is not running")
        exit(1)
    log.info("Postgres service is running\n")
    if Base.setup():
        log.info(f"Creating required tables: [[green]'{"', '".join(map(lambda x: x.__tablename__, tables))}'[/]]")
        Base.metadata.create_all(bind=engine)
        log.info("Database setup complete.")
