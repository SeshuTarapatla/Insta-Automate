import asyncio
from datetime import date, datetime, timedelta
from inspect import isawaitable
from typing import Any, cast

from dotenv import get_key
from my_modules.datetime_utils import Timestamp
from my_modules.helpers import handle_await
from my_modules.inet import Internet
from my_modules.logger import get_logger
from prefect import State
from prefect.client.schemas.objects import FlowRun, StateType
from prefect.deployments import run_deployment
from prefect.flow_runs import wait_for_flow_run
from telethon.events import NewMessage

from insta_automate.controllers.agent import AgentClient
from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.postgres import IaSession
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.models.entity import Entity
from insta_automate.models.follow import Follow
from insta_automate.models.meta import Config
from insta_automate.models.scan import Scan
from insta_automate.models.scrape import Scrape
from insta_automate.tasks.device import wait_for_device
from insta_automate.utils import jpegs
from insta_automate.vars import (
    CONFIG,
    FOLLOW_QUEUE_DIR,
    SCANNED_DIR,
    SCRAPED_DIR,
)

log = get_logger(__name__)


def _gate(ok: bool, reason: str | None = None, detail: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "reason": reason, "detail": detail}


class Deployment:
    def __init__(self, flow: str, deployment: str | None = None) -> None:
        self.flow = flow
        self.deployment = f"{deployment or flow}/{flow}"
        self._switch = self.flow.upper().replace("-", "_")

    def __repr__(self) -> str:
        return f"Deployment('{self.deployment}')"

    def __str__(self) -> str:
        return self.__repr__()

    def switch(self) -> bool:
        return get_key(CONFIG, self._switch) != "0"

    async def trigger(
        self,
        wait: bool = True,
        parameters: dict[str, Any] = {},
        retries: int = 3,
        force: bool = False,
    ) -> FlowRun | None:
        if not self.switch() and not force:
            log.warning(f"Flow switch `{self._switch}` is OFF. Skipping trigger.")
            return
        if force and not self.switch():
            log.warning(f"Flow switch `{self._switch}` is OFF, but forcing the trigger anyway.")
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
        self.session = IaSession()
        self.inet = Internet()
        self.agent = AgentClient()

        self.device: IaDevice = cast(IaDevice, None)

        self.entity_ingest = Deployment("entity-ingest")
        self.entity_scan = Deployment("entity-scan")
        self.entity_classify = Deployment("entity-classify")
        self.entity_scrape = Deployment("entity-scrape")
        self.entity_follow = Deployment("entity-follow")
        self.entity_ingest_queued: bool = False

        # Fed by the trigger loops, drained by heartbeat_loop() into the agent
        # every ~2s (ARCHITECTURE §4.3). Keyed by flow name; each loop only
        # ever sets its own key, so no lock is needed across a single event
        # loop the way ManagedService needs one across threads.
        self.flow_state: dict[str, dict[str, Any]] = {}

        # Commands queued by the agent (ARCHITECTURE §4.4), drained into here
        # by heartbeat_loop() and consumed by wait_until()/the trigger loops.
        # Same no-lock reasoning as flow_state - single event loop, each
        # flow's list is only ever appended to (heartbeat_loop) or popped
        # from (that flow's own loop).
        self._commands: dict[str, list[str]] = {}

    def _set_state(self, flow: str, **fields: Any) -> None:
        state = self.flow_state.setdefault(flow, {"flow": flow})
        state.update(fields)

    def _consume(self, flow: str, command: str) -> bool:
        pending = self._commands.get(flow)
        if pending and command in pending:
            pending.remove(command)
            return True
        return False

    def _pending(self, flow: str, command: str) -> bool:
        return command in self._commands.get(flow, [])

    def _trigger_gate(self, force: bool) -> dict[str, Any]:
        if force:
            return _gate(True, "forced", "triggered via Force run, bypassing the gate")
        return _gate(True)

    async def ping_telegram(self):
        log.info("Pinging telegram to keep session alive.")
        await self.tl.start()

    async def keep_telegram_alive(self):
        while True:
            await self.wait_until("telegram-keepalive", "TG_KEEPALIVE_WAIT")
            await self.ping_telegram()

    async def wait_day_change(self, date: date, flow: str | None = None):
        if flow:
            next_midnight = datetime.combine(date + timedelta(days=1), datetime.min.time())
            self._set_state(
                flow,
                phase="day_paused",
                next_trigger_at=next_midnight.isoformat(),
                gate=_gate(False, "day_limit", f"{flow} limit reached for {date}"),
            )
        while date == Timestamp().date():
            # Peeked, not consumed: consuming here would burn the command
            # without ever reaching the trigger branch. The outer loop's
            # `continue` re-enters the top of the trigger loop, where the
            # real `_consume` picks it up and actually bypasses the gate.
            if flow and self._pending(flow, "force_run"):
                return
            await asyncio.sleep(Config.get("DAY_CHANGE_POLL"))

    async def wait_until(self, flow: str, key: str) -> str:
        """Sleep in Config.get("TICK") increments, re-reading Config.get(key)
        every tick so an edited delay re-targets the deadline live. Returns
        the wake reason - "elapsed", or one of "skip_wait"/"run_now"/
        "reload_config" if that command arrived while waiting (ARCHITECTURE
        §4.4) - all three just mean "re-evaluate now instead of at the
        deadline", so they share one interrupt.

        Only touches `phase`/`next_trigger_at` in flow_state, never `gate` -
        the caller sets the gate once, right before calling this, and it
        should keep reading true for the whole wait rather than being
        clobbered by "ok" on the first tick."""
        if target := Config.get(key):
            log.info(f"{flow}: waiting {target}s ({key}) before next trigger.")
        elapsed = 0.0
        while elapsed < (target := Config.get(key)):
            tick = min(Config.get("TICK"), target - elapsed)
            deadline = datetime.now() + timedelta(seconds=target - elapsed)
            self._set_state(flow, phase="waiting", next_trigger_at=deadline.isoformat())
            await asyncio.sleep(tick)
            elapsed += tick
            for wake in ("skip_wait", "run_now", "reload_config"):
                if self._consume(flow, wake):
                    return wake
        return "elapsed"

    async def entity_ingest_trigger(self, force: bool = False):
        if self.entity_ingest_queued:
            log.warning(
                "Entity ingest flow is already in queue. Skipping this trigger."
            )
        else:
            self.entity_ingest_queued = True
            log.info("New entities found to ingest.")
            self.inet.wait_for_network()
            await self.entity_ingest.trigger(force=force)
            await self.ping_telegram()
            self.entity_ingest_queued = False

    async def entity_ingest_time_trigger(self):
        while True:
            force = self._consume("entity-ingest", "force_run")
            if await self.tl.entities_exist or force:
                self._set_state("entity-ingest", phase="triggering", gate=self._trigger_gate(force))
                await self.entity_ingest_trigger(force=force)
            else:
                self._set_state(
                    "entity-ingest", gate=_gate(False, "no_work", "no new entities in the channel")
                )
            await self.wait_until("entity-ingest", "INGEST_POLL_WAIT")

    async def entity_classify_trigger(self):
        while True:
            force = self._consume("entity-classify", "force_run")
            if jpegs(SCANNED_DIR) or force:
                log.info("Scanned entities found to classify.")
                self._set_state("entity-classify", phase="triggering", gate=self._trigger_gate(force))
                await self.entity_classify.trigger(force=force)
                await self.ping_telegram()
            else:
                self._set_state(
                    "entity-classify", gate=_gate(False, "no_work", "nothing in scanned/ to classify")
                )
            await self.wait_until("entity-classify", "CLASSIFY_POLL_WAIT")

    async def entity_scan_trigger(self):
        while True:
            scan = Scan.fetch(self.session)
            force = self._consume("entity-scan", "force_run")
            if scan.limit_reached and not force:
                log.info(
                    "Scan limit reached for the day. Pausing trigger until next day."
                )
                await self.wait_day_change(Timestamp().date(), flow="entity-scan")
                continue
            if entities := Entity.fetch_queued_entities(self.session):
                self._set_state("entity-scan", phase="triggering", gate=self._trigger_gate(force))
                self.inet.wait_for_network()
                await wait_for_device(self.tl)
                log.info(f"Total entities queued for scan: {len(entities)}")
                log.info(
                    f"Trigerring scan for:\n{entities[0].model_dump_json(indent=4)}"
                )
                await self.entity_scan.trigger(parameters={"url": entities[0].url}, force=force)
                await self.wait_until("entity-scan", "SCAN_WAIT")
            else:
                self._set_state(
                    "entity-scan", gate=_gate(False, "no_work", "no queued entities")
                )
            await self.wait_until("entity-scan", "SCAN_POLL_WAIT")

    async def entity_scrape_trigger(self):
        while True:
            scrape = Scrape.fetch(self.session)
            force = self._consume("entity-scrape", "force_run")
            if scrape.limit_reached and not force:
                log.info(
                    "Scrape limit reached for the day. Pausing trigger until next day."
                )
                await self.wait_day_change(Timestamp().date(), flow="entity-scrape")
                continue
            backpressure = Config.get("FOLLOW") * Config.get("SCRAPE_BACKPRESSURE_FACTOR")
            count = len(jpegs(SCRAPED_DIR) + jpegs(FOLLOW_QUEUE_DIR))
            if count < backpressure or force:
                self._set_state("entity-scrape", phase="triggering", gate=self._trigger_gate(force))
                await wait_for_device(self.tl)
                log.info("Queued entities are requested to scrape.")
                await self.entity_scrape.trigger(force=force)
                await self.ping_telegram()
                await self.wait_until("entity-scrape", "SCRAPE_WAIT")
            else:
                self._set_state(
                    "entity-scrape",
                    gate=_gate(
                        False,
                        "backpressure",
                        f"scraped+follow_queued = {count} ≥ FOLLOW×"
                        f"{Config.get('SCRAPE_BACKPRESSURE_FACTOR')} = {backpressure}",
                    ),
                )
            await self.wait_until("entity-scrape", "SCRAPE_BUFFER")

    async def entity_follow_trigger(self):
        while True:
            follow = Follow.fetch(self.session)
            force = self._consume("entity-follow", "force_run")
            if follow.limit_reached and not force:
                log.info(
                    "Follow limit reached for the day. Pausing trigger until next day."
                )
                await self.wait_day_change(Timestamp().date(), flow="entity-follow")
                continue
            if jpegs(FOLLOW_QUEUE_DIR):
                self._set_state("entity-follow", phase="triggering", gate=self._trigger_gate(force))
                await wait_for_device(self.tl)
                log.info("Queued entities found to follow.")
                await self.entity_follow.trigger(force=force)
                await self.ping_telegram()
                await self.wait_until("entity-follow", "FOLLOW_WAIT")
            else:
                self._set_state(
                    "entity-follow", gate=_gate(False, "no_work", "nothing in follow_queued/")
                )
            await self.wait_until("entity-follow", "FOLLOW_BUFFER")

    # ------------------------------------------------------------- heartbeat

    def _today(self, flow: str) -> dict[str, int] | None:
        match flow:
            case "entity-scan":
                scan = Scan.fetch(self.session)
                return {
                    "profiles": scan.profiles, "profiles_limit": Config.get("PROFILES"),
                    "reels": scan.reels, "reels_limit": Config.get("REELS"),
                    "posts": scan.posts, "posts_limit": Config.get("POSTS"),
                }
            case "entity-scrape":
                scrape = Scrape.fetch(self.session)
                return {"scraped": scrape.scraped, "limit": Config.get("SCRAPE")}
            case "entity-follow":
                follow = Follow.fetch(self.session)
                return {"followed": follow.followed, "limit": Config.get("FOLLOW")}
            case _:
                # entity-ingest and entity-classify have no daily cap.
                return None

    def _last_run(self, deployment: Deployment) -> dict[str, Any] | None:
        flow_run = getattr(deployment, "flow_run", None)
        if flow_run is None:
            return None
        state = getattr(flow_run, "state", None)
        state_type = getattr(state, "type", None)
        duration = getattr(flow_run, "total_run_time", None)
        return {
            "id": str(flow_run.id),
            "state": state_type.value if state_type else "UNKNOWN",
            "duration_s": duration.total_seconds() if hasattr(duration, "total_seconds") else None,
        }

    async def heartbeat_loop(self, wait: float = 2.0):
        """Every flow's state block (ARCHITECTURE §4.3), posted to the agent
        so /api/scheduler has something real to mirror (CP 3.4, D27). Queued
        commands (§4.4) are drained into self._commands here and consumed by
        wait_until()/the trigger loops (CP 3.5)."""
        deployments = {
            "entity-ingest": self.entity_ingest,
            "entity-scan": self.entity_scan,
            "entity-classify": self.entity_classify,
            "entity-scrape": self.entity_scrape,
            "entity-follow": self.entity_follow,
        }
        while True:
            for flow, deployment in deployments.items():
                state = dict(self.flow_state.get(flow, {"flow": flow}))
                state["switch"] = deployment.switch()
                state["today"] = self._today(flow)
                state["last_run"] = self._last_run(deployment)
                state.setdefault("phase", "idle")
                state.setdefault("gate", _gate(True))
                state.setdefault("next_trigger_at", None)
                commands = await self.agent.heartbeat(state)
                for entry in commands:
                    name = entry.get("command") if isinstance(entry, dict) else entry
                    if name:
                        self._commands.setdefault(flow, []).append(name)
                        log.info(f"{flow}: queued command '{name}'")
            await asyncio.sleep(wait)

    async def serve(self):
        await self.tl.start()
        self.device = await wait_for_device(self.tl)

        asyncio.create_task(self.keep_telegram_alive())
        asyncio.create_task(self.entity_ingest_time_trigger())
        asyncio.create_task(self.entity_scan_trigger())
        asyncio.create_task(self.entity_classify_trigger())
        asyncio.create_task(self.entity_scrape_trigger())
        asyncio.create_task(self.entity_follow_trigger())
        asyncio.create_task(self.heartbeat_loop())

        log.info("Insta Automate Scheduler and Trigerrer started!")

        @self.tl.on(NewMessage(chats=self.tl.entity_channel))
        async def entity_ingest_message_trigger(event: NewMessage.Event):
            await self.entity_ingest_trigger()

        await handle_await(self.tl.run_until_disconnected())
