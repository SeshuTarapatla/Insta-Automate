"""A flow that scrapes the selected users in queue directory."""

from random import choice

from my_modules.datetime_utils import Timestamp
from prefect import get_run_logger

from insta_automate.controllers.cli import IaTelegram
from insta_automate.controllers.prefect import SessionLocal
from insta_automate.flows import ia_flow
from insta_automate.models.meta import Limit
from insta_automate.models.scrape import Scrape
from insta_automate.tasks.data import db_backup
from insta_automate.tasks.ia import (
    SCRAPED_DIR,
    device_ready,
    profile_scrape,
    switch_account,
)
from insta_automate.vars import SCRAPE_QUEUE_DIR


@ia_flow()
async def entity_scrape(batch_length: int = Limit.SCRAPE_BATCH):
    log = get_run_logger()
    SCRAPE_QUEUE_DIR.mkdir(exist_ok=True, parents=True)
    SCRAPED_DIR.mkdir(exist_ok=True, parents=True)
    images = list(SCRAPE_QUEUE_DIR.glob("*.jpg"))
    scraped = 0
    if images:
        session = SessionLocal()
        device = device_ready()
        scrape = Scrape.fetch(session)
        switch_account("alt", device)
        while (scraped < Limit.SCRAPE_BATCH) and (scrape.scraped < Limit.SCRAPE):
            image = choice(images)
            log.info(
                f"{scraped + 1}/{Limit.SCRAPE_BATCH}: @{image.stem}: Scrape triggered"
            )
            if await profile_scrape(image.stem, device=device, session=session):
                scrape.increment(session=session)
                scraped += 1
            image.unlink()
        device.lock()
        if scrape.limit_reached:
            tl = await IaTelegram.get_client()
            await tl.bot.notify(
                f"Scrape limit reached for {Timestamp().date()}. Limit: {scrape.scraped}"
            )
        await db_backup()
    else:
        log.error("No entities found to scrape")


if __name__ == "__main__":
    entity_scrape.serve()
