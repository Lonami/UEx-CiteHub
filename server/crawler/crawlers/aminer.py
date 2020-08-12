"""
https://www.aminer.cn/ requires login to view additional info.

Trying to login on aminer.cn seems to be a bit buggy.

They seem to have some (private?) APIs:
* apiv2.aminer.cn/magic
* api.aminer.cn/api

The network tab in web browsers displays a lot of interesting XHR.
"""
import urllib.parse
import logging
from dataclasses import dataclass
from typing import Generator, List, Tuple

from ...storage import Author, Publication
from ..step import Step
from ..task import Task

_log = logging.getLogger(__name__)


class ArnetMiner:
    def __init__(self, session, base_url="https://apiv2.aminer.cn/magic"):
        self._session = session
        self._headers = {"Accept": "application/json"}
        self._base_url = base_url

    async def search_person(self, query):
        return await self.query(
            {
                "action": "person7.SearchPersonWithDSL",
                "parameters": {
                    "offset": 0,
                    "size": 20,
                    "query": query,
                    "aggregation": ["gender", "h_index", "nation", "lang"],
                },
                "schema": {
                    "person": [
                        "id",
                        "name",
                        "name_zh",
                        "avatar",
                        "tags",
                        "is_follow",
                        "num_view",
                        "num_follow",
                        "is_upvoted",
                        "num_upvoted",
                        "is_downvoted",
                        "bind",
                        {
                            "profile": [
                                "position",
                                "position_zh",
                                "affiliation",
                                "affiliation_zh",
                                "org",
                            ]
                        },
                        {
                            "indices": [
                                "hindex",
                                "gindex",
                                "pubs",
                                "citations",
                                "newStar",
                                "risingStar",
                                "activity",
                                "diversity",
                                "sociability",
                            ]
                        },
                    ]
                },
            }
        )

    async def get_stats(self, author_id):
        return await self.query(
            {"action": "person.GetPersonPubsStats", "parameters": {"ids": [author_id]}}
        )

    async def search_publications(self, author_id, offset):
        return await self.query(
            {
                "action": "person.GetPersonPubs",
                "parameters": {
                    "offset": offset,
                    "size": 100,
                    "sorts": ["!year"],
                    "ids": [author_id],
                    "searchType": "all",
                },
                "schema": {
                    "publication": [
                        "id",
                        "year",
                        "title",
                        "title_zh",
                        "authors._id",
                        "authors.name",
                        "authors.name_zh",
                        "num_citation",
                        "venue.info.name",
                        "venue.volume",
                        "venue.info.name_zh",
                        "venue.issue",
                        "pages.start",
                        "pages.end",
                        "lang",
                        "pdf",
                        "doi",
                        "urls",
                        "versions",
                    ]
                },
            }
        )

    async def search_cited_by(self, paper_id, offset):
        return await self.query(
            {
                "action": "publication.CitedByPid",
                "parameters": {"offset": offset, "size": 100, "ids": [paper_id]},
            }
        )

    async def query(self, data):
        url = self._base_url
        # Probably uses and returns a list so many can be invoked at once
        async with self._session.post(url, json=[data], headers=self._headers) as resp:
            if resp.status == 200:
                return (await resp.json())["data"][0]
            else:
                raise ValueError(
                    f"HTTP {resp.status} fetching {url}:\n{await resp.text()}"
                )


def author_id_from_url(url):
    url = urllib.parse.urlparse(url)
    assert url.netloc == "www.aminer.cn", f"unexpected domain {url.netloc}"
    parts = url.path.split("/")
    assert parts[1] == "profile", f"unexpected path {parts[1]}"
    return parts[3]


