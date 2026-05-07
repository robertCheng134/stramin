import logging


_LOG_FORMAT = "%(levelname)s: %(message)s"


def get_logger(name):
    logger = logging.getLogger(name)

    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)

    return logger
