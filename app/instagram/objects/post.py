from typing import Literal


class Post:
    def __init__(self, type: Literal["reel", "post"], auto_generate: bool = True) -> None:
        self.type = type
        if auto_generate:
            self.generate()
    
    def generate(self) -> None:
        ...