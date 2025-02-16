from datetime import datetime
from json import dumps

from app.instagram.objects.common import Format
from model.audit import Audit as AuditModel
from model.audit import Scanned
from model.base import session


class Audit(AuditModel):
    def __init__(self, root: str, list: Scanned) -> None:
        super().__init__()
        self.root = root
        self.list = list
        self.count = 0
        self.timestamp = datetime.now()
    
    def __str__(self) -> str:
        return f"Audit(root: @{self.root}, list: {self.list.value}, count: {self.count}, timestamp: {Format.dt_to_str(self.timestamp)})"
    
    def __repr__(self) -> str:
        data = self.__dict__.copy()
        data.pop("_sa_instance_state")
        data["list"] = self.list.value
        data["timestamp"] = Format.dt_to_str(self.timestamp)
        return dumps(data, indent=2, ensure_ascii=False)
    
    def insert(self) -> None:
        """Insert current record."""
        session.add(self)
        session.commit()
    
    def update_count(self, increment: int = 1) -> None:
        """Increase count of current audit."""
        self.count += increment
        session.commit()

    @staticmethod
    def get_previous(root: str) -> "Audit | None":
        """Get previous audit for given root if exists."""
        return session.query(Audit).where(Audit.root == root).order_by(Audit.timestamp.desc()).limit(1).one_or_none()
    