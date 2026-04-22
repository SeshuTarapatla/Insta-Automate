from prefect import get_run_logger

from insta_automate.controllers.data import IaData
from insta_automate.tasks import ia_task


@ia_task()
async def ia_backup():
    log = get_run_logger()
    log.info("Triggering Insta Automate data backup task...")
    await IaData(log=log).backup()


@ia_task()
async def ia_restore():
    log = get_run_logger()
    log.info("Triggering Insta Automate data restore task...")
    await IaData(log=log).restore()
