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
from typing import Generator, List, Tuple, Optional

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
        known_pub_ids: Optional[List[str]] = None
        offset: int = 0

    @dataclass
    class FetchCitations:
        INDEX = 1
        missing_pub_ids: List[str]
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

    @classmethod
    def validate_field(self, key, value):
        assert key == "url", f"invalid key {key}"
        author_id_from_url(value)  # will raise (fail validation) on bad value

    @classmethod
    async def _step(cls, values, stage, session) -> Step:
        user_author_id = author_id_from_url(values["url"])
        miner = ArnetMiner(session)

        if isinstance(stage, Stage.FetchPublications):
            data = await miner.search_publications(user_author_id, stage.offset)

            pub_count = data["keyValues"]["total"]
            self_publications = list(adapt_publications(data))
            known_pub_ids = (stage.known_pub_ids or []) + [
                # Don't bother saving those without citations to save on requests
                p.id
                for p in self_publications
                if p.extra["cit-count"] != 0
            ]

            offset = stage.offset + len(self_publications)
            if offset >= pub_count or not self_publications:
                delay = 30 * 60
                stage = Stage.FetchCitations(missing_pub_ids=known_pub_ids)
            else:
                delay = 5 * 60
                stage = Stage.FetchPublications(
                    known_pub_ids=known_pub_ids, offset=offset
                )

            return Step(delay=delay, stage=stage, self_publications=self_publications,)

        elif isinstance(stage, Stage.FetchCitations):
            if not stage.missing_pub_ids:
                _log.debug("checked all publications")
                return Step(delay=24 * 60 * 60, stage=cls.initial_stage())

            pub_id = stage.missing_pub_ids[0]
            data = await miner.search_cited_by(pub_id, stage.cit_offset)

            # The listed citations are less than the found count for some reason; however it's
            # unlikely that they are greater (so if we previously fetched 0 we don't bother
            # making additional network requests).
            cit_count = data["keyValues"]["total"]

            citations = list(adapt_publications(data))
            cit_offset = stage.cit_offset + len(citations)

            if cit_offset >= cit_count or not citations:
                delay = 30 * 60
                stage = Stage.FetchCitations(missing_pub_ids=stage.missing_pub_ids[1:])
            else:
                delay = 5 * 60
                stage = Stage.FetchCitations(
                    missing_pub_ids=stage.missing_pub_ids, cit_offset=cit_offset
                )

            return Step(delay=delay, stage=stage, citations={pub_id: citations},)
