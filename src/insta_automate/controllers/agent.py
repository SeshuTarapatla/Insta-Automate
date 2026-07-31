from typing import Any

import httpx
from my_modules.logger import get_logger

from insta_automate.models.meta import Config
from insta_automate.vars import IA_AGENT_TOKEN

log = get_logger(__name__)


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
            await self._client.post(self._url("/api/events"), json=event, timeout=1.0)
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
