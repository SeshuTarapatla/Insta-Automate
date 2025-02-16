from datetime import datetime
from PIL import Image


class Format:
    """Formatter class for Instagram objects."""

    @staticmethod
    def str_to_int(value: str) -> int:
        """Converts instagram human readable number to integer. Used for posts & followers notation."""
        value = value.replace(",", "").upper()
        if "K" in value:
            return int(float(value[:-1]) * 1_000)
        elif "M" in value:
            return int(float(value[:-1]) * 1_000_000)
        else:
            return int(value)

    @staticmethod
    def int_to_str(value: int) -> str:
        """Converts integer to instagram human readable number. Used for posts & followers notation."""
        if value >= 1_000_000:
            return str(value/1_000_000)[:4].rstrip(".") + "M"
        elif value >= 10_000:
            return str(value/1_000_000)[:4].rstrip(".") + "M"
        else:
            return f"{value:,}"
    
    @staticmethod
    def dt_to_str(dt: datetime) -> str:
        """Converts datetime object to instagram human readable date."""
        return dt.strftime("%Y-%m-%d %H:%M:%S")

def app_screenshot() -> Image.Image:
    ...