import logging
import sys
from src.config import config

def setup_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(config.LOG_LEVEL)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
