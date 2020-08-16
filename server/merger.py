import re
import itertools
import asyncio
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from . import utils
from .crawler import CRAWLERS

AUTO_DELAY = 24 * 60 * 60
SIMILARITY_THRESHOLD = 0.9

_log = logging.getLogger(__name__)


def similarity(a, b, _words_re=re.compile(r"\w+")):
    # This function can obviously apply more complex heuristics, but in reality this works
    # good enough and it's nearly as simple as we can get while tolerating some differences.
    title_a = _words_re.findall(a.name.lower())
    title_b = _words_re.findall(b.name.lower())
    if title_a == title_b:
        return 1.0
    else:
        return 0.0


class MergeCheck:
    def __init__(self, merges):
        # {source: {path: [(related source, related path)]}}
        self._relations = defaultdict(lambda: defaultdict(list))
        for merge in merges:
            self._relations[merge.source_a][merge.pub_a].append(
                (merge.source_b, merge.pub_b)
            )
            self._relations[merge.source_b][merge.pub_b].append(
                (merge.source_a, merge.pub_a)
            )

    def get_related(self, source, path):
        return self._relations[source][path]


@dataclass
class Merge:
    source_a: str
    source_b: str
    pub_a: str
    pub_b: str
    similarity: float


class Merger:
    # The merger runs automatically or on demand and merges storage information
    def __init__(self, db):
        self._db = db
        self._merge_task = None
        self._force_check = asyncio.Event()

    async def _periodic_merge(self):
        try:
            while True:
                _log.info("merging data")
                # Set the flag so that if someone else tries it will fail
                self._force_check.set()
                await self._merge()
                _log.info("merged data")

                try:
                    self._force_check.clear()
                    await asyncio.wait_for(self._force_check.wait(), AUTO_DELAY)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("unhandled exception in crawl task")

    async def _merge(self):
        for username in await self._db.get_usernames():
            _log.info("checking merges for user %s", username)
            await self._merge_user(username)

    async def _merge_user(self, username):
        result = []
        for (source_a, source_b) in itertools.combinations(CRAWLERS, 2):
            _log.debug("checking merges between %s and %s", source_a, source_b)
            pubs_a = await self._db.get_source_publications(username, source_a)
            pubs_b = await self._db.get_source_publications(username, source_b)
            for (pub_a, pub_b) in itertools.product(pubs_a, pubs_b):
                sim = similarity(pub_a, pub_b)
                if sim >= SIMILARITY_THRESHOLD:
                    result.append(
                        Merge(
                            source_a=source_a,
                            source_b=source_b,
                            pub_a=pub_a.path,
                            pub_b=pub_b.path,
                            similarity=sim,
                        )
                    )

                # Yielding control to the event loop for every publication pair seems to do
                # a pretty good job, and the web server is able to respond while we do this
                # even if it's pretty CPU intensive (although IO loads may play a big role).
                await asyncio.sleep(0)

        await self._db.save_merges(username, result)

    def force_merge(self):
        if self._force_check.is_set():
            return False

        self._force_check.set()
        return True

    async def __aenter__(self):
        _log.info("entering merger")
        self._merge_task = asyncio.create_task(self._periodic_merge())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        _log.info("exiting merger")
        self._merge_task.cancel()
        try:
            await self._merge_task
        except asyncio.CancelledError:
            pass
        finally:
            self._merge_task = None
