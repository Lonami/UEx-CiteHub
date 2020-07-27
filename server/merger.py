import re
import itertools
import asyncio
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from . import utils

AUTO_DELAY = 24 * 60 * 60
SIMILARITY_THRESHOLD = 0.9

_log = logging.getLogger(__name__)


def similarity(a, b, _words_re=re.compile(r"\w+")):
    # TODO this function can obviously apply other heuristics
    title_a = _words_re.findall(a.name.lower())
    title_b = _words_re.findall(b.name.lower())
    if title_a == title_b:
        return 1.0
    else:
        return 0.0


class MergeCheck:
    def __init__(self, data):
        # {ns: {path: [(related ns, related path)]}}
        self._relations = defaultdict(lambda: defaultdict(list))
        for datum in data:
            merge = Merge(**datum)
            self._relations[merge.ns_a][merge.pub_a].append((merge.ns_b, merge.pub_b))
            self._relations[merge.ns_b][merge.pub_b].append((merge.ns_a, merge.pub_a))

    def get_related(self, namespace, path_name):
        return self._relations[namespace][path_name]


@dataclass
class Merge:
    ns_a: str
    ns_b: str
    pub_a: str
    pub_b: str
    similarity: float


# TODO we need a way to standarize task storages
class Merger:
    # The merger runs automatically or on demand and merges storage information
    def __init__(self, root: Path, storages):
        self._root = root
        self._storages = storages
        self._merge_task = None
        self._force_check = asyncio.Event()

    async def _periodic_merge(self):
        try:
            while True:
                try:
                    self._force_check.clear()
                    await asyncio.wait_for(self._force_check.wait(), AUTO_DELAY)
                except asyncio.TimeoutError:
                    pass
                else:
                    self._force_check.clear()

                _log.info("merging data")
                await self._merge()
                _log.info("merged data")
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("unhandled exception in crawl task")

    async def _merge(self):
        result = []
        for ((ns_a, storage_a), (ns_b, storage_b)) in itertools.combinations(
            self._storages.items(), 2
        ):
            _log.debug("checking merges between %s and %s", ns_a, ns_b)
            for (pub_id_a, pub_id_b) in itertools.product(
                storage_a.user_pub_ids, storage_b.user_pub_ids
            ):
                pub_a = storage_a.load_pub(pub_id_a)
                pub_b = storage_b.load_pub(pub_id_b)
                sim = similarity(pub_a, pub_b)
                if sim >= SIMILARITY_THRESHOLD:
                    result.append(
                        Merge(
                            ns_a=ns_a,
                            ns_b=ns_b,
                            pub_a=pub_a.unique_path_name(),
                            pub_b=pub_b.unique_path_name(),
                            similarity=sim,
                        )
                    )

                for (cit_path_a, cit_path_b) in itertools.product(
                    pub_a.cit_paths or [], pub_b.cit_paths or []
                ):
                    cit_a = storage_a.load_pub(path=Path(cit_path_a))
                    cit_b = storage_b.load_pub(path=Path(cit_path_b))
                    sim = similarity(cit_a, cit_b)
                    if sim >= SIMILARITY_THRESHOLD:
                        result.append(
                            Merge(
                                ns_a=ns_a,
                                ns_b=ns_b,
                                pub_a=cit_path_a,
                                pub_b=cit_path_b,
                                similarity=sim,
                            )
                        )

                # Yielding control to the event loop for every publication pair seems to do
                # a pretty good job, and the web server is able to respond while we do this
                # even if it's pretty CPU intensive (although IO loads may play a big role).
                await asyncio.sleep(0)

        utils.save_json(list(map(asdict, result)), self._root / "merges.json")

    def force_merge(self):
        if self._force_check.is_set():
            return False

        self._force_check.set()
        return True

    def checker(self):
        return MergeCheck(utils.try_load_list(self._root / "merges.json"))

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
