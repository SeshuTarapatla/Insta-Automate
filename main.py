from pyfiglet import figlet_format

import model
from app.vars import args


# Main entrypoint
def main() -> None:
    print(f"{figlet_format("Insta Automate")}")
    match args.action:
        case "setup":
            model.setup()
        case _:
            pass
    print()


if __name__ == "__main__":
    main()
