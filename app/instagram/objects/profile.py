from datetime import datetime
from json import dumps
from pathlib import Path
from shutil import move
from time import sleep

from app.instagram.objects.common import Format, download_last_media
from app.instagram.resource import classNames, resourceIds
from model.base import session
from model.profiles import Profile as ProfileModel
from model.profiles import Relation
from utils import device


class Profile(ProfileModel):
    """Profile object representing a Instagram user."""

    def __init__(self, root: str | None = None, auto_generate: bool = True) -> None:
        """Create profile object from device state."""
        super().__init__()
        self.id = Profile.get_title()
        self.root = self.id
        if auto_generate:
            self.generate(root)
    
    def generate(self, root: str | None) -> None:
        """Generates profile object from current device state."""
        self.name = device.get_text(resourceIds.PROFILE_NAME)
        self.bio = device.get_text(resourceIds.PROFILE_BIO).replace("\n", ", ")
        self.posts_str = device(resourceIds.PROFILE_POSTS).get_text()
        self.followers_str = device(resourceIds.PROFILE_FOLLOWERS).get_text()
        self.following_str = device(resourceIds.PROFILE_FOLLOWING).get_text()
        self.posts = Format.str_to_int(self.posts_str)
        self.followers = Format.str_to_int(self.followers_str)
        self.following = Format.str_to_int(self.following_str)
        self.root = root if root else self.id
        self.private = device(resourceIds.PROFILE_POSTS_TAB).exists()
        self.verified = device(resourceIds.PROFILE_VERIFIED).exists()
        if device(text="Edit profile").exists():
            self.relation = Relation.FOLLOWING
        elif device(text="Restricted profile").exists():
            self.relation = Relation.RESTRICTED
        elif device(resourceIds.PROFILE_RELATION).exists():
            self.relation = Relation(device(resourceIds.PROFILE_RELATION).get_text())
    
    def __str__(self) -> str:
        """Short representation of profile object."""
        return f"Profile(id: @{self.id}, Posts: {self.posts_str}, Followers: {self.followers_str}, Following: {self.following_str})"

    def __repr__(self) -> str:
        """Full representation of profile object."""
        data = self.__dict__.copy()
        data.pop("_sa_instance_state")
        if "relation" in data:
            data["relation"] = self.relation.value
            data["timestamp"] = Format.dt_to_str(self.timestamp)
        return dumps(data, indent=2, ensure_ascii=False)

    def insert(self) -> None:
        """Inserts profile object into database if not exists."""
        if not self.exists:
            session.add(self)
            session.commit()
    
    @property
    def exists(self: "str | Profile") -> bool:
        """Checks if profile object exists in database."""
        id = self.id if isinstance(self, Profile) else self
        return bool(session.query(Profile).where(Profile.id == id).one_or_none())

    @property
    def log_repr(self) -> str:
        id_len = 20
        return (
            f"[magenta bold]Profile[/]("
            f"ID: [cyan bold]@{self.id.ljust(id_len)[:id_len]}[/], "
            f"Posts: [red bold]{self.posts_str.rjust(5)}[/], "
            f"Followers: [green bold]{self.followers_str.rjust(5)}[/], "
            f"Following: [blue bold]{self.following_str.rjust(5)}[/])"
        )

    @staticmethod
    def get_title() -> str:
        """Returns title of current profile."""
        return device(resourceIds.PROFILE_TITLE).get_text()

    def download_dp(self: "str | Profile", save_to: Path = Path(".")) -> Path:
        started_at = datetime.now()
        id = self.id if isinstance(self, Profile) else self
        device(className=classNames.IMAGE_BUTTON).click()
        sleep(0.5)
        device(text="Show Profile Picture Larger").click()
        device(text="DOWNLOAD PROFILE PHOTO").click()
        src = download_last_media(started_at)
        dst = save_to / f"{id}.jpg"
        move(src, dst)
        return dst
    
    