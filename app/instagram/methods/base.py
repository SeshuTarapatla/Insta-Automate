from abc import ABC, abstractmethod


class Base(ABC):
    """Abstract base class for all scrape methods."""

    @abstractmethod
    def download_media(self) -> None:
        """Downloads currenty entity's media.  
        |
            Profile: Profile picture,  
            Post: Post media,  
            Reel: Reel media,  
            Chat: None
        """

    @abstractmethod
    def audit(self) -> None:
        """Audits the current run."""
    
    @abstractmethod
    def backup(self) -> None:
        """Backs up the current entity."""
    
    @abstractmethod
    def start(self) -> None:
        """Sets the UI up before starting scrape."""
    

'''
FLOW:
    1. Audit:
        - Requires: root, list
            Profile: root: TITLE, list: -r with previous audit, -f [1 or 2], default min of f1 or f2
                > Read title, Decide ScanList
            Post: root: Post-INDEX-HASH, list: LIKES
                > Download post, calculate hash, fetch current index
            Reel: root: Reel-INDEX-HASH, list: LIKES
                > Download post, calculate hash, fetch current index
            Chat: root: Chat, list: SAVED
    2. Backup:
        - Condition: Skip if resume
            Profile: Share to BACKUP_ACCOUNT
            Post: Share to BACKUP_ACCOUNT
            Reel: Share to BACKUP_ACCOUNT
            Chat: No backup required
    3. Start:
        - Steps: 1. Create save folder, 2. Put current report, 3. Start scrape
        1. Save dir: INSTA_SAVE_DIR/ROOT/LIST
            Profile:
                - INSTA_SAVE_DIR/PROFILE/LIST
'''