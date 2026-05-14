"""A flow that scrapes the selected users in queue directory."""

from random import choice

from my_modules.datetime_utils import Timestamp
from prefect import get_run_logger

from insta_automate.controllers.cli import IaTelegram
from insta_automate.controllers.instagram import Insta
from insta_automate.controllers.prefect import IaSession
from insta_automate.exceptions import InvalidEntity
from insta_automate.flows import ia_flow
from insta_automate.models.entity import Entity
from insta_automate.models.meta import Limit
from insta_automate.models.scrape import Scrape
from insta_automate.tasks.data import db_backup
from insta_automate.tasks.device import device_ready, switch_account
from insta_automate.tasks.ia import (
    profile_scrape,
)
from insta_automate.tasks.telegram import notify_new_entities_scraped
from insta_automate.utils import jpegs
from insta_automate.vars import SCRAPE_QUEUE_DIR, SCRAPED_DIR


@ia_flow()
async def entity_scrape(entity: str | None = None, n: int = Limit.SCRAPE_BATCH):
    log = get_run_logger()
    scraped, processed = 0, 0
    if entity:
        _entity = (
            Entity.from_url(entity)
            if entity.startswith(Insta.URL)
            else Entity.from_id(entity)
        )
        if (scrape_queue_dir := (SCRAPE_QUEUE_DIR / _entity.id)).exists():
            scraped_dir = SCRAPED_DIR / _entity.id
            log.info(f"Scraping from custom entity: {entity}")
        else:
            raise InvalidEntity(f"No directory found for entity: {entity} to scrape.")
    else:
        scrape_queue_dir = SCRAPE_QUEUE_DIR
        scraped_dir = SCRAPED_DIR

    scrape_queue_dir.mkdir(exist_ok=True, parents=True)
    scraped_dir.mkdir(exist_ok=True, parents=True)
    if jpegs(scrape_queue_dir):
        session = IaSession()
        device = await device_ready()
        scrape = Scrape.fetch(session)
        switch_account("alt", device)
        while (scraped < n) and (not scrape.limit_reached):
            processed += 1
            image = choice(jpegs(scrape_queue_dir, shuffle=True) or [None])
            if not image:
                log.warning("No more entities found to scrape.")
                break
            log.info(f"{processed}. {scraped + 1}/{n}: @{image.stem}: Scrape triggered")
            if await profile_scrape(
                image.stem, scraped_dir, device=device, session=session
            ):
                scrape.increment(session=session)
                scraped += 1
            else:
                scrape.increment(session=session, scraped=0)
            image.unlink()
        device.lock()
        log.info(f"Scrape complete. Processed: {processed}, Scraped: {scraped}")
        await notify_new_entities_scraped()
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
