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
    HOME_TAB = id("feed_tab")
    INBOX_TAB = id("action_bar_inbox_button")
    INBOX_USER_CONTAINER = id("row_inbox_container")
    INBOX_USERNAME = id("row_inbox_username")
    LIKE_USER_CONTAINER = id("row_user_container_base")
    MESSAGE_CONTAINER = id("message_placeholder_container")
    POST_LIKE_COUNT = id("row_feed_like_count")
    PROFILE_POSTS_TITLE = id("row_profile_header_textview_post_title")
    PROFILE_TITLE = id("action_bar_title")
    REEL_LIKE_BUTTON = id("like_button")


class classNames:
    """Instagram UI classnames."""
    ...
