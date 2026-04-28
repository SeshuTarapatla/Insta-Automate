from pathlib import Path

from my_modules.datetime_utils import Timestamp
from my_modules.inet import Internet
from PIL import Image
from prefect import get_run_logger
from sqlmodel import Session

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.postgres import IaSession
from insta_automate.exceptions import InvalidEntity
from insta_automate.models.entity import Entity
from insta_automate.models.meta import (
    EntityAccess,
    EntityRequest,
    EntityStatus,
    EntityType,
    ScanList,
)
from insta_automate.models.scanned import Scanned
from insta_automate.models.user import User
from insta_automate.tasks import ia_task
from insta_automate.tasks.device import network_access, switch_account_for_entity
from insta_automate.vars import ELEMENT_HEIGHT, IA_DIR, SCANNED_DIR, SCRAPED_DIR


async def ensure_network(object: Internet | IaDevice | None = None) -> bool:
    object = object or Internet()
    inet = object.inet if isinstance(object, IaDevice) else object
    if not inet.is_active:
        await network_access(object)
    return True


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
def scan_entity_init(
    entity: Entity, device: IaDevice | None = None, session: Session | None = None
):
    log = get_run_logger()
    device = device or IaDevice()
    session = session or IaSession()

    device.app_start()
    switch_account_for_entity(entity)
    device.open_entity(entity)
    match entity.type:
        case EntityType.PROFILE:
            access = device._profile_entity_access()
        case EntityType.REEL:
            access = device._reel_entity_access(entity.url)
        case EntityType.POST:
            access = device._post_entity_access()
    if access != EntityAccess.PUBLIC:
        log.error("Entity is private locked. Cannot proceed with scan.")
        entity.update(session, access=EntityAccess.PRIVATE, status=EntityStatus.FAILED)
        return False
    return True


@ia_task()
def add_new_entity(url: str, device: IaDevice | None = None) -> Entity:
    log = get_run_logger()
    device = device or IaDevice()
    log.info(f"Input entity url: {url}")
    entity = Entity.from_url(url)
    with IaSession() as session:
        if (_entity := entity.fetch(session)) is not None:
            log.warning(f"Entity already exists: {_entity.model_dump_json(indent=4)}")
        else:
            log.info(f"Entity type is determined to be: {entity.type.upper()}")
            log.info("Determing entity access type...")
            entity.access = device.determine_entity_access(entity)
            log.info(f"Entity access type is determined to be: {entity.access.upper()}")
            log.info(entity.model_dump_json(indent=4))
            log.info("Adding entry to Entity table.")
            entity.update(session)
    return entity


