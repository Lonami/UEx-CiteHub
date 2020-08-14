import asyncio
import codecs
import random
import re
import logging
import urllib.parse
from typing import AsyncGenerator, Optional, List

import aiohttp
import bs4

from ...storage import Author, Publication
from ..crawler import Crawler
from dataclasses import dataclass
from ..step import Step

_log = logging.getLogger(__name__)

_PAGE_CACHE = True  # for debugging purposes

_HOST = "https://scholar.google.com"
_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US",
    "Cookie": "NID=203=vlT7m1DDdoWUifNI20xIboEeWZhbdMDcJbPP52iWy2-DPUww4USzNMKUqZCHn4HJCjBmACqej7LzqA1mkpVx4rtVCvAl1JZrw9rbMHOarMA_oyxzhC_zBEcs-Yr_YFQjjP-mM9doFIUKgb0HXjJB4eiSF6FGY7dxKME-VAi27f2DuOpBSuO4yKsYYTVT9Ek9oBscWCwdgCLxwwwAOdAPbz0F; GSP=A=bl17_A:CPTS=1588243844:LM=1588243844:S=ENX3yc3St4asJnMT; 1P_JAR=2020-04-30-09; SID=wQdzQm6xVVbBRFM6p2wvHyg94TF1IKRqi_HswbQpwHSm7CSfwLY0jBLU8iybA0M3lshdew.; __Secure-3PSID=wQdzQm6xVVbBRFM6p2wvHyg94TF1IKRqi_HswbQpwHSm7CSfQeP6FtOiPTlz9FP9_-4B0Q.; HSID=AglcJQqcUSuMMXjvJ; SSID=AlQxjS1laOR7CJFWO; APISID=bStucEx6CbBCatNj/AoFMuVqLoVzwmbvcu; SAPISID=Md2nISlNjMpqb6C-/Avf8qIllpoKlHDv4i; __Secure-HSID=AglcJQqcUSuMMXjvJ; __Secure-SSID=AlQxjS1laOR7CJFWO; __Secure-APISID=bStucEx6CbBCatNj/AoFMuVqLoVzwmbvcu; __Secure-3PAPISID=Md2nISlNjMpqb6C-/Avf8qIllpoKlHDv4i; SIDCC=AJi4QfEwefW2gbjEmtXdANO43xvGO5y-gZc1mHtETsqIERUvQ7ThoSe0icypAZtMYXpiWufMWE4",
    "Host": "scholar.google.com",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/7046A194A",
}

_PAGE_SIZE = 100

_URL_SEARCH_AUTHOR = "/citations?view_op=search_authors&hl=en&mauthors={}"
_URL_AUTHOR = f"/citations?hl=en&user={{}}&pagesize={_PAGE_SIZE}"
_URL_PUBLICATION = "/citations?view_op=view_citation&hl=en&citation_for_view={}"

_USER_RE = re.compile(r"user=([^&]+)")
_CITATION_RE = re.compile(r"citation_for_view=([\w-]*:[\w-]*)")


if _PAGE_CACHE:
    # copy-paste of non-cache version
    async def _get_page(
        session: aiohttp.ClientSession, path: str = "", url: str = None
    ) -> bs4.BeautifulSoup:
        import hashlib
        from pathlib import Path

        if not url:
            url = _HOST + path

        path = Path("cache/scholar")
        path.mkdir(parents=True, exist_ok=True)
        cache = path / hashlib.sha256(url.encode("utf-8")).hexdigest()

        if cache.is_file():
            with cache.open(encoding="utf-8") as fd:
                html = fd.read()
        else:
            async with session.get(url, headers=_HEADERS) as resp:
                resp.raise_for_status()
                html = (await resp.text()).replace("\xa0", " ")

            with cache.open("w", encoding="utf-8") as fd:
                fd.write(html)

        if 'id="gs_captcha_f"' in html:
            raise RuntimeError("hit captcha while crawling google scholar")

        return bs4.BeautifulSoup(html, "html.parser")


