from app.instagram.methods.base import Base
from utils.logger import log


class Followers(Base):
    def __init__(self) -> None:
        log.info("Method: [bold red]Profile followers[/]")
    
    def audit(self) -> None:
        ...
    
    def start(self) -> None:
        ...