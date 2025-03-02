from atexit import register
from my_modules.logger import log
from my_modules.postgres import connection_string
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.vars import args

__all__ = ["schema", "engine", "session", "Base"]


schema = "instagram2"
metadata = MetaData(schema=schema)

engine = create_engine(url=connection_string)
Session = sessionmaker(bind=engine)

session = Session()
register(session.close_all)


class Base(DeclarativeBase):
    """Base declarative class for table mappings."""
    metadata = metadata
    __tablename__: str

    @staticmethod
    def setup() -> bool:
        """Setup instagram schema."""
        with engine.connect() as conn:
            if args.force:
                log.warning("This action will wipe existing Postgres data. Proceed with [bold white on red]CAUTION![/].")
                resp = input("Do you wish to continue? [Y/n]: ").lower().strip()
                print()
                if resp == "y":
                    log.info("Dropping previous schema: ([bold red]if exists[/])")
                    conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE;"))
                    conn.commit()
                else:
                    if resp != "n":
                        log.error(f'Invalid input: "{resp}"')
                    log.info("Postgres force setup discarded.")
                    return False
            log.info(f"Creating postgres schema: [bold blue]{schema}[/]")
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema};"))
            conn.commit()
        return True
