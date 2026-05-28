"""A flow that scrapes the selected users in queue directory."""

from random import choice

from my_modules.datetime_utils import Timestamp
from prefect import get_run_logger

from insta_automate.controllers.cli import IaTelegram
from insta_automate.controllers.instagram import Insta
from insta_automate.controllers.prefect import IaSession
from insta_automate.controllers.queue import FOLLOW_QUEUE
from insta_automate.exceptions import InvalidEntity
from insta_automate.flows import ia_flow
from insta_automate.models.entity import Entity
from insta_automate.models.follow import Follow
from insta_automate.models.meta import Limit
from insta_automate.tasks.data import db_backup
from insta_automate.tasks.device import device_ready, switch_account
from insta_automate.tasks.ia import (
    profile_follow,
)
from insta_automate.utils import jpegs, rm_empty_subdirs
from insta_automate.vars import FOLLOW_QUEUE_DIR


@ia_flow()
async def entity_follow(entity: str | None = None, n: int = Limit.FOLLOW_BATCH):
    log = get_run_logger()
    followed, processed, follow_queue = 0, 0, FOLLOW_QUEUE.copy()
    if entity:
        _entity = Entity.from_url(
            entity if entity.startswith(Insta.URL) else Insta.url(entity)
        )
        if (entity_dir := (FOLLOW_QUEUE_DIR / _entity.id)).is_dir():
            follow_queue = [entity_dir]
        else:
            raise InvalidEntity(f"No directory found for entity: {entity} to follow.")

    FOLLOW_QUEUE_DIR.mkdir(exist_ok=True, parents=True)

    if jpegs(FOLLOW_QUEUE_DIR):
        session = IaSession()
        device = await device_ready()
        follow = Follow.fetch(session)
        switch_account("main", device)

        for entry in follow_queue:
            if (followed >= n) or follow.limit_reached:
                break
            log.info(f"Following from entity: @{entry.name}")
            while (followed < n) and (not follow.limit_reached):
                image = choice(jpegs(entry, shuffle=True) or [None])
                if not image:
                    log.warning(f"No more entities found to follow in @{entry.name}.")
                    FOLLOW_QUEUE.remove(entry.name)
                    break
                processed += 1
                log.info(f"{processed}. {followed + 1}/{n}: @{image}: Follow triggered")
                if await profile_follow(image, device=device, session=session):
                    follow.increment(session=session)
                    followed += 1
                image.unlink()

        device.lock()
        log.info(
            f"Follow flow complete. Total followed on {Timestamp().date()}: {follow.followed}/{Limit.FOLLOW}"
        )
        if follow.limit_reached:
            log.warning("Follow limit has reached for the day.")
            tl = await IaTelegram.get_client()
            await tl.bot.notify(
                f"Follow limit reached for {Timestamp().date()}. Limit: {follow.followed}"
            )
        await db_backup()
        rm_empty_subdirs()
    else:
        log.error("No entities found to follow")


if __name__ == "__main__":
    entity_follow.serve()
