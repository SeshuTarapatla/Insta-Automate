from app.instagram.methods.base import Base
from utils.logger import log


class Chat(Base):
    def __init__(self) -> None:
        log.info("Method: [italic red]Chat Saved[/]\n")
    
    def backup(self) -> None:
        "No backup required for Chat method."
    
    def download_media(self) -> None:
        ...
    
    def audit(self) -> None:
        ...
    
    def start(self) -> None:
        ...
    