@ia_task()
async def profile_entity_scan(
    entity: Entity,
    list: ScanList = ScanList.AUTO,
    *,
    device: IaDevice | None = None,
    session: Session | None = None,
) -> bool:
    # initialize objects
    started = Timestamp()
    log = get_run_logger()
    device = device or IaDevice()
    session = session or IaSession()
    ui = device.ui

    # match entity type with scan type
    if entity.type != EntityType.PROFILE:
        msg = f"Profile entity scan is called with entity of type: {entity.type.upper()}.\n{entity.model_dump_json(indent=4)}"
        log.error(msg)
        raise InvalidEntity(msg)

    # fetch latest access status of the entity
    if not scan_entity_init(entity, device, session):
        return False

    # update entity status and log metadata
    log.info(f"Setting entity status to {EntityStatus.SCANNING.upper()}")
    entity.update(session, status=EntityStatus.SCANNING)
    profile = User.from_ui(device.ui)
    profile.access = entity.access
    log.info(f"Root:\n{profile.model_dump_json(indent=4)}")
    session.merge(profile)
    session.commit()

    # pick which list to scan
    if list == ScanList.FOLLOWERS:
        _list, list_element = "followers", ui.profile_followers
    elif list == ScanList.FOLLOWING:
        _list, list_element = "following", ui.profile_following
    else:
        if profile.f1 < profile.f2:
            _list, list_element = "followers", ui.profile_followers
        else:
            _list, list_element = "following", ui.profile_following
    log.info(f"Opening profile {_list} list.")
    list_element.click()
    ui.follower_container.must_wait()

    # variable initialization
    SCANNED_DIR.mkdir(exist_ok=True, parents=True)
    current, last = "undef", "undef1"
    scanned, added = 0, 0
    scanned_set = set()

    # start scanning
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
            if current not in scanned_set and follower.exists(session) is False:
                added += 1
                scanned_set.add(current)
                session.add(follower)
                session.commit()
                jpeg = SCANNED_DIR / f"{current}.jpg"
                element.screenshot().save(jpeg)
                log.info(
                    f"[{added}/{scanned}] @{current} | Exported to: {jpeg.relative_to(IA_DIR)}"
                )
        entity.update(session)
        await ensure_network(device)
        device.swipe_list(elements)
        while True:
            try:
                ui.follower_container_loader.click_gone()
                device.press(
                    "back"
                ) if ui.action_bar_title.get_text() != entity.id else None
                device.sleep(0.5)
                break
            except Exception:
                pass
        if current == last and ui.suggested_for_you.exists:
            break
        else:
            last = current

    # update entity status to COMPLETE and return
    entity.update(session, status=EntityStatus.COMPLETED)
    log.info(
        f"Scan complete. Scanned total: {scanned} | New entities: {added} | Total time taken: {Timestamp() - started} "
    )
    device.press("back")
    return True


@ia_task()
async def post_entity_scan(
    entity: Entity, device: IaDevice | None = None, session: Session | None = None
):
    started = Timestamp()
    log = get_run_logger()
    device = device or IaDevice()
    session = session or IaSession()
    ui = device.ui

    if entity.type not in (EntityType.REEL, EntityType.POST):
        msg = f"Post entity scan is called with entity of type: {entity.type.upper()}.\n{entity.model_dump_json(indent=4)}"
        log.error(msg)
        raise InvalidEntity(msg)

    # fetch latest access status of the entity
    if not scan_entity_init(entity, device, session):
        return False

    # update entity status and log metadata
    log.info(f"Setting entity status to {EntityStatus.SCANNING.upper()}")
    entity.update(session, status=EntityStatus.SCANNING)

    # open likes list to scan
    if entity.type == EntityType.REEL:
        likes_element = ui.reel_like_count
    else:
        likes_element = ui.post_like_count
    likes_element.click(offset=(0, 0.5))
    ui.likes_drag_bar.drag_to(0, 0)

    # variable initialization
    SCANNED_DIR.mkdir(exist_ok=True, parents=True)
    current, last = "undef", "undef1"
    scanned, added = 0, 0
    scanned_set = set()

    while True:
        ui.like_container.must_wait()
        elements = [
            element
            for element in ui.like_container
            if ui.height(element, timeout=5) == ELEMENT_HEIGHT
        ]
        for element in elements:
            scanned += 1
            current = element.child(
                resourceId=ui.like_container_id.selector["resourceId"]
            ).get_text()
            like = Scanned(id=current, root=entity.id)
            if current not in scanned_set and like.exists(session) is False:
                added += 1
                scanned_set.add(current)
                session.add(like)
                jpeg = SCANNED_DIR / f"{current}.jpg"
                element.screenshot().save(jpeg)
                log.info(
                    f"[{added}/{scanned}] @{current} | Exported to: {jpeg.relative_to(IA_DIR)}"
                )
        entity.update(session)
        await ensure_network(device)
        device.swipe_list(elements)
        if current == last:
            break
        else:
            last = current

    # update entity status to COMPLETE and return
    entity.update(session, status=EntityStatus.COMPLETED)
    log.info(
        f"Scan complete. Scanned total: {scanned} | New entities: {added} | Total time taken: {Timestamp() - started} "
    )
    device.press("back")
    return True


