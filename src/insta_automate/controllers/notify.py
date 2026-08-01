"""Notifier facade (PLAN CP 6.2, control-center ARCHITECTURE §6).

Replaces every direct `tl.bot.notify(...)` call with one that tries the
control-center agent first — so a paired phone (Phase 6) gets it within a
second — and falls back to the existing Telegram bot, which stays the
guaranteed backstop: the agent can be down, unreachable, or simply have no
live subscriber right now. `NOTIFY_POLICY` (`models.meta.Config`, default
`app_first`) picks the strategy:

- `telegram_only` — skip the agent entirely (today's pre-control-center
  behaviour).
- `app_first` (default) — try the agent; fall through to Telegram only if
  it didn't actually deliver.
- `both` — send to both unconditionally, so history exists in both places
  even on a run where the agent did deliver.

`AgentClient.notify` (CP 3.3) already POSTs to `/api/notify` and returns
`delivered`; this module is the policy layer plus the Telegram fallback
that call sites used to hand-roll individually.
"""
from pathlib import Path
from typing import BinaryIO, Sequence

from insta_automate.controllers.agent import AgentClient
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.models.meta import Config
from insta_automate.vars import IA_DIR

Image = Path | BinaryIO


def _relative_image(image: Image | None) -> str | None:
    """The agent's image cache (control-center CP 4.2) keys everything by an
    `IA_DIR`-relative path, same convention as `emit()`'s `image` field — but
    not every call site has an on-disk file: `notify_profile_unfollow`'s
    image is a live `ui.profile_header.screenshot()` buffer, never written
    to `IA_DIR`. `None` for anything that isn't a real `Path` under `IA_DIR`
    — the agent notification simply carries no image in that case; Telegram
    (the guaranteed backstop) still gets the real buffer regardless, since
    `_notify_telegram` receives the original object, not this string."""
    if not isinstance(image, Path):
        return None
    try:
        return str(image.relative_to(IA_DIR))
    except ValueError:
        return None


async def _notify_telegram(
    tl: IaTelegram,
    msg: str,
    *,
    image: Image | None,
    transient: bool,
    dedupe: str | None,
) -> None:
    """Preserves `tasks/telegram.py`'s old `notify_transient` behaviour
    exactly: when a message is meant to replace its own prior occurrence
    (`dedupe` set), search the notify channel for messages with that exact
    text and delete them before sending the new one. This only ever finds
    something for callers whose message text is constant across calls (the
    two "new entities" notifications it originally covered) — a caller
    whose text embeds a changing number (the limit-reached messages) simply
    never matches anything, which is the same no-op those calls already
    got before this facade existed."""
    if dedupe:
        async for prior in tl.iter_messages_only(tl.notify_channel, search=msg):
            await prior.delete()
    if isinstance(image, Path):
        file = image if image.exists() else None
    else:
        file = image
    await tl.bot.notify(msg, transient=transient, file=file)


async def notify(
    msg: str,
    *,
    image: Image | None = None,
    transient: bool = False,
    dedupe: str | None = None,
    level: str = "info",
    tags: Sequence[str] = (),
    tl: IaTelegram | None = None,
) -> bool:
    policy = str(Config.get("NOTIFY_POLICY"))
    delivered = False

    if policy != "telegram_only":
        delivered = await AgentClient().notify(
            msg,
            image=_relative_image(image),
            transient=transient,
            dedupe=dedupe,
            level=level,
            tags=tuple(tags),
        )

    if policy == "both" or not delivered:
        tl = tl or await IaTelegram.get_client()
        await _notify_telegram(tl, msg, image=image, transient=transient, dedupe=dedupe)

    return delivered
