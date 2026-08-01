import asyncio

from my_modules.inet import Internet
from my_modules.logger import get_logger
from prefect import get_run_logger

from typing import Literal

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.notify import notify
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.models.entity import Entity
from insta_automate.models.meta import EntityAccess
from insta_automate.models.telegram import IaMessages
from insta_automate.tasks import ia_task


@ia_task()
async def device_ready(tl: IaTelegram | None = None) -> IaDevice:
    device = await wait_for_device(tl)
    device.start_scrcpy()
    device.app_start()
    return device


@ia_task()
def switch_account(
    account: Literal["alt", "main"], device: IaDevice | None = None
) -> bool:
    log = get_run_logger()
    device = device or IaDevice()
    log.info(f"Switching to {account.upper()} account.")
    return device.switch_account(account)


@ia_task()
def switch_account_for_entity(entity: Entity, device: IaDevice | None = None) -> bool:
    account = "alt" if entity.access == EntityAccess.PUBLIC else "main"
    return switch_account(account, device)


@ia_task()
async def network_access(object: Internet | IaDevice | None = None):
    def wait_for_network():
        log.error("Internet disconnected. Awaiting for network...")
        wait_method()
        log.info("Internet is back. Network access active.")

    log = get_run_logger()
    object = object or Internet()
    if isinstance(object, Internet):
        wait_method = object.wait_for_network
        if not object.is_active:
            wait_for_network()
    elif isinstance(object, IaDevice):
        wait_method = object.wait_for_network
        if not object.inet.is_active:
            wait_for_network()


async def wait_for_device(tl: IaTelegram | None = None) -> IaDevice:
    log = get_logger(__name__)
    tl = tl or (await IaTelegram.get_client())
    notified = False
    while True:
        try:
            connected = IaDevice.connected()
        except Exception:
            # A transient adb server hiccup (e.g. a version-mismatched client
            # restarting it) raises here instead of just returning False -
            # treat it the same as "not connected yet" rather than letting it
            # propagate and kill whatever task is waiting on us.
            connected = False
        if connected:
            break
        if not notified:
            log.error(IaMessages.DEVICE_DISCONNECTED)
            await notify(IaMessages.DEVICE_DISCONNECTED, level="error", tags=("device",), tl=tl)
            notified = True
        await asyncio.sleep(1)
    log.info(IaMessages.DEVICE_CONNECTED)
    if notified:
        await notify(IaMessages.DEVICE_CONNECTED, transient=True, tags=("device",), tl=tl)
        await tl.purge_adb_notifications()
    device = IaDevice()
    device.start_scrcpy()
    device.sleep(1)
    device.lock()
    return device
