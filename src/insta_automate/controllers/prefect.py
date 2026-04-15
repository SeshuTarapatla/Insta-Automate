import asyncio
from typing import cast

from my_modules.helpers import handle_await
from my_modules.logger import get_logger
from prefect import get_client
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterDeploymentId,
    FlowRunFilterState,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import FlowRun, StateType
from prefect.deployments import run_deployment
from telethon.events import NewMessage
from telethon.types import Message

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.models.telegram import IaMessages

log = get_logger(__name__)


class Prefect:
    def __init__(self) -> None:
        self.tl = IaTelegram()
        self.device_connected: bool = False
        self.entity_ingest = Deployment("entity-ingest")

    async def wait_for_device(self):
        notification: Message = cast(Message, None)
        while not IaDevice.connected():
            if notification is None:
                log.error(IaMessages.DEVICE_DISCONNECTED)
                notification = await self.tl.bot.notify(IaMessages.DEVICE_DISCONNECTED)
            await asyncio.sleep(1)
        self.device_connected = True
        log.info(IaMessages.DEVICE_CONNECTED)
        if notification is not None:
            await self.tl.bot.notify(IaMessages.DEVICE_CONNECTED, transient=True)
            await self.tl.purge_adb_notifications()
        self.device = IaDevice()
        self.device.app_restart()

    async def entity_ingest_trigger(self):
        await self.entity_ingest.trigger()
        log.info("Entity flow run complete. Restarting telegram session.")
        await self.tl.start()

    async def serve(self):
        await self.tl.start()
        await self.wait_for_device()

        @self.tl.on(NewMessage(chats=self.tl.entity_channel))
        async def new_entity_message(event: NewMessage.Event):
            log.info(f"New Entity received: [green]{event.message.text}[/]")
            asyncio.create_task(self.entity_ingest_trigger())

        log.info("Server started!!")
        await handle_await(self.tl.run_until_disconnected())


class Deployment:
    ACTIVE_STATES = [
        StateType.RUNNING,
        StateType.PENDING,
        StateType.SCHEDULED,
    ]

    TERMINAL_STATES = {
        StateType.COMPLETED,
        StateType.FAILED,
        StateType.CANCELLED,
        StateType.CRASHED,
    }

    def __init__(self, flow: str) -> None:
        self.flow = flow
        self._deployment_name = f"{flow}/{flow}"

    async def is_running(self) -> bool:
        async with get_client() as client:
            deployment = await client.read_deployment_by_name(self._deployment_name)

            active_runs = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    state=FlowRunFilterState(
                        type=FlowRunFilterStateType(any_=Deployment.ACTIVE_STATES)
                    ),
                    deployment_id=FlowRunFilterDeploymentId(any_=[deployment.id]),
                ),
                limit=1,
            )

            return len(active_runs) > 0

    async def trigger(
        self,
        concurrent: bool = False,
        wait: bool = True,
        poll_interval: int = 5,
    ):
        if not concurrent and await self.is_running():
            log.warning(f"Skipping: '{self._deployment_name}' is already active.")
            return None

        flow_run = cast(
            FlowRun,
            await handle_await(
                run_deployment(
                    name=self._deployment_name,
                    timeout=0,
                )
            ),
        )

        log.info(f"Triggered flow run: {flow_run.id}")

        if wait:
            return await self._wait_for_completion(
                flow_run.id,
                poll_interval,
            )

        return flow_run

    async def _wait_for_completion(
        self,
        flow_run_id,
        poll_interval: int,
    ):
        async with get_client() as client:
            while True:
                run = await client.read_flow_run(flow_run_id)

                state_type = run.state.type  # type: ignore

                if state_type in Deployment.TERMINAL_STATES:
                    log.info(f"Flow run finished with state: {state_type.name}")
                    return run

                await asyncio.sleep(poll_interval)
