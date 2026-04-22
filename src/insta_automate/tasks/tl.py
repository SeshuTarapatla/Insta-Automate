from datetime import date

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.models.entity import Entity
from insta_automate.tasks import ia_task


@ia_task()
async def notify_unfollow(entity: Entity):
    tl = await IaTelegram.get_client()
    device = IaDevice()
    ui = device.ui
    if not ui.profile_header.exists:
        device.open_entity(entity)
        ui.profile_header.must_wait()
    image = ui.image(ui.profile_header.screenshot(), name=entity.id)
    return await tl.bot.notify(
        f"Scan complete. You can now unfollow **[@{entity.id}]({entity.url})**",
        file=image,
    )


@ia_task()
async def notify_scan_limit(dt: date, type: str, value: int):
    tl = await IaTelegram.get_client()
    await tl.bot.notify(f"Scan limit reached for **{dt}**. {type.upper()}: {value}")
