import abc
import asyncio
import logging
import random
import time


DELAY_JITTER_PERCENT = 0.05


@abc.ABC
class Task:
    def __init__(self):
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

    def load(self, data):
        delta = data.pop('due') - time.time()
        self._due = asyncio.get_event_loop().time() + delta
        self._load(data)

    def save(self):
        data = self._save()
        delta = self._due - asyncio.get_event_loop().time()
        data['due'] = time.time() + delta
        return data

    async def step(self, session, profile):
        delay = await self._step(session, profile)
        if not isinstance(delay, (int, float)):
            raise RuntimeError(f'step returned invalid data: {delay}')

        jitter_range = delay * DELAY_JITTER_PERCENT
        jitter = random.uniform(-jitter_range, jitter_range)
        self._due = asyncio.get_event_loop().time() + delay + jitter

    async def ready(self):
        return asyncio.get_event_loop().time() >= self._due

    def __lt__(self, other):
        return self._due < other._due

    def __gt__(self, other):
        return self._due > other._due



class Crawler:
    def __init__(self, file, profile):
        self._file = file
        self._profile = profile
        self._task = None

    async def _crawl(self):
        while True:
            pass

    async def __aenter__(self):
        self._task = asyncio.create_task(self._crawl())
        return self

    async def __aexit__(self, *args):
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception('unhandled exception in crawl task')
        finally:
            self._task = None
