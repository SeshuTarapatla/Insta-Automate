from datetime import datetime

from app.instagram.methods.common import resume
from app.instagram.resource import resourceIds
from app.vars import args
from utils import device
from utils.logger import log
from utils.misc import time_limit


def scrape() -> None:
    log.info("Insta Automate: [yellow]SCRAPE[/]")
    if args.resume:
        resume()
    started_at = datetime.now()
    while True:
        selectors: list[str] = [
            resourceIds.PROFILE_POSTS_TITLE,
            resourceIds.POST_LIKE_COUNT,
            resourceIds.REEL_LIKE_BUTTON,
            resourceIds.MESSAGE_CONTAINER
        ]
        selector = list(filter(lambda selector: device(selector).exists(), selectors))
        if len(selector) == 1:
            break
        elif len(selector) > 1:
            raise AttributeError("Multiple selectors filtered.")
        time_limit(started_at)
    match selector[0]:
        case resourceIds.PROFILE_POSTS_TITLE:
            log.info("Profile followers")
        case resourceIds.POST_LIKE_COUNT:
            log.info("Post likes")
        case resourceIds.REEL_LIKE_BUTTON:
            log.info("Reel likes")
        case resourceIds.MESSAGE_CONTAINER:
            log.info("Chat saved")
        case _:
            raise AttributeError("Invalid selector.")