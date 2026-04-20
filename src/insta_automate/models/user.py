from datetime import datetime

from my_modules.datetime_utils import now
from sqlmodel import Field, SQLModel

from insta_automate.controllers.device import IaUI
from insta_automate.models.meta import EntityAccess
from insta_automate.utils import ia_int


class User(SQLModel, table=True):
    id: str = Field(primary_key=True)
    root: str
    name: str
    bio: str
    posts: str
    followers: str
    following: str
    p: int
    f1: int
    f2: int
    access: EntityAccess
    added_on: datetime = Field(default_factory=now)

    @classmethod
    def from_ui(cls, ui: IaUI):
        id = ui.profile_id.get_text()
        name = name.get_text() if (name := ui.profile_name).exists else ""
        bio = bio.get_text() if (bio := ui.profile_bio).exists else ""
        posts = ui.profile_posts.get_text()
        followers = ui.profile_followers.get_text()
        following = ui.profile_following.get_text()
        p = ia_int(posts)
        f1 = ia_int(followers)
        f2 = ia_int(following)
        return cls.model_validate(
            cls(
                id=id,
                root=id,
                name=name,
                bio=bio,
                posts=posts,
                followers=followers,
                following=following,
                p=p,
                f1=f1,
                f2=f2,
                access=EntityAccess.PRIVATE,
            )
        )