else:

    async def _get_page(
        session: aiohttp.ClientSession, path: str = "", url: str = None
    ) -> bs4.BeautifulSoup:
        if not url:
            url = _HOST + path

        async with session.get(url, headers=_HEADERS) as resp:
            resp.raise_for_status()
            html = (await resp.text()).replace("\xa0", " ")
            if 'id="gs_captcha_f"' in html:
                raise RuntimeError("hit captcha while crawling google scholar")

            return bs4.BeautifulSoup(html, "html.parser")


def _analyze_basic_author_soup(soup) -> dict:
    name_soup = soup.find("h3", "gs_ai_name")
    name = name_soup.text
    author_id = _USER_RE.search(name_soup.find("a")["href"]).group(1)
    url_picture = _HOST + "/citations?view_op=medium_photo&user={}".format(author_id)
    affiliation = soup.find("div", "gs_ai_aff").text

    email = soup.find("div", "gs_ai_eml").text
    if email:
        email = email.replace("Verified email at ", "")

    interests = [i.text.strip() for i in soup.find_all("a", "gs_ai_one_int")]

    cited_by = soup.find("div", "gs_ai_cby").text
    if cited_by:
        cited_by = int(cited_by.replace("Cited by ", ""))
    else:
        cited_by = None

    return {
        "name": name,
        "id": author_id,
        "url_picture": url_picture,
        "affiliation": affiliation,
        "email": email,
        "interests": interests,
        "cited-by": cited_by,
    }


def _analyze_basic_publication_soup(soup) -> Publication:
    name = soup.find("a", "gsc_a_at").text
    authors, publisher = soup.find("td", "gsc_a_t")("div", "gs_gray")
    authors = [author.strip() for author in authors.text.split(",")]
    publisher = publisher.text

    ref = _HOST + soup.find("a", "gsc_a_at")["data-href"]
    iden = _CITATION_RE.search(ref).group(1)
    cite_count = soup.find(class_="gsc_a_ac").text
    if cite_count:
        cite_count = int(cite_count)

    year = soup.find(class_="gsc_a_h").text
    if year:
        year = int(year)

    return Publication(
        id=iden,
        name=name,
        authors=[Author(full_name=author) for author in authors],
        year=year,
        ref=ref,
        extra={"cite-count": cite_count, "publisher": publisher,},
    )


def parse_author_profile(soup) -> (Author, List[Publication], bool):
    iden = soup.find("div", id="gsc_md_fol-bdy").find("input", {"name": "user"})[
        "value"
    ]
    name = soup.find("div", id="gsc_prf_in").text
    url_picture = soup.find("img", id="gsc_prf_pup-img").src

    email = soup.find("div", "gsc_prf_il").text
    if email:
        email = email.replace("Verified email at ", "")

    affiliation = soup.find("div", class_="gsc_prf_il").text
    interests = [i.text.strip() for i in soup.find_all("a", class_="gsc_prf_inta")]

    indices = soup.find_all("td", class_="gsc_rsb_std")
    if indices:
        cited_by = int(indices[0].text)
        cited_by5y = int(indices[1].text)
        hindex = int(indices[2].text)
        hindex5y = int(indices[3].text)
        i10index = int(indices[4].text)
        i10index5y = int(indices[5].text)
    else:
        cited_by = None
        cited_by5y = None
        hindex = None
        hindex5y = None
        i10index = None
        i10index5y = None

    cites_per_year = dict(
        zip(
            (int(y.text) for y in soup.find_all("span", class_="gsc_g_t")),
            (int(c.text) for c in soup.find_all("span", class_="gsc_g_al")),
        )
    )

    coauthors = []
    for row in soup.find_all("span", class_="gsc_rsb_a_desc"):
        coauthors.append(
            {
                "id": _USER_RE.search(row.find("a")["href"]).group(1),
                "name": row.find(tabindex=-1).text,
                "affiliation": row.find(class_="gsc_rsb_a_ext").text,
            }
        )

    publications, has_offset = parse_author_profile_publications(soup)

    return (
        Author(
            id=iden,
            full_name=name,
            extra={
                "url_picture": url_picture,
                "affiliation": affiliation,
                "email": email,
                "interests": interests,
                "cited-by": cited_by,
                "cited_by5y": cited_by5y,
                "hindex": hindex,
                "hindex5y": hindex5y,
                "i10index": i10index,
                "i10index5y": i10index5y,
                "cites-per-year": cites_per_year,
                "coauthors": coauthors,
            },
        ),
        publications,
        has_offset,
    )


