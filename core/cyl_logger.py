import logging
import logging.handlers
import os
import time

from concurrent_log_handler import ConcurrentRotatingFileHandler


class CustomFormatter(logging.Formatter):

    ## colors
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    blue = "\x1b[36;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "[%(asctime)s] [%(levelname).1s] - %(message)s (%(name)s)(%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: blue + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

class CYLLogger(object):
    def __init__(self, logger=None, log_path="", **kwargs):

        self.logger = logging.getLogger(logger)
        self.logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname).1s] - %(message)s (%(name)s)(%(filename)s:%(lineno)d)"
        )
        if not self.logger.handlers:
            print(self.logger)
            ch = logging.StreamHandler()
            ch.setLevel(kwargs.get("c_level", logging.DEBUG))
            ch.setFormatter(CustomFormatter())
            self.logger.addHandler(ch)
            ch.close()

            if log_path and os.path.exists(os.path.dirname(os.path.abspath(log_path))):
                print(self.logger.handlers)
                fh = logging.FileHandler(log_path, "a", encoding="utf-8")
                if kwargs.get("rotation", False):
                    rotation_size = kwargs.get("rotation_size", 50*1024)
                    backup_count = kwargs.get("backup_count", 5)
                    # fh = logging.handlers.RotatingFileHandler(log_path, maxBytes=rotation_size, backupCount=backup_count, encoding="utf-8")
                    fh = ConcurrentRotatingFileHandler(log_path, maxBytes=rotation_size, backupCount=backup_count, encoding="utf-8")
                fh.setLevel(kwargs.get("f_level", logging.INFO))
                fh.setFormatter(formatter)
                self.logger.addHandler(fh)
                fh.close()

    def getlog(self):
        return self.logger
