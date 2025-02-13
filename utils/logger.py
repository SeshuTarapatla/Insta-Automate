import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.style import Style
from rich.theme import Theme
from rich.traceback import install

__all__ = ["console", "log"]


# rich tracebacks
install(show_locals=True)

# log instance
log = logging.getLogger()
log.setLevel(logging.INFO)

# console for rich printing
console = Console(
    theme=Theme({x: Style() for x in [
        "repr.number",
        "repr.str",
        "repr.bool_true",
        "repr.bool_false",
        "repr.none",
        "repr.call",
        "log.time",
        "log.message"
    ]})
)

# handler and formatter
rich_handler = RichHandler(console=console, show_time=False, markup=True)
rich_handler.setLevel(logging.INFO)

formatter = logging.Formatter(": %(message)s")
rich_handler.setFormatter(formatter)

log.addHandler(rich_handler)


if __name__ == "__main__":
    # sample log messages
    log.debug("This is a debug message.")
    log.info("This is an info message.")
    log.warning("This is a warning message.")
    log.error("This is an error message.")
    log.critical("This is a critical message.")
