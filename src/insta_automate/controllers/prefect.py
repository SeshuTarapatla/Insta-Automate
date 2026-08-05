import asyncio
import contextvars
import logging
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
from insta_automate.models.meta import Config, EntityAccess, EntityType
from insta_automate.models.scan import Scan
from insta_automate.models.scrape import Scrape
from insta_automate.tasks.device import wait_for_device
from insta_automate.utils import jpegs
from insta_automate.vars import (
    CONFIG,
    FOLLOW_QUEUE_DIR,
    GENDER_INVALID_DIR,
    GENDER_VALID_DIR,
    SCANNED_DIR,
    SCRAPE_QUEUE_DIR,
    SCRAPED_DIR,
)

log = get_logger(__name__)

# Tags every log record emitted from within a trigger loop's own asyncio task
# with the flow it belongs to, so the agent's log tailer (flowruns.py) can
# route scheduler-pod lines to the right flow's log pane instead of
# broadcasting every line to every active run. Set once at the top of each
# `entity_*_trigger` loop below; each asyncio task gets its own copy of the
# contextvar, so `Deployment.trigger()`/`log_status()` calls made from inside
# a loop inherit the right tag with no changes needed there. Lines with no
# flow set (heartbeat_loop, keep_telegram_alive, startup) are left untagged.
_current_flow: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_flow", default=None)


class _FlowTagFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        flow = _current_flow.get()
        if flow:
            record.msg = f"[{flow}] {record.msg}"
        return True


log.addFilter(_FlowTagFilter())


def _gate(ok: bool, reason: str | None = None, detail: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "reason": reason, "detail": detail}


