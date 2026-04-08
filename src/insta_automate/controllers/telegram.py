import asyncio
from asyncio import wait_for
from os import getenv
from typing import Any, AsyncIterable, Literal, overload

from dotenv import load_dotenv
from my_modules.datetime_utils import now
from my_modules.helpers import handle_await
from my_modules.logger import get_logger
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.custom.dialog import Dialog
from telethon.tl.functions.channels import CreateChannelRequest, EditAdminRequest
from telethon.types import (
    Channel,
    ChatAdminRights,
    Message,
    Updates,
)

from insta_automate.exceptions import (
    TelegramAuthEnvironmentError,
    TelegramBotNotifyChannelEmpty,
    TelegramChannelBotAdminError,
    TelegramChannelCreateError,
    TelegramChannelNotFoundError,
)
from insta_automate.vars import IA_BACKUP_CHANNEL, IA_ENTITY_CHANNEL, IA_NOTIFY_CHANNEL

log = get_logger(__name__)


class BaseTelegramClient(TelegramClient):
    def __init__(
        self,
        session: str | StringSession,
        api_id: int | str,
        api_hash: str,
    ) -> None:
        session = StringSession(session) if isinstance(session, str) else session
        api_id = int(api_id)
        super().__init__(session=session, api_id=api_id, api_hash=api_hash)

    async def delete_message(self, message: Message):
        return await self.delete_messages(message.peer_id, message)


class UserTelegramClient(BaseTelegramClient):
    def __init__(
        self,
        session: str | StringSession,
        api_id: int | str,
        api_hash: str,
        phone_number: str,
    ) -> None:
        self.phone_number = phone_number
        super().__init__(session, api_id, api_hash)

    async def start(self, timeout: float = 2):  # type: ignore[override]
        _start = super().start(phone=self.phone_number)
        try:
            return await wait_for(handle_await(_start), timeout=timeout)
        except TimeoutError:
            return None

    async def iter_all_dialogs(self) -> AsyncIterable[Dialog]:
        for archived in (False, True):
            async for dialog in self.iter_dialogs(archived=archived):
                yield dialog

    async def get_channels(self) -> list[Channel]:
        channels = [
            dialog.entity
            async for dialog in self.iter_all_dialogs()
            if isinstance(dialog.entity, Channel)
        ]
        return channels

    @overload
    async def get_channel(
        self, title: str, *, strict: Literal[False]
    ) -> Channel | None: ...

    @overload
    async def get_channel(
        self, title: str, *, strict: Literal[True] = True
    ) -> Channel: ...

    async def get_channel(self, title: str, *, strict: bool = True) -> Channel | None:
        async for dialog in self.iter_all_dialogs():
            if isinstance(dialog.entity, Channel) and dialog.entity.title == title:
                return dialog.entity
        if not strict:
            return None
        raise TelegramChannelNotFoundError(
            f'Telegram channel with title "{title}" is not found.'
        )

    async def create_channel(
        self, title: str, *, about: str, broadcast: bool = True
    ) -> Channel:
        request = CreateChannelRequest(
            title=title, about=about, megagroup=not broadcast
        )
        result = await self(request)
        if (
            isinstance(result, Updates)
            and result.chats
            and isinstance((channel := result.chats[0]), Channel)
        ):
            return channel
        raise TelegramChannelCreateError(
            f"Failed to create a Channel(title='{title}', about='{about}', broadcast={broadcast})"
        )

    async def add_bot_admin_to_channel(
        self, channel: Channel, bot_username: str
    ) -> Any:
        try:
            bot = await self.get_entity(bot_username)
            admin_rights = ChatAdminRights(
                anonymous=False,
                change_info=True,
                delete_messages=True,
                edit_messages=True,
                manage_direct_messages=True,
                other=True,
                pin_messages=True,
                post_messages=True,
            )
            request = EditAdminRequest(
                channel=channel,  # type: ignore
                user_id=bot,  # type: ignore
                admin_rights=admin_rights,
                rank="Bot",
            )
            result = await self(request)
            return result
        except Exception as e:
            raise TelegramChannelBotAdminError(
                f"Failed to add @{bot_username} as admin to Channel(title='{channel.title}')"
            ) from e


class BotTelegramClient(BaseTelegramClient):
    def __init__(
        self,
        session: str | StringSession,
        api_id: int | str,
        api_hash: str,
        bot_token: str,
        notify_channel_id: int | None = None,
    ) -> None:
        self.bot_token = bot_token
        self.notify_channel_id = notify_channel_id
        super().__init__(session, api_id, api_hash)

    async def start(self, timeout: float = 2):  # type: ignore[override]
        _start = super().start(bot_token=self.bot_token)
        try:
            return await wait_for(handle_await(_start), timeout=timeout)
        except TimeoutError:
            return None

    @overload
    async def notify(self, message: str, transient: Literal[True]) -> None: ...

    @overload
    async def notify(
        self, message: str, transient: Literal[False] = False
    ) -> Message: ...

    async def notify(
        self,
        message: str,
        transient: bool = False,
    ) -> Message | None:
        if self.notify_channel_id:
            notification = await self.send_message(
                self.notify_channel_id, message=message
            )
            if transient:
                await asyncio.sleep(5)
                await self.delete_message(notification)
            else:
                return notification
        else:
            raise TelegramBotNotifyChannelEmpty("Notify channel is not set.")


