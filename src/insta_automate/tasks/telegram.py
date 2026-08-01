from datetime import date

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.notify import notify
from insta_automate.models.entity import Entity
from insta_automate.models.telegram import IaMessages
from insta_automate.tasks import ia_task


@ia_task()
async def notify_scan_limit_reached(dt: date, type: str, value: int):
    await notify(
        f"Scan limit reached for **{dt}**. {type.upper()}: {value}",
        level="warn",
        tags=("scan", "limit"),
    )


@ia_task()
async def notify_new_entities_classified():
    await notify(IaMessages.ENTITIES_CLASSIFIED, dedupe="entities.classified", tags=("classify",))


@ia_task()
async def notify_new_entities_scraped():
    await notify(IaMessages.ENTITIES_SCRAPED, dedupe="entities.scraped", tags=("scrape",))


@ia_task()
async def notify_profile_unfollow(entity: Entity):
    device = IaDevice()
    ui = device.ui
    if not ui.profile_header.exists:
        device.open_entity(entity)
        ui.profile_header.must_wait()
    image = ui.image(ui.profile_header.screenshot(), name=entity.id)
    return await notify(
        f"Scan complete. You can now unfollow **[@{entity.id}]({entity.url})**",
        image=image,
        tags=("scan", "unfollow"),
    )
