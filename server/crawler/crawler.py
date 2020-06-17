import abc
import asyncio
import heapq
import json
import logging
import random
import time
from pathlib import Path

from .. import constants, utils
from .scholar import CrawlScholar

MAX_SLEEP = 60

# TODO because every citation is a publication on its own, we probably want a way to determine
#      which of those are our own.
#
# TODO be careful when updating our own publications, it might've been saved previously as a
#      citation (marked as not ours)

# TODO this might be a bit overkill
class _JsonFile:
    def __init__(self, path: Path, data):
        self._path = path
        self._data = data

    def load(self):
        try:
            with self._path.open(encoding='utf-8') as fd:
                data = json.load(fd)
        except FileNotFoundError:
            return

        for key, value in data.items():
            if key in self._data:
                self._data[key] = value
            else:
                # TODO warn about bad key
                pass

    def save(self):
        if not self._path.parent.is_dir():
            self._path.parent.mkdir()

        with self._path.open('w', encoding='utf-8') as fd:
            json.dump(self._data, fd)

    def as_dict(self):
        return self._data.copy()  # no immutable dicts so make a copy

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        assert key in self._data
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data

class _Tasks:
    # A class to namespace all the various tasks
    def __init__(self, root: Path):
        self.scholar = CrawlScholar()

    def set_scholar_url(self, url):
        self.scholar.set_url(url)

    def tasks(self):
        return ((
            self.scholar,
        ))

    def load(self):
        for _task in self.tasks():
            # TODO we probably want to share a common Storage all tasks can reuse
            pass

    def save(self):
        for task in self.tasks():
            # TODO this is a no-op
            task.save()

    def next_task(self):
        return min(self.tasks())

class Crawler:
    # The crawler just runs tasks
    def __init__(self, storage_root: Path):
        self._root = storage_root
        self._crawl_task = None
        self._sources = _JsonFile(self._root / 'external-sources.json', {
            constants.SCHOLAR_PROFILE_URL: '',
        })
        self._tasks = _Tasks(self._root)

    async def _crawl(self):
        while True:
            if not self._tasks:
                await asyncio.sleep(MAX_SLEEP)
                continue

            task = self._tasks.next_task()
            delay = task.remaining_delay()
            if delay > MAX_SLEEP:
                await asyncio.sleep(MAX_SLEEP)
                continue

            await asyncio.sleep(delay)
            # It's fine for task to have changed while we slept, if it did it's a fresh start
            # that we would want to run soon anyway.
            await task.step()

    def get_sources(self):
        return self._sources.as_dict()

    def update_sources(self, sources):
        for key, value in sources.items():
            assert key in self._sources

            value = value.strip()
            if value == self._sources[key]:
                continue  # nothing to do

            # Invalidate task for this key and recreate it under a new storage
            self._sources[key] = value

            # It is possible that we update the sources and not tasks, but very unlikely
            # TODO we do zero error handling but the urls may be wrong here and fail
            if key == constants.SCHOLAR_PROFILE_URL:
                self._tasks.set_scholar_url(value)

    async def __aenter__(self):
        # Sources and tasks will be in sync as we update them, which means there is no need to
        # synchronize the tasks based on the sources we loaded but we still need both to let the
        # user know what sources they have configured.
        self._sources.load()
        self._tasks.load()

        # Crawling is a long-running task we can't block on
        self._crawl_task = asyncio.create_task(self._crawl())
        return self

    async def __aexit__(self, *args):
        self._sources.save()
        self._tasks.save()
        self._crawl_task.cancel()
        try:
            await self._crawl_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception('unhandled exception in crawl task')
        finally:
            self._crawl_task = None