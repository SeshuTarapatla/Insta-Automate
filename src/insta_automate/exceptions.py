class TgAuthError(ValueError):
    """Exception raised when telegram auth credentials are missing in environment."""


class TelegramChannelNotFound(RuntimeError):
    """Exception raised when a given Telegram channel is not found."""


class TelegramChannelCreateError(RuntimeError):
    """Exception raised when a request to create a telegram channel is failed."""


class TelegramChannelBotAdminError(RuntimeError):
    """Exception raised when failed to add given bot as an admin to a channel."""
