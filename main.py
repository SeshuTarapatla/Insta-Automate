import model
from app import instagram
from app.vars import args
from utils import scrcpy
from utils.logger import console, log


def main() -> None:
    """Main function to start the program"""
    if args.setup:
        model.setup()
    else:
        scrcpy.start()
        instagram.scrape()
        scrcpy.stop()


if __name__ == "__main__":
    main()
    # console.clear()
    # log.info("Device connected: [cyan]Oneplus6[/]")
    # log.info("Scrcpy session started\n")
    # log.info("Insta Automate: [green]SCRAPE[/]")
    # log.info("Method: [italic red]Profile followers[/]")
