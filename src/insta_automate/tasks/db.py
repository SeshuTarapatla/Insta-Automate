from prefect import get_run_logger, task

from insta_automate.controllers.cli import db_backup as _db_backup


@task
async def db_backup():
    log = get_run_logger()
    log.info("Triggering Insta Automate database backup task...")
    await _db_backup()
