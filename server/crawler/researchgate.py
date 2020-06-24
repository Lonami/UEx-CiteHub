"""
Possibly no API, but https://www.researchgate.net/profile/ has info.

See https://www.researchgate.net/profile/<profile name>

Requires `Rg-Request-Token` and `sid` cookie to work (otherwise it's a 403).

Getting the token and sid: https://www.researchgate.net/refreshToken?c=rgcf-e98aaa8e8f7cad0f
The last part comes from a script in the main site.

The HTML however is a mess, full of nested `<div>` and classes used for style purposes.
"""
import logging
import urllib.parse
import bs4
from typing import Generator
from ..storage import Author, Publication
from .task import Task

_log = logging.getLogger(__name__)


async def fetch_token_sid(session):
    async with session.get(f'https://www.researchgate.net/refreshToken') as resp:
        for header in resp.headers.getall('set-cookie'):
            if header.startswith('sid='):
                sid = header[4:header.index(';')]
                break
        else:
            raise ValueError('sid cookie not found')

        rg_token = (await resp.json())['requestToken']
        return rg_token, sid


async def fetch_author(session, author_id):
    async with session.get(f'https://www.researchgate.net/profile/{author_id}') as resp:
        resp.raise_for_status()
        return bs4.BeautifulSoup(await resp.text(), 'html.parser')


async def fetch_citations(session, rg_token, sid, pub_id, offset):
    async with session.post(
        f'https://www.researchgate.net/lite.PublicationDetailsLoadMore.getCitationsByOffset.html'
        f'?publicationUid={pub_id}&offset={offset}',
        headers={
            'Rg-Request-Token': rg_token,
            'Cookie': f'sid={sid}',
        }
    ) as resp:
        return bs4.BeautifulSoup(await resp.text(), 'html.parser')


def adapt_publications(soup) -> Generator[Publication, None, None]:
    for card in soup.find(id='publications').parent.find_all(class_='nova-o-stack__item'):
        a = card.find(itemprop='headline').find('a')
        iden = a['href'].split('/')[-1].split('_')[0]
        title = a.text
        authors = [span.text for span in card.find_all(itemprop='name')]
        yield Publication(
            id=iden,
            name=title,
            authors=[Author(full_name=name) for name in authors]
        )


def adapt_citations(soup):
    for item in soup.find_all(class_='nova-v-citation-item'):
        a = item.find(class_='nova-v-publication-item__title').find('a')
        iden = a['href'].split('/')[-1].split('_')[0]
        title = a.text

        authors = []
        author_list = item.find(class_='nova-v-publication-item__person-list')
        for li in author_list.find_all('li'):
            a = li.find('a')
            authors.append(Author(
                id=a['href'].split('/')[-1],
                full_name=a.text
            ))

        abstract = item.find(class_='nova-v-publication-item__description')
        if abstract:
            abstract = abstract.text.replace('\n', '')

        yield Publication(
            id=iden,
            name=title,
            authors=authors,
            extra={
                'abstract': abstract,
            }
        )


def author_id_from_url(url):
    url = urllib.parse.urlparse(url)
    assert url.netloc == 'www.researchgate.net'
    parts = url.path.split('/')
    assert parts[1] == 'profile'
    return parts[2]


class CrawlResearchGate(Task):
    def __init__(self, root):
        super().__init__(root)
        self._stage = 0
        self._offset = None
        self._cit_offset = None
        self._rg_token = None
        self._sid = None

    @classmethod
    def namespace(cls):
        return 'researchgate'

    @classmethod
    def fields(cls):
        return {
            'url':
                'Navigate to <a href="https://www.researchgate.net/search">ResearchGate\'s '
                'search</a> and search for your profile. Click on it when you find it and copy '
                'the URL.'
        }

    def set_field(self, key, value):
        assert key == 'url'
        self._storage.user_author_id = author_id_from_url(value)
        self._storage.user_pub_ids = []
        self._due = 0
        self._stage = 0
        self._offset = None
        self._cit_offset = None
        self._rg_token = None
        self._sid = None

    def _load(self, data):
        self._stage = data['stage']
        self._offset = data['offset']
        self._cit_offset = data['cit-offset']
        self._rg_token = data['rg-token']
        self._sid = data['sid']

    def _save(self):
        return {
            'stage': self._stage,
            'offset': self._offset,
            'cit-offset': self._cit_offset,
            'rg-token': self._rg_token,
            'sid': self._sid,
        }

    async def _step(self, session):
        if not self._storage.user_author_id:
            return 24 * 60 * 60

        # Fetch token (hopefully it lasts long enough until we start over)
        if self._stage == 0:
            _log.debug('running stage 0')
            self._rg_token, self._sid = await fetch_token_sid(session)
            self._stage = 1
            return 0

        # Main page with mostly publications
        elif self._stage == 1:
            _log.debug('running stage 1')
            soup = await fetch_author(session, self._storage.user_author_id)
            for pub in adapt_publications(soup):
                self._storage.user_pub_ids.append(pub.id)
                self._storage.save_pub(pub)

            self._stage = 2
            self._offset = 0
            self._cit_offset = 0
            return 10 * 60

        # Citations, one by one (offset is an index into the publications)
        elif self._stage == 2:
            if self._offset >= len(self._storage.user_pub_ids):
                self._stage = 0
                self._offset = None
                self._cit_offset = None
                return 24 * 60 * 60

            _log.debug('running stage 2 at offset %d', self._offset)
            pub_id = self._storage.user_pub_ids[self._offset]
            pub = self._storage.load_pub(pub_id)
            if pub.cit_paths is None:
                pub.cit_paths = []

            soup = await fetch_citations(
                session,
                self._rg_token,
                self._sid,
                pub_id,
                self._cit_offset
            )

            empty = True
            for cit in adapt_citations(soup):
                empty = False
                self._cit_offset += 1
                self._storage.save_pub(cit)
                pub.cit_paths.append(cit.unique_path_name())

            self._storage.save_pub(pub)

            if empty:
                self._offset += 1
                self._cit_offset = 0
                return 10 * 60
            else:
                return 2 * 60
