class Insta:
    @staticmethod
    def to_int(value: str) -> int:
        value, factor = value.replace(",", "").upper(), 1
        if "M" in value:
            factor = 1_000_000
            value = value[:-1]
        elif "K" in value:
            factor = 1_000
            value = value[:-1]
        return round(float(value) * factor)

    @staticmethod
    def url(root: str) -> str:
        if root.startswith("reel"):
            suffix = f"reel/{root.removeprefix('reel-')}"
        elif root.startswith("post"):
            suffix = f"p/{root.removeprefix('post-')}"
        else:
            suffix = root
        return f"https://www.instagram.com/{suffix}"