class IaTelegram(UserTelegramClient):
    def __init__(self) -> None:
        self.load_tg_auth()
        super().__init__(
            self.TELEGRAM_SESSION,
            self.TELEGRAM_API_ID,
            self.TELEGRAM_API_HASH,
            self.TELEGRAM_NUMBER,
        )
        self.bot = BotTelegramClient(
            self.TELEGRAM_BOT_SESSION,
            self.TELEGRAM_API_ID,
            self.TELEGRAM_API_HASH,
            self.TELEGRAM_BOT_TOKEN,
        )

    def load_tg_auth(self):
        load_dotenv()
        self.TELEGRAM_API_ID = getenv("TELEGRAM_API_ID", "")
        self.TELEGRAM_API_HASH = getenv("TELEGRAM_API_HASH", "")
        self.TELEGRAM_NUMBER = getenv("TELEGRAM_NUMBER", "")
        self.TELEGRAM_SESSION = getenv("TELEGRAM_SESSION", "")
        self.TELEGRAM_BOT_NAME = getenv("TELEGRAM_BOT_NAME", "")
        self.TELEGRAM_BOT_TOKEN = getenv("TELEGRAM_BOT_TOKEN", "")
        self.TELEGRAM_BOT_SESSION = getenv("TELEGRAM_BOT_SESSION", "")

        if not any(
            [
                self.TELEGRAM_API_ID,
                self.TELEGRAM_API_HASH,
                self.TELEGRAM_NUMBER,
                self.TELEGRAM_SESSION,
                self.TELEGRAM_BOT_NAME,
                self.TELEGRAM_BOT_TOKEN,
                self.TELEGRAM_BOT_SESSION,
            ]
        ):
            raise TelegramAuthEnvironmentError(
                "TG Auth credentials are missing from the environment."
            )

        self.TELEGRAM_API_ID = int(self.TELEGRAM_API_ID)

    async def start_(self, timeout: float = 2):
        return await super().start(timeout=timeout)

    async def start(self, timeout: float = 2):
        await self.start_(timeout=timeout)
        notify_channel = await self.get_channel(IA_NOTIFY_CHANNEL, strict=False)
        if notify_channel:
            self.bot.notify_channel_id = await self.get_peer_id(notify_channel)
        await self.bot.start(timeout=timeout)

    async def create_channel(
        self, title: str, *, about: str, broadcast: bool = True, bot_access: bool = True
    ) -> Channel:
        channel = await super().create_channel(
            title=title, about=about, broadcast=broadcast
        )
        if bot_access:
            await self.add_bot_admin_to_channel(channel, self.TELEGRAM_BOT_NAME)
        return channel

    @classmethod
    async def verify(cls, timeout: float = 2):
        tl, exit_code = cls(), 0
        if await tl.start_(timeout=timeout):
            log.info("Telegram User session: [dim green]CONNECTED![/]")
        else:
            log.error("Telegram User session: [dim red]DISCONNECTED![/]")
            exit_code = 1
        if await tl.bot.start(timeout=timeout):
            log.info("Telegram Bot  session: [dim green]CONNECTED![/]")
        else:
            log.error("Telegram Bot  session: [dim red]DISCONNECTED![/]")
            exit_code = 1
        exit(exit_code)

    @classmethod
    async def init(cls):
        def channel_str(channel: Channel) -> str:
            return f"Channel(id={channel.id}, title='{channel.title}')"

        started_at = now()

        tl = cls()
        await tl.start()
        if channel := await tl.get_channel(IA_ENTITY_CHANNEL, strict=False):
            log.info(f"Entity channel found: {channel_str(channel)}")
        else:
            log.error("Entity channel not found. Creating one...")
            channel = await tl.create_channel(
                IA_ENTITY_CHANNEL,
                about="Insta Automate Entity Channel",
                broadcast=False,
            )
            log.info(f"Entity channel created: {channel_str(channel)}")
        if channel := await tl.get_channel(IA_BACKUP_CHANNEL, strict=False):
            log.info(f"Backup channel found: {channel_str(channel)}")
        else:
            log.error("Backup channel not found. Creating one...")
            channel = await tl.create_channel(
                IA_BACKUP_CHANNEL, about="Insta Automate Backup Channel", broadcast=True
            )
            log.info(f"Backup channel created: {channel_str(channel)}")
        if channel := await tl.get_channel(IA_NOTIFY_CHANNEL, strict=False):
            log.info(f"Notify channel found: {channel_str(channel)}")
        else:
            log.error("Notify channel not found. Creating one...")
            channel = await tl.create_channel(
                IA_NOTIFY_CHANNEL, about="Insta Automate Notify Channel", broadcast=True
            )
            log.info(f"Notify channel created: {channel_str(channel)}")

        log.info(f"Telegram initialization complete. Time taken: {now() - started_at}")
