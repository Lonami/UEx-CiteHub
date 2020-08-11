import asyncio
import functools
import heapq
import itertools
import json
import hashlib
import os
import base64
from pathlib import Path


PASSWORD_HASH_ITERATIONS = 100_000


def pairwise(iterable):
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


def clamp(x, low, high):
    if x < low:
        return low
    if x > high:
        return high
    return x


def map_range(x, old_low, old_high, new_low, new_high):
    return new_low + ((x - old_low) * (new_high - new_low) / (old_high - old_low))


def locked(func):
    lock = asyncio.Lock()

    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
        async with lock:
            return await func(*args, **kwargs)

    return wrapped


def try_load_json(data, path: Path):
    try:
        with path.open(encoding="utf-8") as fd:
            data.update(json.load(fd))
    except FileNotFoundError:
        pass


def try_load_list(path: Path):
    try:
        with path.open(encoding="utf-8") as fd:
            return json.load(fd)
    except FileNotFoundError:
        return []


def save_json(data, path: Path):
    try:
        with path.open("w", encoding="utf-8") as fd:
            return json.dump(data, fd)
    except FileNotFoundError:  # ask for forgiveness, not permission
        path.parent.mkdir(parents=True)
        with path.open("w", encoding="utf-8") as fd:
            return json.dump(data, fd)


def hash_user_pass(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    else:
        salt = base64.b64decode(salt)

    # https://nakedsecurity.sophos.com/2013/11/20/serious-security-how-to-store-your-users-passwords-safely/
    return (
        base64.b64encode(
            hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
            )
        ).decode("ascii"),
        base64.b64encode(salt).decode("ascii"),
    )


def parse_delay(delay):
    if not delay:
        return 0

    delay = delay.lower()

    if delay.endswith("s"):
        return int(delay[:-1])
    if delay.endswith("m"):
        return 60 * int(delay[:-1])
    if delay.endswith("h"):
        return 60 * 60 * int(delay[:-1])
    if delay.endswith("d"):
        return 24 * 60 * 60 * int(delay[:-1])

    return int(delay)


class Heap:
    """Pythonic heap."""

    def __init__(self, iterable=()):
        self._heap = list(iterable)
        heapq.heapify(self._heap)

    def push(self, item):
        heapq.heappush(self._heap, item)

    def pop(self):
        return heapq.heappop(self._heap)

    def peek(self):
        return self._heap[0]

    def __bool__(self):
        return bool(self._heap)
