"""
See https://app.dimensions.ai.

May need to query certain endpoints manually, such as

    https://app.dimensions.ai/discover/publication/results.json?cursor=<base64>&and_facet_researcher=ur.<id>.<n>

Both the cookie and X-CSRF-Token headers may also need to be necessary, with referer:

    https://app.dimensions.ai/discover/publication?and_facet_researcher=ur.<id>.<n>
"""
import urllib.parse
import json
from typing import Generator, Tuple, Optional
from ...storage import Author, Publication
from ..task import Task
from dataclasses import dataclass
from ..step import Step


def _get_name_arguments(first, last):
    return dict(full_name=f"{first} {last}".strip(), first_name=first, last_name=last,)


async def fetch_author(session, author_id):
    # Alternative paths:
    # * facets/publication.json
    # * facets/publication/researcher/{author_id}/box.json
    async with session.get(
        "https://app.dimensions.ai/panel/publication/author/preview.json",
        params={"and_facet_researcher": author_id},
    ) as resp:
        return await resp.json()


def adapt_authors(data) -> Generator[Author, None, None]:
    for author in data["data"]:
        author = author["details"]

        yield Author(
            id=author["id"],
            *_get_name_arguments(author["first_name"], author["last_name"]),
            extra={
                "organization": author["current_org_name"],
                "country": author["current_org_country"],
            },
        )


async def fetch_publications(session, author_id, cursor):
    async with session.get(
        "https://app.dimensions.ai/discover/publication/results.json",
        params={"and_facet_researcher": author_id, "cursor": cursor or "*"},
    ) as resp:
        return await resp.json()


def _pub_ref(pub_id):
    return f"https://app.dimensions.ai/details/publication/{pub_id}"


def adapt_publications(data) -> Generator[Publication, None, None]:
    for pub in data["docs"]:
        affiliations = json.loads(pub["affiliations_json"])
        yield Publication(
            id=pub["id"],
            name=pub["title"],
            authors=[
                Author(
                    id=a["researcher_id"] or None,
                    *_get_name_arguments(a["first_name"], a["last_name"]),
                )
                for a in affiliations
            ],
            year=pub["pub_year"],
            ref=_pub_ref(pub["id"]),
        )


async def fetch_citations(session, pub_id, cursor):
    async with session.get(
        "https://app.dimensions.ai/details/sources/publication/related/publication/cited-by.json",
        params={"id": pub_id, "cursor": cursor or "*"},
    ) as resp:
        return await resp.json()


def adapt_citations(data) -> Generator[Publication, None, None]:
    for pub in data["docs"]:
        first_page, last_page = map(int, pub["pages"].split("-"))
        yield Publication(
            id=pub["id"],
            name=pub["title"],
            authors=[
                Author(full_name=author) for author in pub["author_list"].split(", ")
            ],
            year=pub["pub_year"],
            ref=_pub_ref(pub["id"]),
            extra={
                "editors": pub.get("editor_list", "").split(", ") or None,
                "journal": pub["journal_title"],
                "book": pub.get("book_title"),
                "pdf": pub["linkout_oa"],
                "publisher": pub["publisher_source"],
                "doi": pub["doi"],
                "first-page": first_page,
                "last-page": last_page,
            },
        )


def author_id_from_url(url):
    url = urllib.parse.urlparse(url)
    assert url.netloc == "app.dimensions.ai", f"unexpected domain {url.netloc}"
    assert url.path == "/discover/publication", f"unexpected path {url.path}"
    query = urllib.parse.parse_qs(url.query)
    return query["and_facet_researcher"][0]


class Stage:
    @dataclass
    class FetchAuthors:
        INDEX = 0

    @dataclass
    class FetchPublications:
        INDEX = 1
        cursor: Optional[str] = None

    @dataclass
    class FetchCitations:
        INDEX = 2
        offset: int = 0
        cursor: Optional[str] = None


class CrawlDimensions(Task):
    Stage = Stage

    @classmethod
    def namespace(cls):
        return "dimensions"

    @classmethod
    def initial_stage(cls):
        return Stage.FetchAuthors()

    @classmethod
    def fields(cls):
        return {
            "url": 'Navigate to <a href="https://app.dimensions.ai/discover/publication">'
            "Dimension's search</a> and search for publications with your name. Open one "
            "of the publications and click on your name in the author list"
            "search for publications with your name. Click on your name in the list of "
            "authors of one of the publications, and copy that final URL."
        }

    def set_field(self, key, value):
        assert key == "url", f"invalid key {key}"
        self._storage.user_author_id = None if not value else author_id_from_url(value)
        self._storage.user_pub_ids = []
        self._due = 0

    async def _step(self, stage, session) -> Step:
        if not self._storage.user_author_id:
            return Step(delay=24 * 60 * 60, stage=None)

        if isinstance(stage, Stage.FetchAuthors):
            data = await fetch_author(session, self._storage.user_author_id)
            authors = list(adapt_authors(data))
            return Step(
                delay=10 * 60, stage=Stage.FetchPublications(), authors=authors,
            )

        elif isinstance(stage, Stage.FetchPublications):
            data = await fetch_publications(
                session, self._storage.user_author_id, stage.cursor
            )
            cursor = data["next_cursor"]
            self_publications = list(adapt_publications(data))

            if cursor:
                return Step(
                    delay=5 * 60,
                    stage=Stage.FetchPublications(cursor=cursor),
                    self_publications=self_publications,
                )
            else:
                return Step(
                    delay=10 * 60,
                    stage=Stage.FetchCitations(),
                    self_publications=self_publications,
                )

        elif isinstance(stage, Stage.FetchCitations):
            if stage.offset >= len(self._storage.user_pub_ids):
                return Step(delay=24 * 60 * 60, stage=self.initial_stage(),)

            pub_id = self._storage.user_pub_ids[stage.offset]

            data = await fetch_citations(session, pub_id, stage.cursor)
            cursor = data["next_cursor"]

            citations = list(adapt_citations(data))

            if cursor:
                return Step(
                    delay=5 * 60,
                    stage=Stage.FetchCitations(offset=stage.offset, cursor=cursor),
                    citations={pub_id: citations},
                )
            else:
                return Step(
                    delay=10 * 60,
                    stage=Stage.FetchCitations(offset=stage.offset + 1),
                    citations={pub_id: citations},
                )
