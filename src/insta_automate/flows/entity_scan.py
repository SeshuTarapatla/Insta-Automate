"""A flow that scans for user from the given Insta Automate Entity URL."""

from prefect import get_run_logger

from insta_automate.controllers.postgres import SessionLocal
from insta_automate.flows import ia_flow
from insta_automate.models.entity import Entity
from insta_automate.models.meta import EntityAccess, EntityStatus, EntityType
from insta_automate.tasks.ia import (
    determine_entity_access,
    device_ready,
    profile_entity_scan,
)
from insta_automate.tasks.tl import notify_unfollow


@ia_flow()
async def entity_scan(url: str):
    log = get_run_logger()
    session = SessionLocal()
    status = None
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
    match entity.type:
        case EntityType.PROFILE:
            status = profile_entity_scan(entity, session=session)
            # if status and entity.access == EntityAccess.PRIVATE:
            if status:
                await notify_unfollow(entity)
        case _:
            log.error(f"Entity scan for '{entity.type.upper()}' is not implemented.")


if __name__ == "__main__":
    entity_scan.serve()
