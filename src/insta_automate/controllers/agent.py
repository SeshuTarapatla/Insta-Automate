from typing import Any

import httpx
from my_modules.logger import get_logger

from insta_automate.models.meta import Config
from insta_automate.vars import IA_AGENT_TOKEN

log = get_logger(__name__)


def _current_flow_run_id() -> str | None:
    """Every `emit()`/`emit_sync()` call needs this so the Live screen (CP 4.4)
    can scope events/logs to one specific run rather than just "this flow in
    general" - two back-to-back runs of `entity-scrape` would otherwise mix
    together. Injected centrally here rather than threaded through every call
    site: `prefect.runtime.flow_run.id` resolves correctly from inside a task
    too, not just the flow body, since it reads the enclosing flow run's
    context. `None` outside an orchestrated run (e.g. a bare function call in
    a script), never raised."""
    try:
        from prefect.runtime import flow_run

        return flow_run.id
    except Exception:
        return None


class AgentClient:
    """Talks to ia-agent over the LAN. Every method swallows failures - the
    agent being unreachable from inside the pod must never affect the
    pipeline (ARCHITECTURE §3-6)."""

    def __init__(self) -> None:
        headers = {"Authorization": f"Bearer {IA_AGENT_TOKEN}"} if IA_AGENT_TOKEN else {}
        self._client = httpx.AsyncClient(headers=headers)

    def _url(self, path: str) -> str:
        return f"{str(Config.get('IA_AGENT_URL')).rstrip('/')}{path}"

    async def heartbeat(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """POST the per-flow state block (ARCHITECTURE §4.3); the response
        body carries queued commands (§4.4). [] if the agent is unreachable
        or the scheduler mirror (CP 3.4) doesn't exist yet."""
        try:
            response = await self._client.post(
                self._url("/api/scheduler/heartbeat"), json=state, timeout=2.0
            )
            response.raise_for_status()
            return response.json().get("commands", [])
        except Exception:
            return []

    async def emit(self, event: dict[str, Any]) -> None:
        """Fire-and-forget flow event (ARCHITECTURE §5). 1s timeout,
        failures swallowed - a scrape must never break because the agent
        is down or the event endpoint (CP 4.2) doesn't exist yet."""
        try:
            body = {"flow_run_id": _current_flow_run_id(), **event}
            await self._client.post(self._url("/api/events"), json=body, timeout=1.0)
        except Exception:
            pass

    async def notify(
        self,
        msg: str,
        *,
        image: str | None = None,
        transient: bool = False,
        dedupe: str | None = None,
        level: str = "info",
        tags: tuple[str, ...] = (),
    ) -> bool:
        """POST to the agent's notify endpoint (ARCHITECTURE §6). Returns
        `delivered` - False on any failure or if the notify endpoint (CP 6.1)
        doesn't exist yet, which is the caller's signal to fall back to
        Telegram."""
        try:
            response = await self._client.post(
                self._url("/api/notify"),
                json={
                    "msg": msg,
                    "image": image,
                    "transient": transient,
                    "dedupe": dedupe,
                    "level": level,
                    "tags": list(tags),
                },
                timeout=2.0,
            )
            response.raise_for_status()
            return bool(response.json().get("delivered", False))
        except Exception:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()


def emit_sync(event: dict[str, Any]) -> None:
    """`AgentClient.emit` for the handful of call sites that are plain sync
    functions (`tasks/ollama.py`'s `remove_public`/`gender_classify`) rather
    than `async def`. This has to actually block, not schedule a background
    task on the running loop: both call sites `unlink()`/`move()` the same
    image on the very next line, in a tight sync loop that never yields back
    to the loop until the whole function returns - a scheduled task would
    only ever run after every file in the batch was already gone, which is
    exactly the race the agent's image cache (CP 4.2) exists to avoid. A
    blocking POST costs nothing next to the AI inference call each iteration
    already makes. Same failure-swallowing contract as `emit`."""
    try:
        body = {"flow_run_id": _current_flow_run_id(), **event}
        httpx.post(
            f"{str(Config.get('IA_AGENT_URL')).rstrip('/')}/api/events",
            json=body,
            headers={"Authorization": f"Bearer {IA_AGENT_TOKEN}"} if IA_AGENT_TOKEN else {},
            timeout=1.0,
        )
    except Exception:
        pass
