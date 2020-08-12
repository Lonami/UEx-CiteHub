import abc
import asyncio
import heapq
import json
import logging
import random
import time
import datetime
from pathlib import Path

from aiohttp import ClientSession

from .crawlers import CRAWLERS
from .. import utils


MAX_SLEEP = 60
_log = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, db, *, enabled: bool):
        self._db = db
        self._enabled = enabled
        self._crawl_task = None
        self._crawl_notify = asyncio.Event()
        self._client_session = ClientSession()

    async def _crawl(self):
        try:
            while True:
                source = await self._db.next_source_task()
                delay = source.due - time.time()
                if delay > MAX_SLEEP:
                    await self._wait_notify(MAX_SLEEP)
                    continue

                if await self._wait_notify(delay):
                    continue  # tasks changed so we don't want to step on any

                _log.debug("stepping source task %s/%s", source.owner, source.key)

                # TODO should these checks be here or in task? do crawlers expect empty values?
                if source.values_json:
                    values = json.loads(source.values_json)
                else:
                    values = {}
                if source.task_json:
                    state = json.loads(source.task_json)
                else:
                    state = CRAWLERS[source.key].initial_stage()

                # TODO except step error
                step, due = await CRAWLERS[source.key].step(
                    values=values, state=state, session=self._client_session
                )
                # TODO begin transaction to save the produced values in the step and due in a transaction
                _log.debug(
                    "stepped source task %s/%s, next at %d",
                    source.owner,
                    source.key,
                    due,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("unhandled exception in crawl task")

    async def _wait_notify(self, delay):
        try:
            self._crawl_notify.clear()
            await asyncio.wait_for(self._crawl_notify.wait(), delay)
            _log.debug("got notification to retry crawling")
            return True
        except asyncio.TimeoutError:
            return False

    # TODO get/update source fields probably don't belong here (and with less confusing names?)
    async def get_source_fields(self, username):
        fields = []
        values = await self._db.get_source_values(username)
        for key, crawler in CRAWLERS.items():
            fields.append(
                {
                    "key": key,
                    "fields": {
                        k: {"description": desc, "value": values[key].get(k) or "",}
                        for k, desc in crawler.fields().items()
                    },
                }
            )

        return fields

    async def update_source_fields(self, username, sources):
        from aiohttp import web

        raise web.HTTPForbidden()  # TODO
        if not self._enabled:
            return

        errors = []
        for key, value in sources.items():
            namespace, key = key.split(".")
            value = value.strip()

            if value == self._sources[namespace].get(key):
                _log.debug("source %s has not changed", key)
                continue  # nothing to do

            _log.info("updating source %s to %s", key, value)

            # It is possible that we update the tasks and not the sources due
            # to a race-condition, but very unlikely.
            try:
                self._tasks.set_field(namespace, key, value)
            except Exception as e:
                _log.exception("failed to set %s.%s", namespace, key)
                errors.append(
                    {"namespace": namespace, "key": key, "reason": str(e),}
                )
            else:
                self._sources[namespace][key] = value

        self.save()
        self._crawl_notify.set()
        return {"errors": errors}

    async def __aenter__(self):
        # Sources and tasks will be in sync as we update them, which means there is no need to
        # synchronize the tasks based on the sources we loaded but we still need both to let the
        # user know what sources they have configured.
        _log.info("entering crawler")

        # Crawling is a long-running task we can't block on
        if self._enabled:
            await self._client_session.__aenter__()
            self._crawl_task = asyncio.create_task(self._crawl())

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        _log.info("exiting crawler")
        if not self._enabled:
            return

        self._crawl_task.cancel()
        try:
            await self._crawl_task
        except asyncio.CancelledError:
            pass
        finally:
            self._crawl_task = None
            await self._client_session.__aexit__(exc_type, exc_val, exc_tb)