def adapt_publications(data) -> Generator[Publication, None, None]:
    def maybe_int(value):
        # Sometimes we get "ArticleNo.22" in the page which is not a page number
        return int(value) if value and value.isdigit() else None

    # If it has 0 keyValues then the items key will be missing
    for pub in data.get("items", ()):
        pub_id = pub["id"]
        yield Publication(
            id=pub_id,
            name=pub["title"],
            authors=[
                Author(
                    id=author.get("id"),
                    full_name=author["name"],
                    extra={"organization": author.get("org"),},
                )
                for author in pub["authors"]
            ],
            year=pub["year"] or None,  # may be 0, we prefer None
            ref=f"https://www.aminer.cn/pub/{pub_id}",
            extra={
                "cit-count": pub["num_citation"],  # used later
                "doi": pub.get("doi"),
                "language": pub.get("lang") or None,
                "first-page": maybe_int(pub.get("pages", {}).get("start")),
                "last-page": maybe_int(pub.get("pages", {}).get("end")),
                "urls": pub.get("urls"),
                "issue": pub.get("venue", {}).get("issue") or None,
                "volume": pub.get("venue", {}).get("volume") or None,
                "publisher": pub.get("venue", {}).get("info", {}).get("name"),
                "pdf": pub.get("pdf") or None,
            },
        )


class Stage:
    @dataclass
    class FetchPublications:
        INDEX = 0
        offset: int = 0

    @dataclass
    class FetchCitations:
        INDEX = 1
        pub_offset: int = 0
        cit_offset: int = 0


class CrawlArnetMiner(Task):
    Stage = Stage

    @classmethod
    def namespace(cls):
        return "aminer"

    @classmethod
    def initial_stage(cls):
        return Stage.FetchPublications()

    @classmethod
    def fields(cls):
        return {
            "url": 'Navigate to <a href="https://www.aminer.cn/">AMiner\'s home</a> and search for '
            "your profile. Click on it when you find it and copy the URL."
        }

    def set_field(self, key, value):
        assert key == "url", f"invalid key {key}"
        self._storage.user_author_id = None if not value else author_id_from_url(value)
        self._storage.user_pub_ids = []
        self._due = 0

    @classmethod
    async def _step(cls, values, stage, session) -> Step:
        if not self._storage.user_author_id:
            return Step(delay=24 * 60 * 60, stage=None)

        miner = ArnetMiner(session)

        if isinstance(stage, Stage.FetchPublications):
            data = await miner.search_publications(
                self._storage.user_author_id, stage.offset
            )

            pub_count = data["keyValues"]["total"]
            self_publications = list(adapt_publications(data))

            offset = stage.offset + len(self_publications)
            if offset >= pub_count or not self_publications:
                delay = 30 * 60
                stage = Stage.FetchCitations()
            else:
                delay = 5 * 60
                stage = Stage.FetchPublications(offset=offset)

            return Step(delay=delay, stage=stage, self_publications=self_publications,)

        elif isinstance(stage, Stage.FetchCitations):
            if stage.pub_offset >= len(self._storage.user_pub_ids):
                _log.debug("checked all publications")
                return Step(delay=24 * 60 * 60, stage=self.initial_stage(),)

            pub_id = self._storage.user_pub_ids[stage.pub_offset]
            pub = self._storage.load_pub(pub_id)

            if pub.extra["cit-count"] == 0:
                _log.debug("no citations to check for this publication")
                return Step(
                    delay=1, stage=Stage.FetchCitations(pub_offset=stage.pub_offset + 1)
                )

            data = await miner.search_cited_by(pub_id, stage.cit_offset)

            # The listed citations are less than the found count for some reason; however it's
            # unlikely that they are greater (so if we previously fetched 0 we don't bother
            # making additional network requests).
            cit_count = data["keyValues"]["total"]

            citations = list(adapt_publications(data))
            cit_offset = stage.cit_offset + len(citations)

            if cit_offset >= cit_count or not citations:
                delay = 30 * 60
                stage = Stage.FetchCitations(pub_offset=stage.pub_offset + 1)
            else:
                delay = 5 * 60
                stage = Stage.FetchCitations(
                    pub_offset=stage.pub_offset, cit_offset=cit_offset
                )

            return Step(delay=delay, stage=stage, citations={pub_id: citations},)
