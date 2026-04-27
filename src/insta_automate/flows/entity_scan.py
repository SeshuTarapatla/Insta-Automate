"""A flow that scans for user from the given Insta Automate Entity URL."""

from prefect import get_run_logger

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.postgres import SessionLocal
from insta_automate.flows import ia_flow
from insta_automate.models.entity import Entity
from insta_automate.models.meta import EntityAccess, EntityStatus, EntityType
from insta_automate.models.scan import Scan
from insta_automate.models.meta import ScanList
from insta_automate.tasks.data import db_backup
from insta_automate.tasks.device import device_ready
from insta_automate.tasks.ia import (
    determine_entity_access,
    post_entity_scan,
    profile_entity_scan,
)
from insta_automate.tasks.telegram import notify_scan_limit_reached, notify_profile_unfollow


@ia_flow()
async def entity_scan(url: str, list: ScanList = ScanList.AUTO, device: IaDevice | None = None):
    log = get_run_logger()
    session = SessionLocal()
    status = None
    scan = Scan.fetch(session)
    device = device or await device_ready()
    if (entity := Entity.fetch(url, session)) is None:
        log.warning(
            f"Entity with url: {url} not found in the db. Creating a new one..."
        )
        entity = Entity.from_url(url)
        entity.update(session, access=determine_entity_access(entity))
    log.info(entity.model_dump_json(indent=4))
    if entity.status == EntityStatus.COMPLETED:
        log.error("This entity has been already scanned.")
        return
    match entity.type:
        case EntityType.PROFILE:
            status = await profile_entity_scan(entity, list=list, device=device, session=session)
            if status is True and entity.access == EntityAccess.PRIVATE:
                await notify_profile_unfollow(entity)
        case EntityType.REEL | EntityType.POST:
            status = await post_entity_scan(entity, session=session, device=device)
            if status:
                scan.increment(entity.type, session=session)
        case _:
            log.error(f"Entity scan for '{entity.type.upper()}' is not implemented.")
    device.lock()
    if status is True:
        scan.increment(entity.type, session=session)
        await db_backup()
    if limit := scan.limit_reached:
        await notify_scan_limit_reached(*limit)


if __name__ == "__main__":
    entity_scan.serve()
