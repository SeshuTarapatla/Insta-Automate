import model
from app import instagram
from app.vars import args
from utils import scrcpy


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
