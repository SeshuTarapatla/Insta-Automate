from prefect import get_run_logger

from insta_automate.controllers.cli import db_backup as _db_backup
from insta_automate.tasks import ia_task


@ia_task()
async def db_backup():
    log = get_run_logger()
    log.info("Triggering Insta Automate database backup task...")
    try:
        await _db_backup()
    except Exception as e:
        log.error(f"Taking db backup failed:\n{e}")
