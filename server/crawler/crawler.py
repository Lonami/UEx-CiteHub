import abc
import asyncio
import heapq
import json
import logging
import random
import time
from pathlib import Path

from aiohttp import ClientSession

from .aminer import CrawlArnetMiner
from .scholar import CrawlScholar
from .msacademics import CrawlAcademics
from .ieeexplore import CrawlExplore
from .researchgate import CrawlResearchGate
from .. import utils


MAX_SLEEP = 60
_log = logging.getLogger(__name__)


class _Tasks:
    # A class to namespace all the various tasks
    def __init__(self, root: Path):
        self._root = root
        self._tasks = {}
        for cls in (
                CrawlScholar,
                CrawlAcademics,
                CrawlArnetMiner,
                CrawlExplore,
                CrawlResearchGate,
        ):
            if cls.namespace() in self._tasks:
                raise ValueError(
                    f'two different tasks have the same namespace "{cls.namespace()}": '
                    f'{self._tasks[cls.namespace()].__class__.__name__} and {cls.__name__}'
                )
            else:
                self._tasks[cls.namespace()] = cls(root)

    def tasks(self):
        return self._tasks.values()

    def set_field(self, namespace, key, value):
        self._tasks[namespace].set_field(key, value)

    def load(self):
        _log.info('loading tasks')
        for task in self.tasks():
            _log.debug('loading task %s', task.namespace())
            task.load()

    def save(self):
        _log.info('saving tasks')
        for task in self.tasks():
            _log.debug('saving task %s', task.namespace())
            task.save()

    def next_task(self):
        return min(self.tasks())

class Crawler:
    # The crawler just runs tasks
    def __init__(self, storage_root: Path):
        self._root = storage_root
        self._crawl_task = None
        self._tasks = _Tasks(self._root)
        # Contains the required fields for the various tasks (persisted only for the frontend)
        # {namespace: {key, value}}
        self._sources_file = self._root / 'external-sources.json'
        self._sources = {task.namespace(): {} for task in self._tasks.tasks()}
        self._crawl_notify = asyncio.Event()
        self._client_session = ClientSession()

    async def _crawl(self):
        try:
            while True:
                task = self._tasks.next_task()
                delay = task.remaining_delay()
                if delay > MAX_SLEEP:
                    await self._wait_notify(MAX_SLEEP)
                    continue

                if await self._wait_notify(delay):
                    continue  # tasks changed so we don't want to step on any

                _log.debug('stepping task %s', task.namespace())
                await task.step(self._client_session)
                task.save()
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception('unhandled exception in crawl task')

    async def _wait_notify(self, delay):
        try:
            self._crawl_notify.clear()
            await asyncio.wait_for(self._crawl_notify.wait(), delay)
            _log.debug('got notification to retry crawling')
            return True
        except asyncio.TimeoutError:
            return False

    def get_source_fields(self):
        fields = []
        for task in self._tasks.tasks():
            for key, description in task.fields().items():
                fields.append({
                    'key': f'{task.namespace()}.{key}',
                    'description': description,
                    'value': self._sources[task.namespace()].get(key),
                })

        return fields

    def update_source_fields(self, sources):
        print(sources)
        for key, value in sources.items():
            namespace, key = key.split('.')
            value = value.strip()

            if value == self._sources[namespace].get(key):
                _log.debug('source %s has not changed', key)
                continue  # nothing to do

            _log.info('updating source %s to %s', key, value)
            self._sources[namespace][key] = value

            # It is possible that we update the sources and not tasks, but very unlikely
            # TODO we do zero error handling but the urls may be wrong here and fail
            self._tasks.set_field(namespace, key, value)

        self.save()
        self._crawl_notify.set()

    def save(self):
        utils.save_json(self._sources, self._sources_file)
        self._tasks.save()

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
        self.save()
        self._crawl_task.cancel()
        try:
            await self._crawl_task
        except asyncio.CancelledError:
            pass
        finally:
            self._crawl_task = None
            await self._client_session.__aexit__(exc_type, exc_val, exc_tb)
