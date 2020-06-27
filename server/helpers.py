import logging
import sys


def get_log_level(level):
    if not level:
        return logging.NOTSET

    value = getattr(logging, level.upper(), None)
    if isinstance(value, int):
        return value
    else:
        print(
            f"note:  illegal logging level {level}, using default unset",
            file=sys.stderr,
        )
        return logging.NOTSET
