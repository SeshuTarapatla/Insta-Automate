"""Notifier facade (PLAN CP 6.2, control-center ARCHITECTURE §6).

Replaces every direct `tl.bot.notify(...)` call with one that tries the
control-center agent first — so an *actively connected* paired phone
(Phase 6) gets it within a second — and falls back to the existing Telegram
bot, which stays the guaranteed backstop: the agent can be down,
unreachable, or simply have no phone connected right now. `delivered`
(from `AgentClient.notify`) means "a paired device's live WS connection got
this," not "someone, possibly just the desktop app, is connected" — the
agent's own `EventBus`/`NotificationStore` (control-center CP 6.1 fix)
enforce that distinction; the desktop is always a passive viewer of
whatever the agent broadcasts and never affects this decision either way.

`NOTIFY_POLICY` (`models.meta.Config`, default `app_first`) picks the
strategy:

- `telegram_only` — skip the agent entirely (today's pre-control-center
  behaviour).
- `app_first` (default) — try the agent; fall through to Telegram only if
  it didn't actually reach a connected phone.
- `both` — send to both unconditionally, so history exists in both places
  even on a run where the agent did deliver.

`always_telegram=True` is a per-call override, independent of policy, for
notifications about one specific profile (a follow/unfollow prompt, an
already-known entity) rather than a flow-level event — these are judged
consequential enough to always reach Telegram regardless of whether a phone
happens to be connected, on top of (not instead of) reaching the phone when
one is. `url`, when set, is that profile's Instagram URL — forwarded to the
agent as the notification's tap target; Telegram doesn't need it separately
since the message text already embeds a markdown link for Telegram's own
renderer.

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
    url: str | None = None,
    always_telegram: bool = False,
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
            url=url,
        )

    if policy == "both" or always_telegram or not delivered:
        tl = tl or await IaTelegram.get_client()
        await _notify_telegram(tl, msg, image=image, transient=transient, dedupe=dedupe)

    return delivered
