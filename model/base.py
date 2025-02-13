from atexit import register

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.vars import args
from utils.logger import log
from utils.sql import connection_string

__all__ = ["schema", "session", "Base"]


# instagram schema
schema = "instagram"
metadata = MetaData(schema=schema)

# connection variables
engine = create_engine(url=connection_string)
Session = sessionmaker(bind=engine)

# common session
session = Session()
register(session.close_all)


class Base(DeclarativeBase):
    """Base declarative class for table mappings."""
    __tablename__: str
    metadata = metadata

    @staticmethod
    def setup() -> bool:
        """Setup to create instagram schema."""
        with engine.connect() as conn:
            if args.force:
                log.warning("This action will wipe existing Postgres data. Proceed with [bold white on red]CAUTION![/].")
                resp = input("Do you wish to continue? [Y/n]: ").lower().strip()
                if resp == "y":
                    log.info("Dropping previous schema: ([bold red]if exists[/])")
                    conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE;"))
                    conn.commit()
                else:
                    if resp != "n":
                        log.info(f"Invalid input: {resp}")
                    log.info("Postgres force setup discarded.")
                    return False
            log.info(f"Creating postgres schema: [bold blue]{schema}[/]")
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema};"))
            conn.commit()
        return True
