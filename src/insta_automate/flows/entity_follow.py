"""A flow that scrapes the selected users in queue directory."""

from random import choice

from my_modules.datetime_utils import Timestamp
from prefect import get_run_logger

from insta_automate.controllers.cli import IaTelegram
from insta_automate.controllers.instagram import Insta
from insta_automate.controllers.prefect import IaSession
from insta_automate.exceptions import InvalidEntity
from insta_automate.flows import entity_choice, ia_flow
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
    entity = entity or entity_choice("FOLLOW_ENTITY")
    if entity:
        _entity = Entity.from_url(
            entity if entity.startswith(Insta.URL) else Insta.url(entity)
        )
        if (follow_queue_dir := (FOLLOW_QUEUE_DIR / _entity.id)).exists():
            log.info(f"Following from custom entity: {entity}")
        else:
            raise InvalidEntity(f"No directory found for entity: {entity} to follow.")
    else:
        follow_queue_dir = FOLLOW_QUEUE_DIR
    follow_queue_dir.mkdir(exist_ok=True, parents=True)
    followed = 0
    if jpegs(FOLLOW_QUEUE_DIR):
        session = IaSession()
        device = await device_ready()
        follow = Follow.fetch(session)
        switch_account("main", device)
        while (followed < n) and (not follow.limit_reached):
            image = choice(jpegs(follow_queue_dir, shuffle=True) or [None])
            if not image:
                log.warning(
                    f"No more entities found to follow in {follow_queue_dir}. Resetting back to {FOLLOW_QUEUE_DIR}."
                )
                follow_queue_dir = FOLLOW_QUEUE_DIR
                continue
            log.info(f"{followed + 1}/{n}: @{image.stem}: Follow triggered")
            if await profile_follow(image, device=device, session=session):
                follow.increment(session=session)
                followed += 1
            image.unlink()
        device.lock()
        log.info(
            f"Follow flow complete. Total followed: {follow.followed}/{Limit.FOLLOW}"
        )
        if follow.limit_reached:
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