def _scan_reserve_gate(
    entities: list[Entity], force: bool
) -> tuple[Entity | None, int | None, int]:
    """Picks the first entity in `entities` (already priority-ordered by
    `Entity.entity_priority_order()`) that the backlog reserve doesn't block,
    so a public profile stuck over the cap can never hold up a private
    profile or REEL/POST queued behind it - `entity_priority_order()` sorts
    by access then type, which does *not* guarantee a never-gated entity
    sorts ahead of a gated one (a public REEL sorts *behind* a public
    PROFILE, same access tier), so checking only `entities[0]` would have
    let one stuck public profile block everything behind it forever. Only a
    public profile keeps feeding scanned/gender_invalid/gender_valid/
    scrape_queued indefinitely - a private profile can't be scanned for
    followers/following at all, and a REEL/POST's own likers list is a
    one-shot scan, not an ongoing backlog contributor - so anything else is
    picked immediately, before the (whole-library, not per-entity) count is
    even computed. Returns `(None, count, target)` if every queued entity is
    a gated public profile and the backlog is still over target."""
    target = Config.get("SCAN_RESERVE_TARGET")
    count = None
    for candidate in entities:
        gated = candidate.type == EntityType.PROFILE and candidate.access == EntityAccess.PUBLIC
        if not gated or force:
            return candidate, count, target
        if count is None:
            count = len(
                jpegs(SCANNED_DIR) + jpegs(GENDER_INVALID_DIR) + jpegs(GENDER_VALID_DIR) + jpegs(SCRAPE_QUEUE_DIR)
            )
        if count < target:
            return candidate, count, target
    return None, count, target


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

    def _trigger_gate(self, force: bool, reduce_reserve: bool = False) -> dict[str, Any]:
        if reduce_reserve:
            return _gate(
                True,
                "reduce_reserve",
                "triggered via Reduce reserve — draining scraped+follow_queued to the "
                "backpressure target",
            )
        if force:
            return _gate(True, "forced", "triggered via Trigger now, bypassing the gate")
        return _gate(True)

    async def ping_telegram(self):
        log.info("Pinging telegram to keep session alive.")
        await self.tl.start()

    async def keep_telegram_alive(self):
        while True:
            try:
                await self.wait_until("telegram-keepalive", "TG_KEEPALIVE_WAIT")
                await self.ping_telegram()
            except Exception:
                log.exception("telegram-keepalive: loop raised - recovering after a short wait.")
                await asyncio.sleep(Config.get("TICK"))

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
            if flow and (
                self._pending(flow, "force_run")
                or self._pending(flow, "reduce_reserve")
                or self._pending(flow, "reduce_reserve_unblock_scrape")
            ):
                return
            await asyncio.sleep(Config.get("DAY_CHANGE_POLL"))

    async def wait_until(self, flow: str, key: str) -> str:
        """Sleep in Config.get("TICK") increments, re-reading Config.get(key)
        every tick so an edited delay re-targets the deadline live. Returns
        the wake reason - "elapsed", one of "skip_wait"/"run_now"/
        "reload_config" if that command arrived while waiting (ARCHITECTURE
        §4.4, all three just mean "re-evaluate now instead of at the
        deadline"), or "force_run" if one is pending - peeked, not consumed,
        so the trigger loop's own `_consume` still sees it and actually
        bypasses the gate; this call just needs to stop sleeping through it.

        `next_trigger_at` is only recomputed when `key`'s value actually
        changes, not every tick - recomputing it from `datetime.now()` each
        tick still lands on (very nearly) the same instant, but not exactly,
        and the UI was reading each of those microsecond-different instants
        as a fresh deadline, resetting its countdown ring to full every TICK.
        Holding the same `deadline` object across unchanged ticks broadcasts
        the identical value until something real changes it.

        Only touches `phase`/`next_trigger_at` in flow_state, never `gate` -
        the caller sets the gate once, right before calling this, and it
        should keep reading true for the whole wait rather than being
        clobbered by "ok" on the first tick."""
        target = Config.get(key)
        if target:
            log.info(f"{flow}: waiting {target}s ({key}) before next trigger.")
        elapsed = 0.0
        deadline = datetime.now() + timedelta(seconds=target)
        while elapsed < target:
            tick = min(Config.get("TICK"), target - elapsed)
            self._set_state(flow, phase="waiting", next_trigger_at=deadline.isoformat())
            await asyncio.sleep(tick)
            elapsed += tick
            for wake in ("skip_wait", "run_now", "reload_config"):
                if self._consume(flow, wake):
                    return wake
            if self._pending(flow, "reduce_reserve") or self._pending(flow, "reduce_reserve_unblock_scrape"):
                return "reduce_reserve"
            if self._pending(flow, "force_run"):
                return "force_run"
            new_target = Config.get(key)
            if new_target != target:
                deadline = datetime.now() + timedelta(seconds=max(new_target - elapsed, 0.0))
                target = new_target
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
        _current_flow.set("entity-ingest")
        while True:
            try:
                force = self._consume("entity-ingest", "force_run")
                if await self.tl.entities_exist or force:
                    self._set_state("entity-ingest", phase="running", gate=self._trigger_gate(force))
                    await self.entity_ingest_trigger(force=force)
                else:
                    self._set_state(
                        "entity-ingest", gate=_gate(False, "no_work", "no new entities in the channel")
                    )
                await self.wait_until("entity-ingest", "INGEST_POLL_WAIT")
            except Exception:
                log.exception("entity-ingest: trigger loop raised - recovering after a short wait.")
                self._set_state(
                    "entity-ingest", gate=_gate(False, "error", "trigger loop raised - see scheduler logs")
                )
                await asyncio.sleep(Config.get("TICK"))

    async def entity_classify_trigger(self):
        _current_flow.set("entity-classify")
        while True:
            try:
                force = self._consume("entity-classify", "force_run")
                if jpegs(SCANNED_DIR) or force:
                    log.info("Scanned entities found to classify.")
                    self._set_state("entity-classify", phase="running", gate=self._trigger_gate(force))
                    await self.entity_classify.trigger(force=force)
                    await self.ping_telegram()
                else:
                    self._set_state(
                        "entity-classify", gate=_gate(False, "no_work", "nothing in scanned/ to classify")
                    )
                await self.wait_until("entity-classify", "CLASSIFY_POLL_WAIT")
            except Exception:
                log.exception("entity-classify: trigger loop raised - recovering after a short wait.")
                self._set_state(
                    "entity-classify", gate=_gate(False, "error", "trigger loop raised - see scheduler logs")
                )
                await asyncio.sleep(Config.get("TICK"))

    async def entity_scan_trigger(self):
        _current_flow.set("entity-scan")
        while True:
            try:
                scan = Scan.fetch(self.session)
                force = self._consume("entity-scan", "force_run")
                if scan.limit_reached and not force:
                    log.info(
                        "Scan limit reached for the day. Pausing trigger until next day."
                    )
                    await self.wait_day_change(Timestamp().date(), flow="entity-scan")
                    continue
                if entities := Entity.fetch_queued_entities(self.session):
                    subject, count, target = _scan_reserve_gate(entities, force)
                    if subject is not None:
                        self._set_state("entity-scan", phase="running", gate=self._trigger_gate(force))
                        self.inet.wait_for_network()
                        await wait_for_device(self.tl)
                        log.info(f"Total entities queued for scan: {len(entities)}")
                        log.info(
                            f"Trigerring scan for:\n{subject.model_dump_json(indent=4)}"
                        )
                        await self.entity_scan.trigger(parameters={"url": subject.url}, force=force)
                        self._set_state(
                            "entity-scan",
                            gate=_gate(True, "cooldown", f"ran — next run allowed in up to {Config.get('SCAN_WAIT')}s"),
                        )
                        await self.wait_until("entity-scan", "SCAN_WAIT")
                    else:
                        self._set_state(
                            "entity-scan",
                            gate=_gate(
                                False,
                                "backpressure",
                                f"scanned+gender_invalid+gender_valid+scrape_queued = {count} ≥ "
                                f"SCAN_RESERVE_TARGET = {target} (every queued entity is a public profile)",
                            ),
                        )
                else:
                    self._set_state(
                        "entity-scan", gate=_gate(False, "no_work", "no queued entities")
                    )
                await self.wait_until("entity-scan", "SCAN_POLL_WAIT")
            except Exception:
                log.exception("entity-scan: trigger loop raised - recovering after a short wait.")
                self._set_state(
                    "entity-scan", gate=_gate(False, "error", "trigger loop raised - see scheduler logs")
                )
                await asyncio.sleep(Config.get("TICK"))

    async def entity_scrape_trigger(self):
        _current_flow.set("entity-scrape")
        while True:
            try:
                scrape = Scrape.fetch(self.session)
                force = self._consume("entity-scrape", "force_run")
                if scrape.limit_reached and not force:
                    log.info(
                        "Scrape limit reached for the day. Pausing trigger until next day."
                    )
                    await self.wait_day_change(Timestamp().date(), flow="entity-scrape")
                    continue
                backpressure = Config.get("FOLLOW") * Config.get("SCRAPE_RESERVE_FACTOR")
                count = len(jpegs(SCRAPED_DIR) + jpegs(FOLLOW_QUEUE_DIR))
                if count < backpressure or force:
                    self._set_state("entity-scrape", phase="running", gate=self._trigger_gate(force))
                    await wait_for_device(self.tl)
                    log.info("Queued entities are requested to scrape.")
                    await self.entity_scrape.trigger(parameters={"force": force}, force=force)
                    await self.ping_telegram()
                    self._set_state(
                        "entity-scrape",
                        gate=_gate(
                            True, "cooldown", f"ran — next run allowed in up to {Config.get('SCRAPE_WAIT')}s"
                        ),
                    )
                    await self.wait_until("entity-scrape", "SCRAPE_WAIT")
                else:
                    self._set_state(
                        "entity-scrape",
                        gate=_gate(
                            False,
                            "backpressure",
                            f"scraped+follow_queued = {count} ≥ FOLLOW×"
                            f"{Config.get('SCRAPE_RESERVE_FACTOR')} = {backpressure}",
                        ),
                    )
                await self.wait_until("entity-scrape", "SCRAPE_BUFFER")
            except Exception:
                log.exception("entity-scrape: trigger loop raised - recovering after a short wait.")
                self._set_state(
                    "entity-scrape", gate=_gate(False, "error", "trigger loop raised - see scheduler logs")
                )
                await asyncio.sleep(Config.get("TICK"))

    async def entity_follow_trigger(self):
        _current_flow.set("entity-follow")
        while True:
            try:
                follow = Follow.fetch(self.session)
                unblock_scrape = self._consume("entity-follow", "reduce_reserve_unblock_scrape")
                reduce_reserve = self._consume("entity-follow", "reduce_reserve") or unblock_scrape
                force = self._consume("entity-follow", "force_run") or reduce_reserve
                if follow.limit_reached and not force:
                    log.info(
                        "Follow limit reached for the day. Pausing trigger until next day."
                    )
                    await self.wait_day_change(Timestamp().date(), flow="entity-follow")
                    continue
                if jpegs(FOLLOW_QUEUE_DIR):
                    self._set_state(
                        "entity-follow", phase="running", gate=self._trigger_gate(force, reduce_reserve)
                    )
                    await wait_for_device(self.tl)
                    log.info("Queued entities found to follow.")
                    await self.entity_follow.trigger(
                        parameters={
                            "force": force,
                            "reduce_reserve": reduce_reserve,
                            "unblock_scrape": unblock_scrape,
                        },
                        force=force,
                    )
                    await self.ping_telegram()
                    self._set_state(
                        "entity-follow",
                        gate=_gate(
                            True, "cooldown", f"ran — next run allowed in up to {Config.get('FOLLOW_WAIT')}s"
                        ),
                    )
                    await self.wait_until("entity-follow", "FOLLOW_WAIT")
                else:
                    self._set_state(
                        "entity-follow", gate=_gate(False, "no_work", "nothing in follow_queued/")
                    )
                await self.wait_until("entity-follow", "FOLLOW_BUFFER")
            except Exception:
                log.exception("entity-follow: trigger loop raised - recovering after a short wait.")
                self._set_state(
                    "entity-follow", gate=_gate(False, "error", "trigger loop raised - see scheduler logs")
                )
                await asyncio.sleep(Config.get("TICK"))

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
            # Unlike every other trigger, this one fires from Telethon's own
            # event dispatch, not from entity_ingest_time_trigger()'s loop -
            # so it never went through that loop's `_set_state(...,
            # phase="running", ...)` call. The flow itself ran correctly
            # (that loop's own polling would eventually pick up the same
            # work anyway), but the scheduler snapshot never showed
            # entity-ingest as "running" for a message-triggered run,
            # invisible to anything reading phase (D66) - found by the
            # control center's Live screen never auto-following an
            # ingest-by-channel-post trigger, only the polling-triggered
            # ones.
            _current_flow.set("entity-ingest")
            self._set_state(
                "entity-ingest", phase="running",
                gate=_gate(True, "message", "triggered by a new channel post"),
            )
            await self.entity_ingest_trigger()
            self._set_state("entity-ingest", phase="idle")
            # This path never touches `gate`, so the last thing anyone sees
            # is the "message" gate set above - accurate while running, but
            # stale for however long is left of entity_ingest_time_trigger()'s
            # own independent INGEST_POLL_WAIT before it happens to loop
            # back around and recompute a real one. Waking that loop now
            # (the same command "Trigger now" uses) makes it reassess
            # `entities_exist` immediately instead of leaving the stale gate
            # sitting there for up to 10 minutes.
            self._commands.setdefault("entity-ingest", []).append("skip_wait")

        await handle_await(self.tl.run_until_disconnected())
