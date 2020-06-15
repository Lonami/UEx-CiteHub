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


async def fetch_full_author(session, author_id):
    soup = await _get_page(session, _URL_AUTHOR.format(author_id))
    name = soup.find('div', id='gsc_prf_in').text
    url_picture = _HOST + '/citations?view_op=medium_photo&user={}'.format(author_id)

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

    offset = 0
    publications = []
    while True:
        for row in soup.find_all('tr', class_='gsc_a_tr'):
            publications.append(_analyze_basic_publication_soup(row))

        if 'disabled' in soup.find('button', id='gsc_bpf_more').attrs:
            break

        offset += _PAGE_SIZE
        soup = await _get_page(session, _URL_AUTHOR.format(author_id) + f'&cstart={offset}')

    return {
        'name': name,
        'id': author_id,
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


async def search_author(session: aiohttp.ClientSession, name: str, *, full=True) -> AsyncGenerator[dict, None]:
    path = _URL_SEARCH_AUTHOR.format(urllib.parse.quote(name))
    while path is not None:
        soup = await _get_page(session, path)

        for row in soup.find_all('div', 'gsc_1usr'):
            author = _analyze_basic_author_soup(row)
            if full:
                author = await fetch_full_author(session, author['id'])
                author['publications'] = [
                    await fetch_full_publication(session, pub['id'])
                    for pub in author['publications']
                ]

            yield author

        nav_next = soup.find(class_='gs_btnPR gs_in_ib gs_btn_half gs_btn_lsb gs_btn_srt gsc_pgn_pnx')
        if nav_next and 'disabled' not in nav_next.attrs:
            path = codecs.getdecoder('unicode_escape')(nav_next['onclick'][17:-1])[0]
        else:
            path = None


async def fetch_full_publication(session, pub_id):
    soup = await _get_page(session, _URL_PUBLICATION.format(pub_id))

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
    citations = []

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

    if citations_url is not None:
        soup = await _get_page(session, url=citations_url)
        path = None
        while True:
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
                soup = await _get_page(session, path)
            else:
                break

    return {
        'id': pub_id,
        'name': title,
        'authors': authors,
        'date': date,
        'journal': journal,
        'volume': volume,
        'issue': issue,
        'page_range': page_range,
        'publisher': publisher,
        'abstract': abstract,
        'citations': citations,
    }


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
