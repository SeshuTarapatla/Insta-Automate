from pathlib import Path, PurePosixPath


# Instagram runtime variables
PACKAGE         : str = "com.instagram.android"
BACKUP_ACCOUNT  : str = "lonewolf_cy"
PICTURES_FOLDER : PurePosixPath = PurePosixPath("/storage/emulated/0/Download/InstaPro")
VIDEOS_FOLDER   : PurePosixPath = PurePosixPath("/storage/emulated/0/Download/InstaPro")
SAVE_FOLDER     : Path = Path(r"C:\Users\seshu\Pictures\Insta")


def id(resourceId: str) -> str:
    """Parses given string into resourceId."""
    return ":id/".join([PACKAGE, resourceId])


class resourceIds:
    """Instagram UI resourceIds."""
    APP_FULLSCREEN = id("layout_container_main")
    HOME_TAB = id("feed_tab")
    INBOX_TAB = id("action_bar_inbox_button")
    INBOX_USER_CONTAINER = id("row_inbox_container")
    INBOX_USERNAME = id("row_inbox_username")
    LIKE_USER_CONTAINER = id("row_user_container_base")
    MESSAGE_CONTAINER = id("message_placeholder_container")
    POST_LIKE_COUNT = id("row_feed_like_count")
    POST_MENU_BUTTON = id("feed_more_button_stub")
    POST_HINT_AREA = id("hint_icon_container")
    POST_SHARE_BUTTON = id("row_feed_button_share")
    PROFILE_BIO = id("profile_header_bio_text")
    PROFILE_FOLLOWERS = id("row_profile_header_textview_followers_count")
    PROFILE_FOLLOWING = id("row_profile_header_textview_following_count")
    PROFILE_NAME = id("profile_header_full_name")
    PROFILE_OPTIONS = id("action_bar_overflow_icon")
    PROFILE_PICTURE = id("profilePic")
    PROFILE_POSTS = id("row_profile_header_textview_post_count")
    PROFILE_POSTS_TAB = id("profile_tabs_container")
    PROFILE_POSTS_TITLE = id("row_profile_header_textview_post_title")
    PROFILE_RELATION = id("profile_header_follow_button")
    PROFILE_TABS = id("profile_tabs_container")
    PROFILE_TITLE = id("action_bar_title")
    PROFILE_VERIFIED = id("action_bar_title_verified_badge")
    REEL_LIKE_BUTTON = id("like_button")
    REEL_MENU_BUTTON = id("clips_ufi_more_button_component")
    SHARE_USERNAME = id("row_user_primary_name")


class classNames:
    """Instagram UI classnames."""
    IMAGE_BUTTON = "android.widget.ImageButton"
