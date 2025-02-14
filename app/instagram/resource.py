from pathlib import PurePosixPath


# Instagram runtime variables
PACKAGE         : str = "cc.honista.app"
BACKUP_ACCOUNT  : str = "lonewolf_cy"
PICTURES_FOLDER : PurePosixPath = PurePosixPath("/storage/emulated/0/Download/Honista/Honista_Photos")
VIDEOS_FOLDER   : PurePosixPath = PurePosixPath("/storage/emulated/0/Download/Honista/Honista_Videos")


def id(resourceId: str) -> str:
    """Parses given string into resourceId."""
    return ":id/".join([PACKAGE, resourceId])


class resourceIds:
    """Instagram UI resourceIds."""
    PROFILE_TITLE = id("action_bar_title")
    HOME_TAB = id("feed_tab")
    INBOX_TAB = id("action_bar_inbox_button")
    INBOX_USER_CONTAINER = id("row_inbox_container")
    INBOX_USERNAME = id("row_inbox_username")
    MESSAGE_CONTAINER = id("message_placeholder_container")


class classNames:
    """Instagram UI classnames."""
    ...
