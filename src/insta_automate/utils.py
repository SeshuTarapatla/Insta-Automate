import logging

from insta_automate.vars import IA_PACKAGE_NAME


def set_logger_propagation(propagate: bool = True):
    for name in logging.root.manager.loggerDict:
        if name.startswith(IA_PACKAGE_NAME):
            logging.getLogger(name).propagate = propagate
