import asyncio
import re
from pathlib import Path

from my_modules.datetime_utils import Timestamp
from my_modules.inet import Internet
from PIL import Image
from prefect import get_run_logger
from sqlalchemy import func
from sqlmodel import Session, select

from insta_automate.controllers.agent import AgentClient
from insta_automate.controllers.cli import append_entity
from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.notify import notify
from insta_automate.controllers.postgres import IaSession
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.exceptions import InvalidEntity
from insta_automate.models.entity import Entity
from insta_automate.models.meta import (
    EntityAccess,
    EntityRequest,
    EntityStatus,
    EntityType,
    Limit,
    ScanList,
)
from insta_automate.models.scanned import Scanned
from insta_automate.models.user import User
from insta_automate.tasks import ia_task
from insta_automate.tasks.device import network_access, switch_account_for_entity
from insta_automate.vars import (
    ELEMENT_HEIGHT,
    ENTITY_DIR,
    IA_DIR,
    SCANNED_DIR,
    SCRAPE_QUEUE_DIR,
    SCRAPED_DIR,
)


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
    device.export_entity(entity)
    return True


@ia_task()
async def add_new_entity(
    url: str, device: IaDevice | None = None, tl: IaTelegram | None = None
) -> Entity:
    log = get_run_logger()
    device = device or IaDevice()
    tl = tl or await IaTelegram.get_client()
    log.info(f"Input entity url: {url}")
    entity = Entity.from_url(url)
    with IaSession() as session:
        if (_entity := entity.fetch(session)) is not None:
            log.warning(f"Entity already exists: {_entity.model_dump_json(indent=4)}")
            img = ENTITY_DIR / f"{_entity.id}.jpg"
            await notify(
                f"[@{_entity.id}]({url}) has been already {'scraped' if _entity.status == EntityStatus.COMPLETED else 'added'}.",
                image=img,
                tags=("entity",),
                tl=tl,
                url=url,
                always_telegram=True,
            )
        else:
            log.info(f"Entity type is determined to be: {entity.type.upper()}")
            log.info("Determing entity access type...")
            entity.access = device.determine_entity_access(entity)
            log.info(f"Entity access type is determined to be: {entity.access.upper()}")
            log.info(entity.model_dump_json(indent=4))
            log.info("Adding entry to Entity table.")
            entity.update(session)
            await AgentClient().emit({
                "flow": "entity-ingest", "kind": "entity.added",
                "entity": entity.id, "subject": entity.id,
                "image": f"entities/{entity.id}.jpg",
                "extra": {"type": entity.type, "access": entity.access, "url": url},
            })
    return entity


