"""
An asyncio and modern alternative to https://pypi.org/project/scholarly/.
"""
import asyncio
import codecs
import random
import re
import urllib.parse
from typing import AsyncGenerator

import aiohttp
import bs4

from ..datamodel import Source, Author, Publication
from ..crawler import Task

_HOST = 'https://scholar.google.com'
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

_URL_SEARCH_AUTHOR = '/citations?view_op=search_authors&hl=en&mauthors={}'
_URL_AUTHOR = f'/citations?hl=en&user={{}}&pagesize={_PAGE_SIZE}'
_URL_PUBLICATION = '/citations?view_op=view_citation&hl=en&citation_for_view={}'

_USER_RE = re.compile(r'user=([^&]+)')
_CITATION_RE = re.compile(r'citation_for_view=([\w-]*:[\w-]*)')


async def _get_page(session: aiohttp.ClientSession, path: str = '', url: str = None) -> bs4.BeautifulSoup:
    if not url:
        url = _HOST + path

    try:
        with open('cache/' + url.replace('/', '_')) as fd:
            return bs4.BeautifulSoup(fd.read(), 'html.parser')
    except OSError:
        pass

    # sucks but hopefully avoids captcha
    await asyncio.sleep(5 + random.uniform(0, 5))
    while True:
        async with session.get(url, headers=_HEADERS) as resp:
            resp.raise_for_status()
            html = (await resp.text()).replace('\xa0', ' ')
            if 'id="gs_captcha_f"' in html:
                input('After solving the captcha above press enter to continue')

            else:
                with open('cache/' + url.replace('/', '_'), 'w') as fd:
                    fd.write(html)
                return bs4.BeautifulSoup(html, 'html.parser')


def _analyze_basic_author_soup(soup) -> dict:
    name_soup = soup.find('h3', 'gs_ai_name')
    name = name_soup.text
    author_id = _USER_RE.search(name_soup.find('a')['href']).group(1)
    url_picture = _HOST + '/citations?view_op=medium_photo&user={}'.format(author_id)
    affiliation = soup.find('div', 'gs_ai_aff').text

    email = soup.find('div', 'gs_ai_eml').text
    if email:
        email = email.replace('Verified email at ', '')

    interests = [i.text.strip() for i in soup.find_all('a', 'gs_ai_one_int')]

    cited_by = soup.find('div', 'gs_ai_cby').text
    if cited_by:
        cited_by = int(cited_by.replace('Cited by ', ''))
    else:
        cited_by = None

    return {
        'name': name,
        'id': author_id,
        'url_picture': url_picture,
        'affiliation': affiliation,
        'email': email,
        'interests': interests,
        'cited-by': cited_by,
    }

def _analyze_basic_publication_soup(soup) -> dict:
    name = soup.find('a', 'gsc_a_at').text
    authors, publisher = soup.find('td', 'gsc_a_t')('div', 'gs_gray')
    authors = authors.text
    publisher = publisher.text

    id_citations = _CITATION_RE.search(soup.find('a', 'gsc_a_at')['data-href']).group(1)
    cites = soup.find(class_='gsc_a_ac').text
    if cites:
        cites = int(cites)

    year = soup.find(class_='gsc_a_h').text
    if year:
        year = int(year)

    return {
        'id': id_citations,
        'name': name,
        'cites': cites,
        'year': year,
        'authors': authors,
        'publisher': publisher,
    }


def parse_author_profile(soup):
    # TODO maybe remove most parsing if we don't care about the data.
    #      it's in the git history if we ever need it anyway.
    #
    # TODO this should probably return a proper Profile
    name = soup.find('div', id='gsc_prf_in').text
    url_picture = soup.find('img', id='gsc_prf_pup-img').src

    email = soup.find('div', 'gsc_prf_il').text
    if email:
        email = email.replace('Verified email at ', '')

    affiliation = soup.find('div', class_='gsc_prf_il').text
    interests = [i.text.strip() for i in soup.find_all('a', class_='gsc_prf_inta')]

    indices = soup.find_all('td', class_='gsc_rsb_std')
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

    cites_per_year = dict(zip(
        (int(y.text) for y in soup.find_all('span', class_='gsc_g_t')),
        (int(c.text) for c in soup.find_all('span', class_='gsc_g_al'))
    ))

    coauthors = []
    for row in soup.find_all('span', class_='gsc_rsb_a_desc'):
        coauthors.append({
            'id': _USER_RE.search(row.find('a')['href']).group(1),
            'name': row.find(tabindex=-1).text,
            'affiliation': row.find(class_='gsc_rsb_a_ext').text,
        })

    publications, offset = parse_author_profile_publications(soup)

    data = {
        'name': name,
        'url_picture': url_picture,
        'affiliation': affiliation,
        'email': email,
        'interests': interests,
        'cited-by': cited_by,
        'cited_by5y': cited_by5y,
        'hindex': hindex,
        'hindex5y': hindex5y,
        'i10index': i10index,
        'i10index5y': i10index5y,
        'cites-per-year': cites_per_year,
        'coauthors': coauthors,
        'publications': publications,
    }
    return data, offset


def parse_author_profile_publications(soup):
    publications = []
    for row in soup.find_all('tr', class_='gsc_a_tr'):
        publications.append(_analyze_basic_publication_soup(row))

    offset = 'disabled' not in soup.find('button', id='gsc_bpf_more').attrs
    return publications, offset


