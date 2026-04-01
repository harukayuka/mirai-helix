import logging
import os

_LOGGER = None


def setup_logging() -> logging.Logger:
    """Configure and return a shared logger for the app."""
    global _LOGGER
    if _LOGGER:
        return _LOGGER

    log_level = os.getenv("MIRAI_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    logger = logging.getLogger("mirai")
    logger.setLevel(level)

    if not logger.handlers:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        stream = logging.StreamHandler()
        stream.setLevel(level)
        stream.setFormatter(formatter)
        logger.addHandler(stream)

        log_file = os.getenv("MIRAI_LOG_FILE")
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    _LOGGER = logger
    return logger