@ia_task()
def append_entity_to_queue(entity: str):
    log = get_run_logger()
    resp = append_entity(entity)
    if resp:
        log.info(f"Entity '{entity}' has been added to queue.")
    else:
        if (ENTITY_DIR / f"{entity}.jpg").exists():
            log.warning(f"Entity '{entity}' already exists in the queue.")
        else:
            log.error(f"Entity '{entity}' is invalid / does not exist.")


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

    device.unlock()
    scanned_dir = SCANNED_DIR / entity.id

    if ui.follower_container.exists() and ui.action_bar_title.get_text() == entity.id:
        count = session.exec(
            select(func.count()).select_from(Scanned).where(Scanned.root == entity.id)
        ).one()
        scanned, added = count, count
    else:
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
        await AgentClient().emit({
            "flow": "entity-scan", "kind": "scan.started",
            "entity": entity.id, "subject": entity.id,
            "image": f"entities/{entity.id}.jpg",
            "extra": {"list": _list, "f1": profile.f1, "f2": profile.f2},
        })
        list_element.click()
        ui.follower_container.must_wait()

        # variable initialization
        scanned_dir.mkdir(exist_ok=True, parents=True)
        scanned, added = 0, 0

    current, last = "undef", "undef1"
    scanned_set = set()

    # start scanning
    while True:
        if device.locked:
            device.unlock()
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
            if current not in scanned_set and not follower.exists(session):
                added += 1
                scanned_set.add(current)
                session.add(follower)
                session.commit()
                jpeg = scanned_dir / f"{current}.jpg"
                element.screenshot().save(jpeg)
                log.info(
                    f"[{added}/{scanned}] @{current} | Exported to: {jpeg.relative_to(IA_DIR)}"
                )
                await AgentClient().emit({
                    "flow": "entity-scan", "kind": "scan.item",
                    "entity": entity.id, "subject": current,
                    "image": str(jpeg.relative_to(IA_DIR)),
                    "counters": {"added": added, "scanned": scanned},
                })
        entity.update(session)
        await ensure_network(device)
        device.swipe_list(elements, wait=0)
        await asyncio.sleep(1)
        while True:
            try:
                ui.follower_container_loader.click_gone()
                device.press(
                    "back"
                ) if ui.action_bar_title.get_text() != entity.id else None
                await asyncio.sleep(0.5)
                break
            except Exception:
                if device.locked:
                    device.unlock()
        if current == last and ui.suggested_for_you.exists:
            break
        else:
            last = current

    # update entity status to COMPLETE and return
    entity.update(session, status=EntityStatus.COMPLETED)
    duration = Timestamp() - started
    log.info(
        f"Scan complete. Scanned total: {scanned} | New entities: {added} | Total time taken: {duration} "
    )
    await AgentClient().emit({
        "flow": "entity-scan", "kind": "scan.completed",
        "entity": entity.id, "subject": entity.id,
        "counters": {"scanned": scanned, "added": added},
        "extra": {"duration_s": duration.total_seconds()},
    })
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
    elif ui.post_comment_button.exists:
        likes_element = ui.post_like_count
    elif (liked_by := ui.text_contains("Liked by")).exists:
        likes_element = liked_by
    else:
        raise Exception("Failed to open likes.")
    likes_element.click(offset=(0, 0.5))
    ui.likes_drag_bar.drag_to(0, 0)
    await AgentClient().emit({
        "flow": "entity-scan", "kind": "scan.started",
        "entity": entity.id, "subject": entity.id,
        "image": f"entities/{entity.id}.jpg",
        "extra": {"list": "likes"},
    })

    # variable initialization
    scanned_dir = SCANNED_DIR / entity.id
    scanned_dir.mkdir(exist_ok=True, parents=True)
    current, last = "undef", "undef1"
    scanned, added = 0, 0
    scanned_set = set()

    while True:
        if device.locked:
            device.unlock()
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
                jpeg = scanned_dir / f"{current}.jpg"
                element.screenshot().save(jpeg)
                log.info(
                    f"[{added}/{scanned}] @{current} | Exported to: {jpeg.relative_to(IA_DIR)}"
                )
                await AgentClient().emit({
                    "flow": "entity-scan", "kind": "scan.item",
                    "entity": entity.id, "subject": current,
                    "image": str(jpeg.relative_to(IA_DIR)),
                    "counters": {"added": added, "scanned": scanned},
                })
        entity.update(session)
        await ensure_network(device)
        device.swipe_list(elements, wait=0)
        await asyncio.sleep(1)
        if current == last:
            break
        else:
            last = current

    # update entity status to COMPLETE and return
    entity.update(session, status=EntityStatus.COMPLETED)
    duration = Timestamp() - started
    log.info(
        f"Scan complete. Scanned total: {scanned} | New entities: {added} | Total time taken: {duration} "
    )
    await AgentClient().emit({
        "flow": "entity-scan", "kind": "scan.completed",
        "entity": entity.id, "subject": entity.id,
        "counters": {"scanned": scanned, "added": added},
        "extra": {"duration_s": duration.total_seconds()},
    })
    device.press("back")
    return True


