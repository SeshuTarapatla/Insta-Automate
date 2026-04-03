__all__ = ["ia"]

from dotenv import load_dotenv

from insta_automate.controllers.cli import ia

if __name__ == "__main__":
    load_dotenv()
    ia()
