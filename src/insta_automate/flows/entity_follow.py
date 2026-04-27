"""A flow that scrapes the selected users in queue directory."""

from random import choice

from my_modules.datetime_utils import Timestamp
from prefect import get_run_logger

from insta_automate.controllers.cli import IaTelegram
from insta_automate.controllers.prefect import IaSession
from insta_automate.flows import ia_flow
from insta_automate.models.follow import Follow
from insta_automate.models.meta import Limit
from insta_automate.tasks.data import db_backup
from insta_automate.tasks.device import device_ready, switch_account
from insta_automate.tasks.ia import (
    profile_scrape,
)
from insta_automate.vars import FOLLOW_QUEUE_DIR


@ia_flow()
async def entity_follow():
    log = get_run_logger()
    FOLLOW_QUEUE_DIR.mkdir(exist_ok=True, parents=True)
    images = list(FOLLOW_QUEUE_DIR.glob("*.jpg"))
    followed = 0
    if images:
        session = IaSession()
        device = await device_ready()
        follow = Follow.fetch(session)
        switch_account("alt", device)
        while (followed < Limit.FOLLOW_BATCH) and (not follow.limit_reached):
            image = choice(images)
            log.info(
                f"{followed + 1}/{Limit.FOLLOW_BATCH}: @{image.stem}: Follow triggered"
            )
            if await profile_scrape(image.stem, device=device, session=session):
                follow.increment(session=session)
                followed += 1
            image.unlink()
        device.lock()
        if follow.limit_reached:
            tl = await IaTelegram.get_client()
            await tl.bot.notify(
                f"Follow limit reached for {Timestamp().date()}. Limit: {follow.followed}"
            )
        await db_backup()
    else:
        log.error("No entities found to follow")


if __name__ == "__main__":
    entity_follow.serve()
