from pathlib import Path

from app.instagram.objects.profile import Profile
from app.instagram.resource import SAVE_FOLDER


def current_profile() -> Path:
    """Function to download one profile at time of UiError. This automatically saves the profile to latest scrape dir."""
    current =  sorted(map(lambda x: x, SAVE_FOLDER.glob("*/*/*/*.jpg")), key=lambda x: x.stat().st_mtime, reverse=True)[0].parent
    root = current.parts[-2]
    profile = Profile.get_or_create(root=root)
    print(profile.__repr__())
    report = profile.generate_report(current)
    profile.insert()
    return report
