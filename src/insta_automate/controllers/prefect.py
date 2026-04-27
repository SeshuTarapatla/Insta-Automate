import asyncio
from inspect import isawaitable
from typing import Any, cast

from my_modules.datetime_utils import Timestamp
from my_modules.helpers import handle_await
from my_modules.inet import Internet
from my_modules.logger import get_logger
from prefect import State
from prefect.client.schemas.objects import FlowRun, StateType
from prefect.deployments import run_deployment
from prefect.flow_runs import wait_for_flow_run
from telethon.events import NewMessage
from telethon.types import Message
from datetime import date

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.postgres import SessionLocal
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.models.entity import Entity
from insta_automate.models.scan import Scan
from insta_automate.models.scrape import Scrape
from insta_automate.models.telegram import IaMessages
from insta_automate.vars import SCANNED_DIR, SCRAPE_QUEUE_DIR

log = get_logger(__name__)


class Deployment:
    def __init__(self, flow: str, deployment: str | None = None) -> None:
        self.flow = flow
        self.deployment = f"{deployment or flow}/{flow}"

    def __repr__(self) -> str:
        return f"Deployment('{self.deployment}')"

    def __str__(self) -> str:
        return self.__repr__()

    async def trigger(
        self, wait: bool = True, parameters: dict[str, Any] = {}, retries: int = 3
    ) -> FlowRun | None:
        attempt = 1
        while attempt <= retries:
            try:
                log.info(f"Triggering: {self} - attempt {attempt}")
                flow_run = run_deployment(
                    self.deployment, timeout=0, parameters=parameters
                )
                self.flow_run = await flow_run if isawaitable(flow_run) else flow_run
                log.info("Trigger successful.")
                if wait:
                    await self.log_status()
                else:
                    asyncio.create_task(self.log_status())
                return self.flow_run
            except Exception:
                log.error(f"Trigger attempt {attempt} failed. Retrying...")
                attempt += 1
        return None

    async def log_status(self) -> None:
        while True:
            try:
                self.flow_run = await wait_for_flow_run(self.flow_run.id)
                if isinstance(self.flow_run.state, State):
                    if self.flow_run.state.type == StateType.COMPLETED:
                        log.info(f"{self} run completed.")
                    else:
                        log.error(
                            f"{self} run failed with status: [bold red]{self.flow_run.state.type.value}[/]"
                        )
                else:
                    log.error(f"{self} run completed with UNKNOWN status.")
                return
            except Exception:
                pass


class Prefect:
    def __init__(self) -> None:
        self.tl = IaTelegram()
        self.session = SessionLocal()
        self.inet = Internet()

        self.device: IaDevice = cast(IaDevice, None)

        self.entity_ingest = Deployment("entity-ingest")
        self.entity_scan = Deployment("entity-scan")
        self.ai_classify = Deployment("ai-classify")
        self.entity_scrape = Deployment("entity-scrape")
        self.entity_ingest_queued: bool = False

    async def wait_for_device(self):
        notification: Message = cast(Message, None)
        while not IaDevice.connected():
            if notification is None:
                log.error(IaMessages.DEVICE_DISCONNECTED)
                notification = await self.tl.bot.notify(IaMessages.DEVICE_DISCONNECTED)
            await asyncio.sleep(1)
        log.info(IaMessages.DEVICE_CONNECTED)
        if notification is not None:
            await self.tl.bot.notify(IaMessages.DEVICE_CONNECTED, transient=True)
            await self.tl.purge_adb_notifications()
        self.device = self.device or IaDevice()
        self.device.start_scrcpy()
        self.device.sleep(1)
        self.device.lock()

    async def ping_telegram(self):
        log.info("Pinging telegram to keep session alive.")
        await self.tl.start()

    async def keep_telegram_alive(self, wait: float = 1800):
        while True:
            await asyncio.sleep(wait)
            await self.ping_telegram()

    async def wait_day_change(self, date: date):
        while date == Timestamp().date():
            await asyncio.sleep(60)

    async def entity_scan_trigger(self):
        while True:
            scan = Scan.fetch(self.session)
            if scan.limit_reached:
                log.info(
                    "Scan limit reached for the day. Pausing trigger until next day."
                )
                await self.wait_day_change(Timestamp().date())
            elif entities := Entity.fetch_queued_entities(self.session):
                log.info(f"Total entities queued for scan: {len(entities)}")
                log.info(
                    f"Trigerring scan for:\n{entities[0].model_dump_json(indent=4)}"
                )
                self.inet.wait_for_network()
                await self.entity_scan.trigger(parameters={"url": entities[0].url})
            await asyncio.sleep(10)

    async def entity_ingest_trigger(self):
        if self.entity_ingest_queued:
            log.warning(
                "Entity ingest flow is already in queue. Skipping this trigger."
            )
        else:
            self.entity_ingest_queued = True
            log.info("New entities found to ingest.")
            self.inet.wait_for_network()
            await self.entity_ingest.trigger()
            await self.ping_telegram()
            self.entity_ingest_queued = False

    async def entity_ingest_time_trigger(self, wait: float = 600):
        while True:
            if await self.tl.entities_exist:
                await self.entity_ingest_trigger()
            await asyncio.sleep(wait)

    async def ai_classify_trigger(self, wait: float = 10):
        while True:
            if list(SCANNED_DIR.glob("*.jpg")):
                log.info("Scanned entities found to classify.")
                await self.ai_classify.trigger()
                await self.ping_telegram()
            await asyncio.sleep(wait)

    async def entity_scrape_trigger(self, wait: float = 600):
        while True:
            scrape = Scrape.fetch(self.session)
            if scrape.limit_reached:
                log.info(
                    "Scrape limit reached for the day. Pausing trigger until next day."
                )
                await self.wait_day_change(Timestamp().date())
            elif list(SCRAPE_QUEUE_DIR.glob("*.jpg")):
                log.info("Queued entities found to scrape.")
                await self.entity_scrape.trigger()
                await self.ping_telegram()
            await asyncio.sleep(wait)

    async def serve(self):
        await self.tl.start()
        await self.wait_for_device()

        asyncio.create_task(self.keep_telegram_alive())
        asyncio.create_task(self.entity_ingest_time_trigger())
        asyncio.create_task(self.entity_scan_trigger())
        asyncio.create_task(self.ai_classify_trigger())
        asyncio.create_task(self.entity_scrape_trigger())

        log.info("Insta Automate Scheduler and Trigerrer started!")

        @self.tl.on(NewMessage(chats=self.tl.entity_channel))
        async def entity_ingest_message_trigger(event: NewMessage.Event):
            await self.entity_ingest_trigger()

        await handle_await(self.tl.run_until_disconnected())