def parse_publication(soup):
    title = soup.find('div', id='gsc_vcd_title').text
    authors = None
    date = None
    journal = None
    volume = None
    issue = None
    page_range = None
    publisher = None
    abstract = None
    citations_url = None

    for row in soup.find('div', id='gsc_vcd_table').children:
        key = row.find('div', class_='gsc_vcd_field').text
        val = row.find('div', class_='gsc_vcd_value').text
        if key == 'Authors':
            authors = list(map(str.strip, val.split(',')))
        elif key == 'Publication date':
            date = val
        elif key == 'Journal':
            journal = val
        elif key == 'Volume':
            volume = val
        elif key == 'Issue':
            issue = val
        elif key == 'Pages':
            page_range = val
        elif key == 'Publisher':
            publisher = val
        elif key == 'Description':
            abstract = val
        elif key == 'Total citations':
            citations_url = row.find('a')['href']

    data = {
        'name': title,
        'authors': authors,
        'date': date,
        'journal': journal,
        'volume': volume,
        'issue': issue,
        'page_range': page_range,
        'publisher': publisher,
        'abstract': abstract,
    }

    return data, citations_url


def parse_citations(soup):
    citations = []
    for row in soup.find_all('div', 'gs_or'):
        a_val = row.find(class_='gs_a').text.split('-')[0]
        abstract = row.find(class_='gs_rs')
        citations.append({
            'name': row.find('h3').text,
            'authors': list(map(str.strip, a_val.split(','))),
            'abstract': abstract.text if abstract else None,
        })

    if soup.find(class_='gs_ico gs_ico_nav_next'):
        path = soup.find(class_='gs_ico gs_ico_nav_next').parent['href']
        next_url = _HOST + path
    else:
        next_url = None

    return citations, next_url


# TODO remove these?
def adapt_author(author: dict) -> Author:
    name_parts = author['name'].split(maxsplit=1)

    return Author(
        iden=author['id'],
        source=Source.GOOGLE_SCHOLAR,
        first_name=name_parts[0],
        last_name=name_parts[1] if len(name_parts) > 1 else '',
        aliases=[],
    )


def adapt_publication(pub: dict, author: Author) -> Publication:
    return Publication(
        iden=pub['id'],
        author=author,
        source=Source.GOOGLE_SCHOLAR,
        title=author['name'],
        year=pub['year'],
        cited_by=None  # TODO
    )


def author_id_from_url(url):
    url = urllib.parse.urlparse(url)
    assert url.netloc == 'scholar.google.com'
    assert url.path == '/citations'
    query = urllib.parse.parse_qs(url.query)
    return query['user'][0]


PROFILE_DELAY = 5 * 60
PUBLICATION_DELAY = 60 * 60
CITATION_DELAY = 5 * 60
FULL_DELAY = 24 * 60 * 60


class CrawlScholar(Task):
    def __init__(self, author_id):
        super().__init__()
        self._author_id = author_id
        self._stage = 0  # int
        self._offset = None  # int
        self._cit_offset = None  # url

    def _load(self, data):
        self._author_id = data['author_id']
        self._stage = data['stage']
        self._offset = data['offset']
        self._cit_offset = data['cit-offset']

    def _save(self):
        return {
            'author_id': self._author_id,
            'stage': self._stage,
            'offset': self._offset,
            'cit-offset': self._cit_offset,
        }

    async def _step(self, session, profile):
        # Initial load
        if self._stage == 0:
            soup = await _get_page(session, _URL_AUTHOR.format(self._author_id))
            data, pubs_remain = parse_author_profile(soup)
            if pubs_remain:
                self._stage = 1
                self._offset = _PAGE_SIZE
                return PROFILE_DELAY
            else:
                self._offset = -1
                return self._next_pub_offset(profile)

            # TODO once we use a Profile we could have a .update() method to avoid pitfalls
            profile.full_name = data['name']
            profile.publications = data['publications']

        # Main page but with more results (offset advances by page size)
        elif self._stage == 1:
            soup = await _get_page(session, _URL_AUTHOR.format(self._author_id) + f'&cstart={self._offset}')
            data, pubs_remain = parse_author_profile_publications(soup)
            if pubs_remain:
                # stay in stage 1
                self._offset += _PAGE_SIZE
                return PROFILE_DELAY
            else:
                self._offset = -1
                return self._next_pub_offset(profile)  # stage 2 or 4

            profile.publications.extend(data)

        # Publications, one by one (offset is an index into the publications)
        elif self._stage == 2:
            soup = await _get_page(session, _URL_PUBLICATION.format(profile.publications[self._offset].id))
            data, cit_url = parse_publication(soup)

            if cit_url:
                self._stage = 3
                self._cit_offset = cit_url
                return CITATION_DELAY
            else:
                return self._next_pub_offset(profile)  # stage 2 or 4

        # Parsing citation pages
        elif self._stage == 3:
            soup = await _get_page(session, url=self._cit_offset)
            data, cit_url = parse_citations(soup)

            if cit_url:
                # stay in stage 3
                self._cit_offset = cit_url
                return CITATION_DELAY
            else:
                return self._next_pub_offset(profile)  # stage 2 or 4

    def _next_pub_offset(self, profile):
        self._offset += 1
        if self._offset >= len(profile.publications):
            self._stage = 0
            return FULL_DELAY
        else:
            self._stage = 2
            return PUBLICATION_DELAY