@ia_task()
async def profile_scrape(
    img: Path,
    buffer: float = 5,
    device: IaDevice | None = None,
    session: Session | None = None,
) -> Path | bool:
    log = get_run_logger()
    device = device or IaDevice()
    session = session or IaSession()
    ui = device.ui
    id = img.stem
    inet = Internet()

    await ensure_network(device)
    entity = Entity.from_id(id)

    # Emitted the instant the attempt is triggered, not once the profile page
    # actually loads - the display's "attempting" card needs to appear right
    # away (matching the log line's own "Scrape triggered"), and a profile
    # that turns out not-found below still needs a `started` for its
    # `scrape.skipped` to resolve against instead of never having appeared.
    rel_img = img.relative_to(IA_DIR)
    await AgentClient().emit({
        "flow": "entity-scrape", "kind": "scrape.started",
        "entity": id, "subject": id, "image": str(rel_img),
    })

    while True:
        log.info(f"Scraping profile: @{id}")
        device.open_entity(entity)
        if ui.profile_id.wait(timeout=5):
            break
        elif not inet.is_active:
            await ensure_network(device)
        else:
            log.error(f"@{id}: Profile not found")
            await AgentClient().emit({
                "flow": "entity-scrape", "kind": "scrape.skipped",
                "entity": id, "subject": id, "image": str(rel_img), "reason": "NOT_FOUND",
            })
            return False

    # D68, corrected same-session from D64: checking only
    # `profile_tabs_container` treated every *legitimate PRIVATE* profile as
    # "unavailable" too, since a private profile's page never has tabs
    # either (it shows a lock/banner instead) - PRIVATE is scrape's own
    # dominant, expected case (`elif user.access == PUBLIC: skip` below
    # exists precisely because scrape only wants PRIVATE), so this broke
    # real scraping outright, not just guarded against a rare edge case.
    # `_profile_entity_access` already implements the full three-way check
    # (PRIVATE banner / PUBLIC tabs / neither == genuinely unavailable) -
    # reused here instead of re-deriving a partial version of the same
    # logic, and its result is carried forward so the access check below
    # doesn't redundantly re-run the same wait a second time.
    access = device._profile_entity_access(timeout=15)
    if access is None:
        # The app bar can still show a username for a disabled/unavailable
        # profile (that's all `profile_id.wait` above checks), but none of
        # `User.from_ui`'s post/follower/following elements exist on that
        # page - previously an uncaught crash there, retried 3x by @ia_task,
        # then a hard failure that aborted every other queued profile in
        # this run too.
        log.error(f"@{id}: profile page loaded but has no content (disabled/unavailable?)")
        await AgentClient().emit({
            "flow": "entity-scrape", "kind": "scrape.skipped",
            "entity": id, "subject": id, "image": str(rel_img), "reason": "UNAVAILABLE",
        })
        return False

    user = User.from_ui(ui, session)
    user.access = access
    user.update(session)

    if user.access == EntityAccess.PUBLIC:
        log.error(
            f"@{id} access is found out to be: {EntityAccess.PUBLIC.upper()}. Skipping scrape."
        )
        await AgentClient().emit({
            "flow": "entity-scrape", "kind": "scrape.skipped",
            "entity": id, "subject": id, "image": str(rel_img), "reason": "PUBLIC",
        })
        return False
    elif user.p == 0 and (year := device.determine_year_joined()) is not None and year < 5:
        log.error(f"@{id} has zero posts. Skipping scrape.")
        await AgentClient().emit({
            "flow": "entity-scrape", "kind": "scrape.skipped",
            "entity": id, "subject": id, "image": str(rel_img), "reason": "NO_POSTS",
        })
        return False
    elif (_min := min(user.f1, user.f2)) < Limit.get("FMIN"):
        log.error(f"@{id} has {_min} < {Limit.get('FMIN')} followers. Skipping scrape.")
        await AgentClient().emit({
            "flow": "entity-scrape", "kind": "scrape.skipped",
            "entity": id, "subject": id, "image": str(rel_img),
            "reason": f"f={_min} < FMIN={Limit.get('FMIN')}",
        })
        return False
    elif user.f1 > Limit.get("FMAX"):
        log.error(
            f"@{id} has {user.f1} > {Limit.get('FMAX')} followers. Skipping scrape."
        )
        await AgentClient().emit({
            "flow": "entity-scrape", "kind": "scrape.skipped",
            "entity": id, "subject": id, "image": str(rel_img),
            "reason": f"f={user.f1} > FMAX={Limit.get('FMAX')}",
        })
        return False

    if user.p == 0:
        # determine_year_joined() only returns to the profile page on its own
        # success path - on any exception (caught, returns None) it can leave
        # the device mid-navigation (options menu / about page), which would
        # break the profile screenshot below.
        device.open_entity(entity)

    profile_page = ui.profile_page.screenshot()
    crop_height = int(ui.profile_follow_button.center()[-1])
    profile_header = profile_page.crop((0, 0, profile_page.width, crop_height))
    width, height = profile_header.size

    dp = ui.profile_avatar_small.screenshot()
    dp_try = 0
    while dp_try <= 3:
        dp_try += 1
        ui.profile_avatar.long_click()
        await asyncio.sleep(1)
        if ui.profile_avatar_expanded.wait(timeout=5):
            dp = ui.profile_avatar_expanded.screenshot()
            break
    dp_resized = dp.resize((width, width), Image.Resampling.LANCZOS)
    height += dp_resized.height

    profile_report = Image.new("RGB", (width, height))
    profile_report.paste(dp_resized)
    profile_report.paste(profile_header, (0, dp_resized.height))

    output = SCRAPED_DIR / img.relative_to(SCRAPE_QUEUE_DIR)
    output.parent.mkdir(exist_ok=True, parents=True)
    profile_report.save(output)
    rel_output = output.relative_to(IA_DIR)
    log.info(f"Scrape exported to {rel_output}")
    await AgentClient().emit({
        "flow": "entity-scrape", "kind": "scrape.done",
        "entity": id, "subject": id, "image": str(rel_output),
        "counters": {"posts": user.p, "followers": user.f1, "following": user.f2},
    })

    device.press("back")
    await asyncio.sleep(buffer)

    return output


