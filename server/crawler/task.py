import abc
import asyncio
import json
import random
import time
from typing import Mapping

from ..storage import Storage


DELAY_JITTER_PERCENT = 0.05


# TODO tasks are a bit messy because each stores its resume state in its own way
# ideally we'd have a rust-like enum to ensure that only the data we need is saved
# (and we don't have garbage) which maybe we could return to automate the process
#
# similar for set_url which resets due and stage, maybe the tasks should define what
# they require so it can be better generalized and also have a "start state" which
# could be defined through decorators or something
class Task(abc.ABC):
    # Every different external source uses its own `Task` for crawling profiles, and the
    # subclasses know how to update the profile data. Every task also has its own profile.
    def __init__(self, root):
        self._root = root / self.namespace()
        self._task_file = self._root / 'task.json'
        self._storage = Storage(self._root)  # TODO maybe storage should have the task too?
        self._due = 0

    @classmethod
    @abc.abstractmethod
    def namespace(cls) -> str:
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def fields(cls) -> Mapping[str, str]:
        # Should return `{field key: field description}`` on required user-provided fields.
        # The description may contain HTML tags.
        raise NotImplementedError

    def set_field(self, key, value):
        raise NotImplementedError

    @abc.abstractmethod
    def _load(self, data):
        raise NotImplementedError

    @abc.abstractmethod
    def _save(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def _step(self, session):
        # Should return the delay needed before calling it again
        # TODO probably don't call step if there's no author id in storage
        raise NotImplementedError

    def load(self):
        self._storage.load()

        try:
            with self._task_file.open(encoding='utf-8') as fd:
                data = json.load(fd)
        except FileNotFoundError:
            return

        delta = data.pop('due') - time.time()
        self._due = asyncio.get_event_loop().time() + delta
        self._load(data)

    def save(self):
        self._storage.save()

        data = self._save()
        delta = self._due - asyncio.get_event_loop().time()
        data['due'] = time.time() + delta

        if not self._task_file.parent.is_dir():
            self._task_file.parent.mkdir()

        with self._task_file.open('w', encoding='utf-8') as fd:
            json.dump(data, fd)

    async def step(self, session):
        delay = await self._step(session)
        if not isinstance(delay, (int, float)):
            raise TypeError(f'step returned invalid data: {delay}')

        jitter_range = delay * DELAY_JITTER_PERCENT
        jitter = random.uniform(-jitter_range, jitter_range)
        self._due = asyncio.get_event_loop().time() + delay + jitter

    def remaining_delay(self):
        return self._due - asyncio.get_event_loop().time()

    def __lt__(self, other):
        return self._due < other._due

    def __gt__(self, other):
        return self._due > other._due
