from datetime import datetime

from app.instagram.methods.chat import Chat
from app.instagram.methods.common import resume
from app.instagram.methods.followers import Followers
from app.instagram.methods.likes import Likes
from app.instagram.resource import resourceIds
from app.vars import args
from utils import device
from utils.logger import log
from utils.misc import time_limit


def scrape() -> None:
    log.info("Insta Automate: [green]SCRAPE[/]")
    if args.resume:
        resume()
    started_at = datetime.now()
    while True:
        selectors: list[str] = [
            resourceIds.PROFILE_POSTS_TITLE,
            resourceIds.POST_LIKE_BUTTON,
            resourceIds.REEL_LIKE_BUTTON,
            resourceIds.MESSAGE_CONTAINER,
        ]
        selector = list(filter(lambda selector: device(selector).exists(), selectors))
        if len(selector) == 1:
            break
        elif len(selector) > 1:
            raise AttributeError("Multiple selectors filtered.")
        time_limit(started_at)
    match selector[0]:
        case resourceIds.PROFILE_POSTS_TITLE:
            method = Followers()
        case resourceIds.POST_LIKE_BUTTON:
            method = Likes("post")
        case resourceIds.REEL_LIKE_BUTTON:
            method = Likes("reel")
        case resourceIds.MESSAGE_CONTAINER:
            method = Chat()
        case _:
            raise AttributeError("Invalid selector.")
    method.start()
