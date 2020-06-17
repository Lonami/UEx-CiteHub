import abc
import asyncio
import heapq
import logging
import random
import time

from . import utils


DELAY_JITTER_PERCENT = 0.05
MAX_SLEEP = 60


class Task(abc.ABC):
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

    def remaining_delay(self):
        return self._due - asyncio.get_event_loop().time()

    def __lt__(self, other):
        return self._due < other._due

    def __gt__(self, other):
        return self._due > other._due


class Crawler:
    # The crawler just runs tasks
    def __init__(self):
        self._crawl_task = None
        self._tasks = []

    async def _crawl(self):
        while True:
            if not self._tasks:
                await asyncio.sleep(MAX_SLEEP)
                continue

            task = self._tasks[0]
            delay = task.remaining_delay()
            if delay > MAX_SLEEP:
                await asyncio.sleep(MAX_SLEEP)
                continue

            await asyncio.sleep(delay)
            await task.step()
            self._tasks.sort()

    def add_task(self, task):
        # Only one class per type (subclasses are considered different)
        for i, t in enumerate(self._tasks):
            if type(t) == type(task):
                self._tasks[i] = task
                break
        else:
            self._tasks.append(task)

        self._tasks.sort()

    async def __aenter__(self):
        self._crawl_task = asyncio.create_task(self._crawl())
        return self

    async def __aexit__(self, *args):
        self._crawl_task.cancel()
        try:
            await self._crawl_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception('unhandled exception in crawl task')
        finally:
            self._crawl_task = None
