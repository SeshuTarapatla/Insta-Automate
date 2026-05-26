"""A flow that scrapes the selected users in queue directory."""

from random import choice

from my_modules.datetime_utils import Timestamp
from prefect import get_run_logger

from insta_automate.controllers.cli import IaTelegram
from insta_automate.controllers.instagram import Insta
from insta_automate.controllers.prefect import IaSession
from insta_automate.controllers.queue import SCRAPE_QUEUE, Queue
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
from insta_automate.utils import jpegs, rm_empty_subdirs
from insta_automate.vars import SCRAPE_QUEUE_DIR, SCRAPED_DIR


@ia_flow()
async def entity_scrape(entity: str | None = None, n: int = Limit.SCRAPE_BATCH):
    log = get_run_logger()
    scraped, processed, scrape_queue = 0, 0, SCRAPE_QUEUE.copy()
    if entity:
        _entity = Entity.from_url(
            entity if entity.startswith(Insta.URL) else Insta.url(entity)
        )
        if (entity_dir := (SCRAPE_QUEUE_DIR / _entity.id)).is_dir():
            scrape_queue = [entity_dir]
        else:
            raise InvalidEntity(f"No directory found for entity: {entity} to scrape.")

    SCRAPE_QUEUE_DIR.mkdir(exist_ok=True, parents=True)
    SCRAPED_DIR.mkdir(exist_ok=True, parents=True)

    if jpegs(SCRAPE_QUEUE_DIR):
        session = IaSession()
        device = await device_ready()
        scrape = Scrape.fetch(session)
        switch_account("alt", device)

        for entry in scrape_queue:
            if (scraped >= n) or scrape.limit_reached:
                break
            log.info(f"Scraping from entity: @{entry.name}")
            while (scraped < n) and (not scrape.limit_reached):
                image = choice(jpegs(entry, shuffle=True) or [None])
                if not image:
                    log.warning(f"No more entities found to scrape in @{entry.name}.")
                    if not Queue.dir_exists(entry.name):
                        SCRAPE_QUEUE.remove(entry.name)
                    break
                processed += 1
                log.info(f"{processed}. {scraped + 1}/{n}: {image}: Scrape triggered")
                if await profile_scrape(image, device=device, session=session):
                    scrape.increment(session=session)
                    scraped += 1
                else:
                    scrape.increment(session=session, scraped=0)
                image.unlink()

        device.lock()
        log.info(f"Scrape complete. Processed: {processed}, Scraped: {scraped}") 
        await notify_new_entities_scraped() if scraped else None
        if scrape.limit_reached:
            tl = await IaTelegram.get_client()
            await tl.bot.notify(
                f"Scrape limit reached for {Timestamp().date()}. Limit: {scrape.scraped}"
            )
        await db_backup()
        rm_empty_subdirs()
    else:
        log.error("No entities found to scrape")


if __name__ == "__main__":
    entity_scrape.serve()
