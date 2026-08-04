"""A flow that scrapes the selected users in queue directory."""

from random import choice

from my_modules.datetime_utils import Timestamp
from prefect import get_run_logger

from insta_automate.controllers.agent import AgentClient
from insta_automate.controllers.instagram import Insta
from insta_automate.controllers.notify import notify
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
from insta_automate.vars import FOLLOW_QUEUE_DIR, SCRAPED_DIR


@ia_flow()
async def entity_follow(
    entity: str | None = None,
    n: int | None = None,
    force: bool = False,
    reduce_reserve: bool = False,
):
    log = get_run_logger()
    agent = AgentClient()
    await agent.emit({
        "flow": "entity-follow", "kind": "flow.started", "entity": entity,
        "reduce_reserve": reduce_reserve,
    })
    n = n if n is not None else Limit.get("FOLLOW_BATCH")
    reserve_target = Limit.get("FOLLOW") * Limit.get("SCRAPE_RESERVE_FACTOR")
    pool_count = len(jpegs(SCRAPED_DIR) + jpegs(FOLLOW_QUEUE_DIR))
    followed, processed, follow_queue = 0, 0, FOLLOW_QUEUE.copy()

    def more_to_do() -> bool:
        return pool_count > reserve_target if reduce_reserve else followed < n

    if reduce_reserve and not more_to_do():
        log.info(
            f"scraped+follow_queued already at {pool_count} ≤ reserve target {reserve_target} "
            "— nothing to drain."
        )

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
            if (not more_to_do()) or (follow.limit_reached and not force):
                break
            log.info(f"Following from entity: @{entry.name}")
            while more_to_do() and (force or not follow.limit_reached):
                image = choice(jpegs(entry, shuffle=True) or [None])
                if not image:
                    log.warning(f"No more entities found to follow in @{entry.name}.")
                    FOLLOW_QUEUE.remove(entry.name)
                    break
                processed += 1
                if reduce_reserve:
                    log.info(
                        f"{processed}. pool {pool_count}→{reserve_target}: @{image}: Follow triggered"
                    )
                else:
                    log.info(f"{processed}. {followed + 1}/{n}: @{image}: Follow triggered")
                if await profile_follow(image, device=device, session=session):
                    follow.increment(session=session)
                    followed += 1
                image.unlink()
                if reduce_reserve:
                    pool_count -= 1

        device.lock()
        log.info(
            f"Follow flow complete. Total followed on {Timestamp().date()}: {follow.followed}/{Limit.get('FOLLOW')}"
            + (
                f" · scraped+follow_queued now {pool_count} (target {reserve_target})"
                if reduce_reserve else ""
            )
        )
        if follow.limit_reached:
            if reduce_reserve:
                log.info(
                    f"Follow limit reached for the day ({follow.followed}) but this was a "
                    "Reduce reserve run, so it kept going."
                )
            elif force:
                log.info(
                    f"Follow limit reached for the day ({follow.followed}) but this run was "
                    "forced, so it kept going."
                )
            else:
                log.warning("Follow limit has reached for the day.")
                await notify(
                    f"Follow limit reached for {Timestamp().date()}. Limit: {follow.followed}",
                    level="warn",
                    tags=("follow", "limit"),
                )
        await db_backup()
        rm_empty_subdirs()
        await agent.emit({
            "flow": "entity-follow", "kind": "flow.completed", "entity": entity,
            "counters": {"processed": processed, "followed": followed},
            "reduce_reserve": reduce_reserve,
        })
    else:
        log.error("No entities found to follow")
        await agent.emit({
            "flow": "entity-follow", "kind": "flow.completed", "entity": entity,
            "reason": "no work",
        })


if __name__ == "__main__":
    entity_follow.serve()
