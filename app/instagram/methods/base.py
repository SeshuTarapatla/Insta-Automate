from abc import ABC, abstractmethod


class Base(ABC):
    """Abstract base class for all scrape methods."""

    @abstractmethod
    def start(self) -> None:
        """Sets the UI up before starting scrape."""
        

    @abstractmethod
    def audit(self) -> None:
        """Audits the current run."""
