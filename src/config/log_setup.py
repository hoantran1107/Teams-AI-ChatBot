import logging
import sys


def setup_logging(logger=None, level=logging.INFO):
    if logger is None:
        logger = logging.getLogger()
    if logger.handlers:
        return
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler('ifd.log', encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.setLevel(level)
    logging.getLogger('httpx').setLevel(logging.WARNING)
