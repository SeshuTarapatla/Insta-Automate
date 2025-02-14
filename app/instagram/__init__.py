from app.instagram.methods.common import resume
from app.vars import args
from utils.logger import log


def scrape() -> None:
    log.info("Insta Automate: [yellow]SCRAPE[/]")
    if args.resume:
        resume()