@ia_task()
async def profile_scrape(
    id: str,
    buffer: float = 5,
    device: IaDevice | None = None,
    session: Session | None = None,
) -> Path | bool:
    log = get_run_logger()
    device = device or IaDevice()
    session = session or IaSession()
    ui = device.ui
    inet = Internet()

    f_min, f_max = 100, 2500

    await ensure_network(device)
    entity = Entity.from_id(id)

    while True:
        log.info(f"Scraping profile: @{id}")
        device.open_entity(entity)
        if ui.profile_id.wait(timeout=5):
            break
        elif not inet.is_active:
            await ensure_network(device)
        else:
            log.error(f"@{id}: Profile not found")
            return False

    user = User.from_ui(ui, session)
    if access := device._profile_entity_access():
        user.access = access
    user.update(session)

    if user.access == EntityAccess.PUBLIC:
        log.error(
            f"@{id} access is found out to be: {EntityAccess.PUBLIC.upper()}. Skipping scrape."
        )
        return False
    elif user.p == 0:
        log.error(f"@{id} has zero posts. Skipping scrape.")
        return False
    elif (_min := min(user.f1, user.f2)) < f_min:
        log.error(f"@{id} has {_min} < {f_min} followers. Skipping scrape.")
        return False
    elif (_max := max(user.f1, user.f2)) > f_max:
        log.error(f"@{id} has {_max} > {f_max} followers. Skipping scrape.")
        return False

    profile_page = ui.profile_page.screenshot()
    crop_height = int(ui.profile_follow_button.center()[-1])
    profile_header = profile_page.crop((0, 0, profile_page.width, crop_height))
    width, height = profile_header.size

    dp = ui.profile_avatar_small.screenshot()
    dp_try = 0
    while dp_try <= 3:
        dp_try += 1
        ui.profile_avatar.long_click()
        ui.sleep()
        if ui.profile_avatar_expanded.wait(timeout=5):
            dp = ui.profile_avatar_expanded.screenshot()
            break
    dp_resized = dp.resize((width, width), Image.Resampling.LANCZOS)
    height += dp_resized.height

    profile_report = Image.new("RGB", (width, height))
    profile_report.paste(dp_resized)
    profile_report.paste(profile_header, (0, dp_resized.height))

    output = SCRAPED_DIR / f"{id}.jpg"
    profile_report.save(output)
    log.info(f"Scrape exported to {output}")

    device.press("back")
    device.sleep(buffer)

    return output


@ia_task()
async def profile_follow(
    id: str,
    buffer: float = 5,
    device: IaDevice | None = None,
    session: Session | None = None,
) -> bool:
    log = get_run_logger()
    device = device or IaDevice()
    session = session or IaSession()
    ui = device.ui
    inet = Internet()

    await ensure_network(device)
    entity = Entity.from_id(id)

    while True:
        log.info(f"Following profile: @{id}")
        device.open_entity(entity)
        if ui.profile_id.wait(timeout=5):
            break
        elif not inet.is_active:
            await ensure_network(device)
        else:
            log.error(f"@{id}: Profile not found")
            return False

    if device._profile_entity_access() == EntityAccess.PUBLIC:
        log.error(
            f"@{id} access is found out to be: {EntityAccess.PUBLIC.upper()}. Skipping scrape."
        )
        return False

    if ui.profile_follow_button.wait(timeout=5):
        current = ui.profile_follow_button.get_text()
        match current:
            case EntityRequest.FOLLOW:
                ui.profile_follow_button.click()
                log.info(f"@{id} follow successful.")
                status = True
            case EntityRequest.REQUESTED | EntityRequest.FOLLOWING:
                log.warning(
                    f"@{id} profile request status is already: {current.upper()}"
                )
                status = False
            case _:
                log.error(f"@{id} profile unknown status: {current.upper()}")
                status = False
        status = True
    else:
        log.error(f"@{id} follow failed.")
        status = False

    device.sleep(buffer)
    return status