def parse_author_profile_publications(soup) -> (List[Publication], bool):
    publications = []
    for row in soup.find_all("tr", class_="gsc_a_tr"):
        publications.append(_analyze_basic_publication_soup(row))

    has_offset = "disabled" not in soup.find("button", id="gsc_bpf_more").attrs
    return publications, has_offset


def _parse_year(date):
    if date:
        matches = re.findall(r"\d{4}", date)
        if matches:
            return int(matches[0])
        else:
            _log.warning("date had no year %s", date)


def parse_publication(soup) -> (Publication, str):
    iden = soup.find("input", id="gsc_vcd_cid")["value"]
    title = soup.find("div", id="gsc_vcd_title").text
    authors = None
    date = None
    journal = None
    volume = None
    issue = None
    page_range = None
    publisher = None
    abstract = None
    citations_url = None

    for row in soup.find("div", id="gsc_vcd_table").children:
        key = row.find("div", class_="gsc_vcd_field").text
        val = row.find("div", class_="gsc_vcd_value").text
        if key == "Authors":
            authors = list(map(str.strip, val.split(",")))
        elif key == "Publication date":
            date = val
        elif key == "Journal":
            journal = val
        elif key == "Volume":
            volume = val
        elif key == "Issue":
            issue = val
        elif key == "Pages":
            page_range = val
        elif key == "Publisher":
            publisher = val
        elif key == "Description":
            abstract = val
        elif key == "Total citations":
            citations_url = row.find("a")["href"]

    return (
        Publication(
            id=iden,
            name=title,
            authors=[Author(full_name=author) for author in authors],
            year=_parse_year(date),
            ref=f"https://scholar.google.com/citations?view_op=view_citation&citation_for_view={iden}",
            extra={
                "name": title,
                "authors": authors,
                "date": date,
                "journal": journal,
                "volume": volume,
                "issue": issue,
                "page_range": page_range,
                "publisher": publisher,
                "abstract": abstract,
            },
        ),
        citations_url,
    )


def parse_citations(soup) -> (List[Publication], Optional[str]):
    citations = []
    for row in soup.find_all("div", "gs_or"):
        a_val = row.find(class_="gs_a").text.split("-")[0]
        abstract = row.find(class_="gs_rs")
        title = row.find("h3")
        title_ref = title.find("a")
        citations.append(
            Publication(
                name=title.text,
                authors=[
                    Author(full_name=author.strip()) for author in a_val.split(",")
                ],
                ref=title_ref["href"] if title_ref else None,
                extra={"abstract": abstract.text if abstract else None},
            )
        )

    if soup.find(class_="gs_ico gs_ico_nav_next"):
        path = soup.find(class_="gs_ico gs_ico_nav_next").parent["href"]
        next_url = _HOST + path
    else:
        next_url = None

    return citations, next_url


def author_id_from_url(url):
    url = urllib.parse.urlparse(url)
    assert url.netloc == "scholar.google.com", f"unexpected domain {url.netloc}"
    assert url.path == "/citations", f"unexpected path {url.path}"
    query = urllib.parse.parse_qs(url.query)
    return query["user"][0]


PROFILE_DELAY = 5 * 60
PUBLICATION_DELAY = 60 * 60
CITATION_DELAY = 5 * 60


class Stage:
    @dataclass
    class FetchFirst:
        INDEX = 0

    @dataclass
    class FetchPublications:
        INDEX = 1
        known_pub_ids = List[str]

    @dataclass
    class FetchSinglePublication:
        INDEX = 2
        known_pub_ids = List[str]
        offset: int = 0

    @dataclass
    class FetchCitations:
        INDEX = 3
        known_pub_ids = List[str]
        offset: int
        cit_url: str


