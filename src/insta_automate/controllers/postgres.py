from my_modules.datetime_utils import now
from my_modules.logger import get_logger
from my_modules.postgres import Postgres

from insta_automate.vars import IA_DATABASE

log = get_logger(__name__)


class IaPostgres:
    @staticmethod
    def init(drop: bool = False):
        started_at = now()
        ia_db = Postgres(IA_DATABASE)
        if drop:
            if ia_db.db_exists:
                log.info(f"Dropping [cyan]{IA_DATABASE}[/] PostgreSQL database.")
                ia_db.drop_db(force=True)
            else:
                log.warning("No PostgreSQL database found to drop.")
        if ia_db.db_exists:
            log.info(f"[cyan]{IA_DATABASE}[/] PostgreSQL database already exists.")
        else:
            log.info(f"Creating a new [cyan]{IA_DATABASE}[/] PostgreSQL database.")
            ia_db.create_db()
        log.info(f"Database initialization complete. Time taken: {now() - started_at}")
