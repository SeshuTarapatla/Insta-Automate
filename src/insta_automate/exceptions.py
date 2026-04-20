class TelegramAuthEnvironmentError(EnvironmentError):
    """Exception raised when telegram auth credentials are missing in environment."""


class TelegramChannelNotFoundError(RuntimeError):
    """Exception raised when a given Telegram channel is not found."""


class TelegramChannelCreateError(RuntimeError):
    """Exception raised when a request to create a telegram channel is failed."""


class TelegramChannelBotAdminError(RuntimeError):
    """Exception raised when failed to add given bot as an admin to a channel."""


class TelegramBotNotifyChannelEmpty(ValueError):
    """Exception raised when a bot user tries to notify without setting the notify channel."""


class IaTelegramBackupNotFound(FileNotFoundError):
    """Exception raised when there is no Insta Automate backup found to restore."""


class InvalidEntityUrl(ValueError):
    """Exception raised when a given entity is not a valid Instagram url."""


class InvalidEntity(RuntimeError):
    """Exception raised when an invalid entity object is passed to the tasks."""


class EntityAccessResolutionError(TimeoutError):
    """Exception raised when failed to determina access type of a given entity."""
