from typing import Literal

from my_modules.datetime_utils import Timestamp
from prefect import get_run_logger
from sqlmodel import Session

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.postgres import SessionLocal
from insta_automate.exceptions import InvalidEntity
from insta_automate.models.entity import Entity
from insta_automate.models.meta import EntityAccess, EntityStatus, EntityType
from insta_automate.models.scanned import Scanned
from insta_automate.models.user import User
from insta_automate.tasks import ia_task
from insta_automate.vars import ELEMENT_HEIGHT, IA_DIR


@ia_task()
def device_ready() -> bool:
    device = IaDevice()
    device.start_scrcpy()
    device.unlock()
    device.app_start()
    return True


@ia_task()
def switch_account(
    account: Literal["main", "alt"], device: IaDevice | None = None
) -> bool:
    log = get_run_logger()
    device = device or IaDevice()
    log.info(f"Switching to {account.upper()} account.")
    return device.switch_account(account)


@ia_task()
def determine_entity_access(
    entity: Entity, device: IaDevice | None = None
) -> EntityAccess:
    log = get_run_logger()
    device = device or IaDevice()
    log.info(f"Determining access of {entity.url}")
    entity.access = device.determine_entity_access(entity)
    log.info(f"Entity access is found out to be: {entity.access.upper()}")
    return entity.access


@ia_task()
def add_new_entity(url: str, device: IaDevice | None = None) -> Entity:
    log = get_run_logger()
    device = device or IaDevice()
    log.info(f"Input entity url: {url}")
    entity = Entity.from_url(url)
    with SessionLocal() as session:
        if (_entity := entity.fetch(session)) is not None:
            log.warning(f"Entity already exists: {_entity.model_dump_json(indent=4)}")
        else:
            log.info(f"Entity type is determined to be: {entity.type.upper()}")
            log.info("Determing entity access type...")
            entity.access = device.determine_entity_access(entity)
            log.info(f"Entity access type id determined to be: {entity.access.upper()}")
            log.info(entity.model_dump_json(indent=4))
            log.info("Adding entry to Entity table.")
            session.add(entity)
            session.commit()
    return entity


@ia_task()
def profile_entity_scan(
    entity: Entity, *, device: IaDevice | None = None, session: Session | None = None
) -> bool:
    # initialize objects
    started = Timestamp()
    log = get_run_logger()
    device = device or IaDevice()
    session = session or SessionLocal()
    scanned_dir = IA_DIR / "scanned"
    ui = device.ui

    # match entity type with scan type
    if entity.type != EntityType.PROFILE:
        msg = f"Profile entity scan is called with entity of type: {entity.type.upper()}.\n{entity.model_dump_json(indent=4)}"
        log.error(msg)
        raise InvalidEntity(msg)

    # fetch latest access status of the entity
    device.unlock()
    device.app_start()
    switch_account("alt" if entity.access == EntityAccess.PUBLIC else "main", device)
    device.open_url(entity.url)
    if device.determine_entity_access(entity) != EntityAccess.PUBLIC:
        log.error("Entity is private locked. Cannot proceed with scan.")
        entity.access = EntityAccess.PRIVATE
        entity.status = EntityStatus.FAILED
        session.merge(entity)
        session.commit()
        return False

    # start scanning
    log.info(f"Setting entity status to {EntityStatus.SCANNING.upper()}")
    entity.status = EntityStatus.SCANNING
    session.merge(entity)
    session.commit()
    profile = User.from_ui(device.ui)
    profile.access = entity.access
    log.info(f"Root:\n{profile.model_dump_json(indent=4)}")
    session.add(profile)
    session.commit()
    if profile.f1 < profile.f2:
        log.info("Opening profile followers list.")
        ui.profile_followers.click()
    else:
        log.info("Opening profile following list.")
        ui.profile_following.click()
    ui.follower_container.must_wait()
    scanned_dir.mkdir(exist_ok=True, parents=True)
    current, last = "undef", "undef1"
    scanned, added = 0, 0
    scanned_set = set()
    while True:
        elements = [
            element
            for element in ui.follower_container
            if ui.height(element) == ELEMENT_HEIGHT
        ]
        for element in elements:
            scanned += 1
            current = element.child(
                resourceId=ui.follower_container_id.selector["resourceId"]
            ).get_text()
            follower = Scanned(id=current, root=entity.id)
            if current not in scanned_set and follower.fetch(session) is None:
                added += 1
                scanned_set.add(current)
                session.add(follower)
                jpeg = scanned_dir / f"{current}.jpg"
                element.screenshot().save(jpeg)
                log.info(
                    f"[{added}/{scanned}] @{current} | Screenshot exported to: {jpeg.relative_to(IA_DIR)}"
                )
        entity.update(session)
        device._wait_for_network()
        device.swipe_list(elements)
        device.press("back") if ui.action_bar_title.get_text() != entity.id else None
        device.sleep(0.5)
        while True:
            try:
                ui.follower_container_loader.click_gone()
                break
            except Exception:
                pass
        if current == last:
            break
        else:
            last = current
    log.info(
        f"Scan complete. Scanned total: {scanned} | New entities: {added} | Total time taken: {Timestamp() - started} "
    )
    device.press("back")
    return True
