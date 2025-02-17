from datetime import datetime
from io import BytesIO
from json import dumps
from pathlib import Path
from shutil import move
from typing import Literal, overload

from PIL import Image
from send2trash import send2trash

from app.instagram.methods.common import download_media
from app.instagram.objects.common import Format
from app.instagram.resource import resourceIds
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
        device(resourceIds.PROFILE_POSTS).wait(timeout=5)
        self.name = device.get_text(resourceIds.PROFILE_NAME)
        self.bio = device.get_text(resourceIds.PROFILE_BIO).replace("\n", ", ")
        self.posts_str = device(resourceIds.PROFILE_POSTS).get_text()
        self.followers_str = device(resourceIds.PROFILE_FOLLOWERS).get_text()
        self.following_str = device(resourceIds.PROFILE_FOLLOWING).get_text()
        self.posts = Format.str_to_int(self.posts_str)
        self.followers = Format.str_to_int(self.followers_str)
        self.following = Format.str_to_int(self.following_str)
        self.root = root if root else self.id
        self.private = not device(resourceIds.PROFILE_POSTS_TAB).exists()
        self.verified = device(resourceIds.PROFILE_VERIFIED).exists()
        if device(text="Edit profile").exists():
            self.relation = Relation.FOLLOWING
        elif device(text="Restricted profile").exists():
            self.relation = Relation.RESTRICTED
        elif device(resourceIds.PROFILE_RELATION).exists():
            self.relation = Relation(device(resourceIds.PROFILE_RELATION).get_text())
        self.timestamp = datetime.now()
    
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
        if not self.exists():
            session.add(self)
            session.commit()
    
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
    
    @staticmethod
    def get(id: str) -> "Profile":
        return session.query(Profile).where(Profile.id == id).one()
        
    @overload
    def download_dp(self, return_type: Literal["path"] = "path", save_to: Path = Path(".")) -> Path: ...
    
    @overload
    def download_dp(self, return_type: Literal["bytes"], save_to: Path = Path(".")) -> bytes: ...

    def download_dp(self, return_type: Literal["path", "bytes"] = "path", save_to: Path = Path(".")) -> Path | bytes:
        started_at = datetime.now()
        dp_icon = device.get_siblings(resourceIds.PROFILE_HEADER)[4]
        dp_icon.click()
        device(text="SAVE PHOTO").click()
        src = download_media(started_at)
        dst = save_to / f"{self.id}.jpg"
        move(src, dst)
        if return_type == "bytes":
            data = dst.read_bytes()
            send2trash(dst)
            return data
        return dst
    
    def generate_report(self, save_to: Path = Path(".")) -> Path:
        dst = save_to/(self.id+".jpg")
        if dst.exists():
            return dst
        profile_page = device(resourceIds.APP_FULLSCREEN).screenshot()
        dp = self.download_dp(return_type="bytes")
        profile_pic = Image.open(BytesIO(dp))
        profile_pic = profile_pic.resize((profile_page.height, profile_page.height))
        report = Image.new("RGB", (profile_pic.width + profile_page.width, profile_page.height))
        report.paste(profile_pic, (0, 0))
        report.paste(profile_page, (profile_pic.width, 0))
        report.save(dst)
        return dst
    
    @staticmethod
    def get_or_create(id: str | None = None) -> "Profile":
        if id is None:
            id = Profile.get_title()
        if Profile.exists(id):
            return Profile.get(id)
        else:
            return Profile()