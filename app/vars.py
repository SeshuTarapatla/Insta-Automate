from argparse import ArgumentParser

__all__ = ["args"]


class InstagramNamespace:
    """Namespace for input arguments."""
    action  : str
    force   : bool

    def __str__(self) -> str:
        """String representation for Instagram Namespace."""
        return f"InstagramNamespace(action='{self.action}'{', force=True' if self.force else ''})"

# input argument parser
parser  = ArgumentParser()
action  = parser.add_subparsers(dest="action", required=False)
setup   = action.add_parser("setup", help="setup postgres tables")
force   = setup.add_argument("-f", "--force", action="store_true", help="clear postgres and setup new")

# args parsed into namespace
args    = parser.parse_args(namespace=InstagramNamespace())
