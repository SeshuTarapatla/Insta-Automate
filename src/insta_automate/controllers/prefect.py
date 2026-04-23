import asyncio
from inspect import isawaitable
from typing import Any, cast

from my_modules.helpers import handle_await
from my_modules.inet import Internet
from my_modules.logger import get_logger
from prefect import State
from prefect.client.schemas.objects import FlowRun, StateType
from prefect.deployments import run_deployment
from prefect.flow_runs import wait_for_flow_run
from telethon.events import NewMessage
from telethon.types import Message

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.postgres import SessionLocal
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.models.entity import Entity
from insta_automate.models.scan import Scan
from insta_automate.models.telegram import IaMessages
from insta_automate.vars import SCANNED_DIR

log = get_logger(__name__)


class Prefect:
    def __init__(self) -> None:
        self.tl = IaTelegram()
        self.session = SessionLocal()
        self.inet = Internet()

        self.device: IaDevice = cast(IaDevice, None)

        self.entity_ingest = Deployment("entity-ingest")
        self.entity_scan = Deployment("entity-scan")
        self.gender_classify = Deployment("gender-classify")

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

    async def ia_flows_trigger(self):
        while True:
            scan = Scan.fetch(self.session)
            try:
                if not scan.limit_reached and (
                    entities := Entity.fetch_queued_entities(self.session)
                ):
                    log.info(f"Total entities queued for scan: {len(entities)}")
                    log.info(
                        f"Trigerring scan for:\n{entities[0].model_dump_json(indent=4)}"
                    )
                    self.inet.wait_for_network()
                    await self.wait_for_device()
                    await self.entity_scan.trigger(parameters={"url": entities[0].url})
            except Exception as e:
                log.error(f"IA Flows trigger exception: {e}")
                self.session.rollback()
            await asyncio.sleep(10)

    async def ping_telegram(self):
        log.info("Pinging telegram to keep session alive.")
        await self.tl.start()

    async def keep_telegram_alive(self, wait: float = 1800):
        while True:
            await asyncio.sleep(wait)
            await self.ping_telegram()

    async def entity_ingest_trigger(self):
        log.info("New entities found to ingest.")
        self.inet.wait_for_network()
        await self.entity_ingest.trigger()
        await self.ping_telegram()

    async def entity_ingest_time_trigger(self, wait: float = 600):
        while True:
            if await self.tl.entities_exist:
                log.info("New scanned entities found to classify.")
                await self.entity_ingest_trigger()
            await asyncio.sleep(wait)

    async def gender_classify_trigger(self, wait: float = 10):
        while True:
            if list(SCANNED_DIR.glob("*.jpg")):
                await self.gender_classify.trigger()
            await asyncio.sleep(wait)

    async def serve(self):
        await self.tl.start()
        await self.wait_for_device()
        log.info("Insta Automate Scheduler and Trigerrer started!")

        asyncio.create_task(self.keep_telegram_alive())
        asyncio.create_task(self.entity_ingest_time_trigger())
        asyncio.create_task(self.gender_classify_trigger())
        asyncio.create_task(self.ia_flows_trigger())

        @self.tl.on(NewMessage(chats=self.tl.entity_channel))
        async def entity_ingest_message_trigger(event: NewMessage.Event):
            await self.entity_ingest_trigger()

        await handle_await(self.tl.run_until_disconnected())


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
