"""
API keys: https://msr-apis.portal.azure-api.net/
API methods: https://msr-apis.portal.azure-api.net/Products/project-academic-knowledge
Tutorial and attributes: https://docs.microsoft.com/en-us/azure/cognitive-services/academic-knowledge/queryexpressionsyntax

Website: https://academic.microsoft.com/home

For some reason, querying the public API they offer with "AA.AuId" as returned by their "private"
API yields no results on publications. Using the name query "AA.AuN" does seem to return all of
them, but names are not as reliable as using the author Id so we would rather avoid them.

This doesn't make much sense (why would querying the name find publications but not the Id?).

Instead of using the API we're meant to use, we pretend to be the website and perform the same
API calls as it. This is the most-reliable method.
"""
import urllib.parse
from typing import Generator, List, Tuple
import logging

from ...storage import Author, Publication
from ..task import Task
from dataclasses import dataclass
from datetime import datetime
from ..step import Step


def new_filtered_dict(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}


_log = logging.getLogger(__name__)


class Academics:
    def __init__(
        self,
        session,
        api_key,
        base_url="https://api.labs.cognitive.microsoft.com/academic/v1.0/",
    ):
        self._session = session
        self._headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Accept": "application/json",
        }
        self._base_url = base_url

    async def interpret(self, query):
        url = self._base_url + "interpret"
        async with self._session.get(
            url, params={"query": query}, headers=self._headers
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise ValueError(f"HTTP {resp.status} fetching {url}")

    async def evaluate(
        self,
        expr: str,
        *,
        model: str = None,
        count: int = None,
        offset: int = None,
        orderby: str = None,
        attributes: str = None,
    ):
        """
        Parameters
            expr
                A query expression that specifies which entities should be returned.

                For details, see
                https://docs.microsoft.com/en-us/academic-services/project-academic-knowledge/reference-query-expression-syntax.

                Query expressions should be in lowercase with no special characters.

                Single value:       Field='query'
                Exact single value: Field=='query'
                Prefix value:       Field='value'...
                Range:              Field>=3 (or) Field=[2010, 2012)
                Date:               Field='2020-02-20'
                And/or queries:     And(Or(Field='a', Field='b'), Field='c')
                Composite fields:   Composite(Comp.Field='a')

                Examples

                    Composite(AA.AuN='mike smith')

            model
                Name of the model that you wish to query. Currently, the value defaults to "latest".

            count
                Number of results to return.

            offset
                Index of the first result to return.

            orderby
                Name of an attribute that is used for sorting the entities. Optionally,
                ascending/descending can be specified. The format is: `name:asc` or `name:desc`.

            attributes
                A comma delimited list that specifies the attribute values that are included in the
                response. Attribute names are case-sensitive.

                For details, see
                https://docs.microsoft.com/en-us/academic-services/project-academic-knowledge/reference-entity-attributes.

        Notes
            Querying for a field that does not exist (e.g. `AuN`) results in error 500.

            Duplicate attributes are fine.
        """
        url = self._base_url + "evaluate"
        async with self._session.get(
            url,
            params=new_filtered_dict(
                expr=expr,
                model=model,
                count=count,
                offset=offset,
                orderby=orderby,
                attributes=attributes,
            ),
            headers=self._headers,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise ValueError(f"HTTP {resp.status} fetching {url}")


def author_id_from_url(url):
    url = urllib.parse.urlparse(url)
    assert url.netloc == "academic.microsoft.com", f"unexpected domain {url.netloc}"
    parts = url.path.split("/")
    assert parts[1] == "profile", f"unexpected path {parts[1]}"
    return parts[2]


async def fetch_profile(session, iden):
    # Note: the author ID from here is not the one we actually expect and using it in the real API will fail
    async with session.post(
        "https://academic.microsoft.com/api/user/profile", json=iden
    ) as resp:
        return await resp.json()


def adapt_profile(profile) -> Author:
    entity = profile["entity"]
    inst = entity.get("i", {})
    return Author(
        # An author may have actually published papers under a different ID
        id=str(entity["id"]),
        full_name=entity["dn"],
        extra={
            "profile-id": entity["profileId"],
            "latitude": inst.get("lat"),
            "longitude": inst.get("lon"),
            "institution": inst.get("dn"),
            "institution-desc": inst.get("d"),
            "institution-logo": inst.get("iurl"),
            "alternate-name": entity.get("an"),
            "web-profiles": entity.get("w"),
        },
    )


_FETCH_SIZE = 10  # capped to 10


def _expr_query(expr, query, offset):
    return {
        "query": query,  # seems needed to get original papers when fetching citations
        "queryExpression": expr,
        "filters": [],
        "orderBy": 0,
        "skip": offset,
        "sortAscending": True,
        "take": _FETCH_SIZE,
        "includeCitationContexts": True,
        # 'profileId': '<uuid4 from expr>',
    }


async def fetch_publications(session, expr, query, offset):
    async with session.post(
        "https://academic.microsoft.com/api/search",
        json=_expr_query(expr, query, offset),
    ) as resp:
        return await resp.json()


def _adapt_paper(paper) -> Publication:
    publisher = paper["v"]
    _sources = paper["s"]  # source type 0 and 1 has link
    authors = paper["a"]

    try:
        year = datetime.fromisoformat(publisher["publishedDate"]).year
    except ValueError:
        year = None
        _log.warning(
            "publisher date is not in iso format: %s", publisher["publishedDate"]
        )

    pub_id = str(paper["id"])
    return Publication(
        id=pub_id,
        name=paper["dn"],
        authors=[
            Author(
                full_name=author["dn"],
                extra={"institutions": [inst["dn"] for inst in author["i"]],},
            )
            for author in authors
        ],
        year=year,
        ref=f"https://academic.microsoft.com/paper/{pub_id}",
        extra={
            "description": paper["d"],
            "publisher": publisher.get(
                "displayName"
            ),  # id 0 won't have this field and the rest empty
            "volume": publisher["volume"] or None,
            "issue": publisher["issue"] or None,
            "first-page": publisher["firstPage"] or None,
            "last-page": publisher["lastPage"] or None,
            "date": publisher["publishedDate"],
        },
    )


def adapt_publications(data) -> Generator[Publication, None, None]:
    paper_results = data["pr"]
    for paper in paper_results:
        yield _adapt_paper(paper["paper"])


async def fetch_citations(session, expr, query, offset):
    async with session.post(
        "https://academic.microsoft.com/api/edpsearch/citations",
        json=_expr_query(expr, query, offset),
    ) as resp:
        return await resp.json()


def adapt_citations(data) -> Generator[Tuple[Publication, List[str]], None, None]:
    for paper in data["rpi"]:
        yield _adapt_paper(paper["paper"]), [
            paper["paperId"] for paper in paper["originalPaperLinks"]
        ]


class Stage:
    @dataclass
    class FetchQueries:
        INDEX = 0

    @dataclass
    class FetchPublications:
        INDEX = 1
        pub_count: int
        pub_expr: str
        cit_expr: str
        query: str
        offset: int = 0

    @dataclass
    class FetchCitations:
        INDEX = 2
        cit_expr: str
        query: str
        offset: int = 0


class CrawlAcademics(Task):
    Stage = Stage

    @classmethod
    def namespace(cls):
        return "academics"

    @classmethod
    def initial_stage(cls):
        return Stage.FetchQueries()

    @classmethod
    def fields(cls):
        return {
            "url": 'Navigate to <a href="https://academic.microsoft.com/home">Microsoft Academic\'s '
            "home</a> and search for your profile. Click on it when you find it and copy the "
            "URL."
        }

    @classmethod
    def validate_field(self, key, value):
        assert key == "url", f"invalid key {key}"
        author_id_from_url(value)  # will raise (fail validation) on bad value

    @classmethod
    async def _step(cls, values, stage, session) -> Step:
        user_author_id = author_id_from_url(values["url"])

        if isinstance(stage, Stage.FetchQueries):
            data = await fetch_profile(session, user_author_id)
            return Step(
                delay=1,
                stage=Stage.FetchPublications(
                    pub_count=data["entity"]["pc"],
                    pub_expr=data["publicationsExpression"],
                    cit_expr=data["citedByExpression"],
                    query=data["entity"]["dn"],
                ),
            )

        elif isinstance(stage, Stage.FetchPublications):
            data = await fetch_publications(
                session, stage.pub_expr, stage.query, stage.offset
            )

            self_publications = list(adapt_publications(data))
            offset = stage.offset + len(self_publications)
            if offset >= stage.pub_count or not self_publications:
                return Step(
                    delay=30 * 60,
                    stage=Stage.FetchCitations(
                        cit_expr=stage.cit_expr, query=stage.query,
                    ),
                    self_publications=self_publications,
                )
            else:
                return Step(
                    delay=2 * 60,
                    stage=Stage.FetchPublications(
                        pub_count=stage.pub_count,
                        pub_expr=stage.pub_expr,
                        cit_expr=stage.cit_expr,
                        query=stage.query,
                        offset=offset,
                    ),
                    self_publications=self_publications,
                )

        elif isinstance(stage, Stage.FetchCitations):
            data = await fetch_citations(
                session, stage.cit_expr, stage.query, stage.offset
            )
            cit_count = data["sr"]["t"]

            citations = {}
            offset = stage.offset
            for cit, cites_ids in adapt_citations(data):
                offset += 1
                for cites_id in cites_ids:
                    citations.setdefault(cites_id, []).append(cit)

            if offset >= cit_count or not citations:
                return Step(delay=30 * 60, stage=cls.initial_stage())
            else:
                return Step(
                    delay=2 * 60,
                    stage=Stage.FetchCitations(
                        cit_expr=stage.cit_expr, query=stage.query, offset=offset,
                    ),
                )
