import abc
import asyncio
import heapq
import json
import logging
import random
import time
from pathlib import Path

from aiohttp import ClientSession

from .scholar import CrawlScholar
from .. import constants, utils


MAX_SLEEP = 60
_log = logging.getLogger(__name__)

# TODO because every citation is a publication on its own, we probably want a way to determine
#      which of those are our own.
#
# TODO be careful when updating our own publications, it might've been saved previously as a
#      citation (marked as not ours)

class _Tasks:
    # A class to namespace all the various tasks
    def __init__(self, root: Path):
        self._root = root
        self._scholar = CrawlScholar(root / 'scholar')

    def set_scholar_url(self, url):
        self._scholar.set_url(url)

    def tasks(self):
        return ((
            self._scholar,
        ))

    def load(self):
        _log.info('loading tasks')
        for task in self.tasks():
            _log.debug('loading task %s', task.__class__.__name__)
            task.load()

    def save(self):
        _log.info('saving tasks')
        for task in self.tasks():
            _log.debug('saving task %s', task.__class__.__name__)
            task.save()

    def next_task(self):
        return min(self.tasks())

class Crawler:
    # The crawler just runs tasks
    def __init__(self, storage_root: Path):
        self._root = storage_root
        self._crawl_task = None
        self._sources_file = self._root / 'external-sources.json'
        self._sources = {
            constants.SCHOLAR_PROFILE_URL: '',
        }
        self._tasks = _Tasks(self._root)
        self._crawl_notify = asyncio.Event()
        self._client_session = ClientSession()

    async def _crawl(self):
        while True:
            task = self._tasks.next_task()
            delay = task.remaining_delay()
            if delay > MAX_SLEEP:
                await self._wait_notify(MAX_SLEEP)
                continue

            if await self._wait_notify(delay):
                continue  # tasks changed so we don't want to step on any

            _log.debug('stepping task %s', task.__class__.__name__)
            await task.step(self._client_session)

    async def _wait_notify(self, delay):
        try:
            self._crawl_notify.clear()
            await asyncio.wait_for(self._crawl_notify.wait(), delay)
            _log.debug('got notification to retry crawling')
            return True
        except asyncio.TimeoutError:
            return False

    def get_sources(self):
        return self._sources.copy()

    def update_sources(self, sources):
        for key, value in sources.items():
            assert key in self._sources

            value = value.strip()
            if value == self._sources[key]:
                _log.debug('source %s has not changed', key)
                continue  # nothing to do

            # Invalidate task for this key and recreate it under a new storage
            _log.info('updating source %s to %s', key, value)
            self._sources[key] = value

            # It is possible that we update the sources and not tasks, but very unlikely
            # TODO we do zero error handling but the urls may be wrong here and fail
            if key == constants.SCHOLAR_PROFILE_URL:
                self._tasks.set_scholar_url(value)

        self._crawl_notify.set()

    async def __aenter__(self):
        # Sources and tasks will be in sync as we update them, which means there is no need to
        # synchronize the tasks based on the sources we loaded but we still need both to let the
        # user know what sources they have configured.
        _log.info('entering crawler')
        await self._client_session.__aenter__()

        utils.try_load_json(self._sources, self._sources_file)
        self._tasks.load()

        # Crawling is a long-running task we can't block on
        self._crawl_task = asyncio.create_task(self._crawl())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        _log.info('exiting crawler')
        utils.save_json(self._sources, self._sources_file)
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
            await self._client_session.__aexit__(exc_type, exc_val, exc_tb)
