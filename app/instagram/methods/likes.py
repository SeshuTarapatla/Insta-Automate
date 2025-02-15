from typing import Literal
from app.instagram.methods.base import Base
from utils.logger import log


class Likes(Base):
    def __init__(self, type: Literal["reel", "post"]) -> None:
        log.info(f"Method: [bold red]{type.capitalize()} Likes[/]")
    
    def audit(self) -> None:
        ...
    
    def start(self) -> None:
        ...