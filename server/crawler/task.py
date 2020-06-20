import abc
import asyncio
import json
import random
import time


DELAY_JITTER_PERCENT = 0.05


class Task(abc.ABC):
    # Every different external source uses its own `Task` for crawling profiles, and the
    # subclasses know how to update the profile data. Every task also has its own profile.
    def __init__(self, root):
        self._root = root
        self._task_file = root / 'task.json'
        self._profile_file = root / 'profile.json'
        self._due = 0

    @abc.abstractmethod
    def _load(self, data):
        raise NotImplementedError

    @abc.abstractmethod
    def _save(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def _step(self, session, profile):
        # Should return the delay needed before calling it again
        raise NotImplementedError

    def load(self):
        try:
            with self._task_file.open(encoding='utf-8') as fd:
                data = json.load(fd)
        except FileNotFoundError:
            return

        delta = data.pop('due') - time.time()
        self._due = asyncio.get_event_loop().time() + delta
        self._load(data)

    def save(self):
        data = self._save()
        delta = self._due - asyncio.get_event_loop().time()
        data['due'] = time.time() + delta

        if not self._task_file.parent.is_dir():
            self._task_file.parent.mkdir()

        with self._task_file.open('w', encoding='utf-8') as fd:
            json.dump(data, fd)

    async def step(self, session, profile):
        delay = await self._step(session, profile)
        if not isinstance(delay, (int, float)):
            raise RuntimeError(f'step returned invalid data: {delay}')

        jitter_range = delay * DELAY_JITTER_PERCENT
        jitter = random.uniform(-jitter_range, jitter_range)
        self._due = asyncio.get_event_loop().time() + delay + jitter

    def remaining_delay(self):
        return self._due - asyncio.get_event_loop().time()

    def __lt__(self, other):
        return self._due < other._due

    def __gt__(self, other):
        return self._due > other._due
