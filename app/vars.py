from argparse import ArgumentParser, Namespace

__all__ = ["SERIAL", "args"]


# Args Namespace
class InstagramNamespace(Namespace):
    """Namespace for input arguments."""
    flist   : int
    force   : bool
    resume  : bool
    setup   : bool
    backup  : bool

# Runtime variables
SERIAL: str = "9cb9ec04"


# Argparse for input arguments
parser = ArgumentParser(allow_abbrev=False)
parser.add_argument("-s", "--setup" , action="store_true", help="Setup postgres schema and tables.")
parser.add_argument("-F", "--force" , action="store_true", help="Force flag, use with setup to recreate schema.")
parser.add_argument("-r", "--resume", action="store_true", help="Resume previous scrape entity.")
parser.add_argument("-f", "--flist" , choices=[1, 2], type=int, help="Follower list to scrape. 1-Followers, 2-Following.")
parser.add_argument("-b", "--backup", action="store_false", help="Skip taking backup of scrape entity.")
args, redundant = parser.parse_known_args(namespace=InstagramNamespace)