@ia_task()
async def profile_follow(
    img: Path,
    buffer: float = 5,
    device: IaDevice | None = None,
    session: Session | None = None,
    tl: IaTelegram | None = None,
) -> bool:
    log = get_run_logger()
    device = device or IaDevice()
    session = session or IaSession()
    tl = tl or await IaTelegram.get_client()
    ui = device.ui
    id = img.stem
    inet = Internet()

    await ensure_network(device)
    entity = Entity.from_id(id)

    # Same reasoning as `profile_scrape`'s emit above: fires the instant the
    # attempt is triggered, not once the profile page actually loads, so a
    # not-found profile still gets a `follow.attempt` for its `follow.result`
    # to resolve against instead of leaving no trace at all.
    rel_img = img.relative_to(IA_DIR)
    await AgentClient().emit({
        "flow": "entity-follow", "kind": "follow.attempt",
        "entity": id, "subject": id, "image": str(rel_img),
    })

    while True:
        log.info(f"Following profile: @{id}")
        device.open_entity(entity)
        if ui.profile_id.wait(timeout=5):
            break
        elif not inet.is_active:
            await ensure_network(device)
        else:
            log.error(f"@{id}: Profile not found")
            await AgentClient().emit({
                "flow": "entity-follow", "kind": "follow.result",
                "entity": id, "subject": id, "image": str(rel_img),
                "verdict": "FAILED", "reason": "NOT_FOUND",
            })
            return False

    if device._profile_entity_access() == EntityAccess.PUBLIC:
        log.error(
            f"@{id} access is found out to be: {EntityAccess.PUBLIC.upper()}. Skipping Follow."
        )
        await AgentClient().emit({
            "flow": "entity-follow", "kind": "follow.result",
            "entity": id, "subject": id, "image": str(rel_img),
            "verdict": "FAILED", "reason": "PUBLIC",
        })
        return False

    if ui.followed_by.exists:
        # "Followed by test_user_123" -> "Followed by @test_user_123" - purely
        # cosmetic, to match the "@entity" styling of the link just before it
        # (the followed-by name itself is never a link, just visually
        # consistent with one). Only the first name gets the "@" on Instagram's
        # own "Followed by X and 3 others" multi-name phrasing - acceptable
        # since this is display polish, not a second link target.
        followed_text = re.sub(r"^(Followed by )(\S)", r"\1@\2", ui.followed_by.get_text())
        msg = f"**[@{entity.id}]({entity.url})** is {followed_text}"
        log.error(msg)
        await notify(
            msg, image=img, level="warn", tags=("follow",), tl=tl,
            url=entity.url, always_telegram=True,
        )
        await AgentClient().emit({
            "flow": "entity-follow", "kind": "follow.result",
            "entity": id, "subject": id, "image": str(rel_img), "verdict": "FOLLOWED_BY",
        })
        return False

    if ui.wants_to_follow.exists:
        log.error(f"@{id} already wants to follow you.")
        await AgentClient().emit({
            "flow": "entity-follow", "kind": "follow.result",
            "entity": id, "subject": id, "image": str(rel_img), "verdict": "WANTS_TO_FOLLOW",
        })
        return False

    if ui.profile_follow_button.wait(timeout=5):
        current = ui.profile_follow_button.get_text()
        match current:
            case EntityRequest.FOLLOW:
                ui.profile_follow_action_button.click_gone()
                log.info(f"@{id} follow successful.")
                status = True
                verdict, reason = "FOLLOWED", None
            case EntityRequest.REQUESTED | EntityRequest.FOLLOWING:
                log.warning(
                    f"@{id} profile request status is already: {current.upper()}"
                )
                status = False
                verdict, reason = current.upper(), None
            case _:
                log.error(f"@{id} profile unknown status: {current.upper()}")
                status = False
                verdict, reason = "FAILED", f"unknown status: {current}"
    else:
        log.error(f"@{id} follow failed.")
        status = False
        verdict, reason = "FAILED", "follow button not found"

    await AgentClient().emit({
        "flow": "entity-follow", "kind": "follow.result",
        "entity": id, "subject": id, "image": str(rel_img),
        "verdict": verdict, "reason": reason,
    })

    await asyncio.sleep(buffer)
    return status
