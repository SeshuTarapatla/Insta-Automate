from asyncio import wait_for
from os import getenv

from my_modules.helpers import handle_await
from telethon import TelegramClient
from telethon.sessions import StringSession

from insta_automate.exceptions import TgAuthError


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


class BotTelegramClient(BaseTelegramClient):
    def __init__(
        self,
        session: str | StringSession,
        api_id: int | str,
        api_hash: str,
        bot_token: str,
    ) -> None:
        self.bot_token = bot_token
        super().__init__(session, api_id, api_hash)

    async def start(self, timeout: float = 2):  # type: ignore[override]
        _start = super().start(bot_token=self.bot_token)
        try:
            return await wait_for(handle_await(_start), timeout=timeout)
        except TimeoutError:
            return None


class IaTelegramClient(UserTelegramClient):
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
            raise TgAuthError("TG Auth credentials are missing from the environment.")

        self.TELEGRAM_API_ID = int(self.TELEGRAM_API_ID)
