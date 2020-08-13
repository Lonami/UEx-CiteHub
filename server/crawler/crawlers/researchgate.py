"""
Possibly no API, but https://www.researchgate.net/profile/ has info.

See https://www.researchgate.net/profile/<profile name>

Requires `Rg-Request-Token` and `sid` cookie to work (otherwise it's a 403).

Getting the token and sid: https://www.researchgate.net/refreshToken?c=rgcf-e98aaa8e8f7cad0f
The last part comes from a script in the main site.

The HTML however is a mess, full of nested `<div>` and classes used for style purposes.
"""
import urllib.parse
import re
import bs4
import logging
from typing import Generator, List
from ...storage import Author, Publication
from ..crawler import Crawler
from dataclasses import dataclass
from ..step import Step


_log = logging.getLogger(__name__)


async def fetch_token_sid(session):
    async with session.get(f"https://www.researchgate.net/refreshToken") as resp:
        for header in resp.headers.getall("set-cookie"):
            if header.startswith("sid="):
                sid = header[4 : header.index(";")]
                break
        else:
            raise ValueError("sid cookie not found")

        rg_token = (await resp.json())["requestToken"]
        return rg_token, sid


async def fetch_author(session, author_id):
    async with session.get(f"https://www.researchgate.net/profile/{author_id}") as resp:
        resp.raise_for_status()
        return bs4.BeautifulSoup(await resp.text(), "html.parser")


async def fetch_citations(session, rg_token, sid, pub_id, offset):
    async with session.post(
        f"https://www.researchgate.net/lite.PublicationDetailsLoadMore.getCitationsByOffset.html"
        f"?publicationUid={pub_id}&offset={offset}",
        headers={"Rg-Request-Token": rg_token, "Cookie": f"sid={sid}",},
    ) as resp:
        return bs4.BeautifulSoup(await resp.text(), "html.parser")


def _find_year(soup):
    date = soup.find(class_="nova-v-publication-item__meta-data-item")
    if date:
        matches = re.findall(r"\d{4}", date.text)
        if matches:
            return int(matches[0])
        else:
            _log.warning("found meta with no date %s", date)


def adapt_publications(soup) -> Generator[Publication, None, None]:
    for card in soup.find(id="publications").parent.find_all(
        class_="nova-o-stack__item"
    ):
        a = card.find(itemprop="headline").find("a")
        iden = a["href"].split("/")[-1].split("_")[0]
        title = a.text
        authors = [span.text for span in card.find_all(itemprop="name")]
        year = _find_year(card)
        yield Publication(
            id=iden,
            name=title,
            authors=[Author(full_name=name) for name in authors],
            year=year,
            ref=a["href"],
        )


def adapt_citations(soup):
    for item in soup.find_all(class_="nova-v-citation-item"):
        a = item.find(class_="nova-v-publication-item__title").find("a")
        iden = a["href"].split("/")[-1].split("_")[0]
        title = a.text

        authors = []
        author_list = item.find(class_="nova-v-publication-item__person-list")
        for li in author_list.find_all("li"):
            a = li.find("a")
            authors.append(Author(id=a["href"].split("/")[-1], full_name=a.text))

        year = _find_year(item)

        abstract = item.find(class_="nova-v-publication-item__description")
        if abstract:
            abstract = abstract.text.replace("\n", "")

        yield Publication(
            id=iden,
            name=title,
            authors=authors,
            year=year,
            ref=a["href"],
            extra={"abstract": abstract,},
        )


def author_id_from_url(url):
    url = urllib.parse.urlparse(url)
    assert url.netloc == "www.researchgate.net", f"unexpected domain {url.netloc}"
    parts = url.path.split("/")
    assert parts[1] == "profile", f"unexpected path {parts[1]}"
    return parts[2]


class Stage:
    @dataclass
    class FetchPublications:
        INDEX = 0

    @dataclass
    class FetchToken:
        INDEX = 1
        known_pub_ids: List[str]

    @dataclass
    class FetchCitations:
        INDEX = 2
        rg_token: str
        sid: str
        missing_pub_ids: List[str]
        cit_offset: int = 0


class CrawlResearchGate(Crawler):
    Stage = Stage

    @classmethod
    def namespace(cls):
        return "researchgate"

    @classmethod
    def initial_stage(cls):
        return Stage.FetchPublications()

    @classmethod
    def fields(cls):
        return {
            "url": 'Navigate to <a href="https://www.researchgate.net/search">ResearchGate\'s '
            "search</a> and search for your profile. Click on it when you find it and copy "
            "the URL."
        }

    @classmethod
    def validate_field(self, key, value):
        assert key == "url", f"invalid key {key}"
        author_id_from_url(value)  # will raise (fail validation) on bad value

    @classmethod
    async def _step(cls, values, stage, session) -> Step:
        user_author_id = author_id_from_url(values["url"])

        if isinstance(stage, Stage.FetchPublications):
            soup = await fetch_author(session, user_author_id)
            self_publications = list(adapt_publications(soup))

            return Step(
                delay=1,
                stage=Stage.FetchToken(known_pub_ids=[p.id for p in self_publications]),
                self_publications=self_publications,
            )

        elif isinstance(stage, Stage.FetchToken):
            rg_token, sid = await fetch_token_sid(session)
            return Step(
                delay=10 * 60,
                stage=Stage.FetchCitations(
                    rg_token=rg_token, sid=sid, missing_pub_ids=stage.known_pub_ids
                ),
            )

        elif isinstance(stage, Stage.FetchCitations):
            if not stage.missing_pub_ids:
                return Step(delay=24 * 60 * 60, stage=cls.initial_stage())

            pub_id = stage.missing_pub_ids[0]

            soup = await fetch_citations(
                session, stage.rg_token, stage.sid, pub_id, stage.cit_offset
            )

            citations = list(adapt_citations(soup))
            if citations:
                return Step(
                    delay=10 * 60,
                    stage=Stage.FetchCitations(
                        rg_token=stage.rg_token,
                        sid=stage.sid,
                        missing_pub_ids=stage.missing_pub_ids,
                        cit_offset=stage.cit_offset + len(citations),
                    ),
                    citations={pub_id: citations},
                )
            else:
                return Step(
                    delay=2 * 60,
                    stage=Stage.FetchCitations(
                        rg_token=stage.rg_token,
                        sid=stage.sid,
                        missing_pub_ids=stage.missing_pub_ids[1:],
                    ),
                    citations={pub_id: citations},
                )
