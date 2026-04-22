"""A flow that scans for user from the given Insta Automate Entity URL."""

from prefect import get_run_logger

from insta_automate.controllers.postgres import SessionLocal
from insta_automate.flows import ia_flow
from insta_automate.models.entity import Entity
from insta_automate.models.meta import EntityAccess, EntityStatus, EntityType, Scan
from insta_automate.models.scanned import ScanList
from insta_automate.tasks.db import db_backup
from insta_automate.tasks.ia import (
    determine_entity_access,
    device_ready,
    profile_entity_scan,
    post_entity_scan,
)
from insta_automate.tasks.tl import notify_scan_limit_reached, notify_unfollow


@ia_flow()
async def entity_scan(url: str, list: ScanList = ScanList.AUTO):
    log = get_run_logger()
    session = SessionLocal()
    status = None
    scan = Scan.fetch(session)
    device_ready()
    if (entity := Entity.fetch(url, session)) is None:
        log.warning(
            f"Entity with url: {url} not found in the db. Creating a new one..."
        )
        entity = Entity.from_url(url)
        entity.access = determine_entity_access(entity)
        session.add(entity)
        session.commit()
    log.info(entity.model_dump_json(indent=4))
    if entity.status == EntityStatus.COMPLETED:
        log.error("This entity has been already scanned.")
        return
    match entity.type:
        case EntityType.PROFILE:
            status = profile_entity_scan(entity, list=list, session=session)
            if status:
                scan.increment(EntityType.PROFILE, session=session)
                if entity.access == EntityAccess.PRIVATE:
                    await notify_unfollow(entity)
        case EntityType.REEL | EntityType.POST:
            status = post_entity_scan(entity, session=session)
        case _:
            log.error(f"Entity scan for '{entity.type.upper()}' is not implemented.")
    if limit := scan.limit_reached:
        await notify_scan_limit_reached(*limit)
    await db_backup()


if __name__ == "__main__":
    entity_scan.serve()