class CrawlScholar(Crawler):
    Stage = Stage

    @classmethod
    def namespace(cls):
        return "scholar"

    @classmethod
    def fields(cls):
        return {
            "url": 'Navigate to <a href="https://scholar.google.com/citations'
            "?view_op=search_authors\">Google Scholar's profiles search</a> and search for "
            "your profile. Click on it when you find it and copy the URL."
        }

    @classmethod
    def validate_field(self, key, value):
        assert key == "url", f"invalid key {key}"
        author_id_from_url(value)  # will raise (fail validation) on bad value

    @classmethod
    async def _step(cls, values, stage, session) -> Step:
        user_author_id = author_id_from_url(values["url"])

        if isinstance(stage, Stage.FetchFirst):
            soup = await _get_page(session, _URL_AUTHOR.format(user_author_id))
            self_author, self_publications, pubs_remain = parse_author_profile(soup)
            known_pub_ids = [p.id for p in self_publications]

            if pubs_remain:
                return Step(
                    delay=PROFILE_DELAY,
                    stage=Stage.FetchPublications(known_pub_ids=known_pub_ids),
                    authors=[self_author],
                    self_publications=self_publications,
                )
            else:
                return Step(
                    delay=PUBLICATION_DELAY,
                    stage=Stage.FetchSinglePublication(known_pub_ids=known_pub_ids),
                    authors=[self_author],
                    self_publications=self_publications,
                )

        elif isinstance(stage, Stage.FetchPublications):
            soup = await _get_page(
                session,
                _URL_AUTHOR.format(user_author_id)
                + f"&cstart={len(stage.known_pub_ids)}",
            )
            self_publications, pubs_remain = parse_author_profile_publications(soup)
            known_pub_ids = stage.known_pub_ids + [p.id for p in self_publications]

            if pubs_remain:
                return Step(
                    delay=PROFILE_DELAY,
                    stage=Stage.FetchPublications(known_pub_ids=known_pub_ids),
                    self_publications=self_publications,
                )
            else:
                return Step(
                    delay=PUBLICATION_DELAY,
                    stage=Stage.FetchSinglePublication(known_pub_ids=known_pub_ids),
                    self_publications=self_publications,
                )

        elif isinstance(stage, Stage.FetchSinglePublication):
            if stage.offset >= len(stage.known_pub_ids):
                return Step()

            pub_id = stage.known_pub_ids[stage.offset]
            soup = await _get_page(session, _URL_PUBLICATION.format(pub_id),)
            pub, cit_url = parse_publication(soup)

            if cit_url:
                return Step(
                    delay=CITATION_DELAY,
                    stage=Stage.FetchCitations(
                        known_pub_ids=stage.known_pub_ids,
                        offset=stage.offset,
                        cit_url=cit_url,
                    ),
                    self_publications=[pub],
                )
            else:
                return Step(
                    delay=PUBLICATION_DELAY,
                    stage=Stage.FetchSinglePublication(
                        known_pub_ids=stage.known_pub_ids, offset=stage.offset + 1
                    ),
                    self_publications=[pub],
                )

        elif isinstance(stage, Stage.FetchCitations):
            soup = await _get_page(session, url=stage.cit_url)
            citations, cit_url = parse_citations(soup)

            pub_id = stage.known_pub_ids[stage.offset]

            if cit_url:
                return Step(
                    delay=CITATION_DELAY,
                    stage=Stage.FetchCitations(
                        known_pub_ids=stage.known_pub_ids,
                        offset=stage.offset,
                        cit_url=cit_url,
                    ),
                    citations={pub_id: citations},
                )
            else:
                return Step(
                    delay=PUBLICATION_DELAY,
                    stage=Stage.FetchSinglePublication(
                        known_pub_ids=stage.known_pub_ids, offset=stage.offset + 1
                    ),
                    citations={pub_id: citations},
                )
