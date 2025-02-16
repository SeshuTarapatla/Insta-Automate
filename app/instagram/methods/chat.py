from app.instagram.methods.base import Base
from app.instagram.objects.audit import Audit
from model.audit import Scanned
from utils.logger import log


class Chat(Base):
    def __init__(self) -> None:
        log.info("Method: [italic red]Chat Saved[/]\n")
    
    def backup(self) -> None:
        "No backup required for Chat method."
    
    def download_media(self) -> None:
        "No media download required for Chat method"
    
    def audit_run(self) -> None:
        self.audit = Audit("chat-saved", Scanned.SAVED)
        self.audit.insert()
    
    def start(self) -> None:
        self.audit_run()
    