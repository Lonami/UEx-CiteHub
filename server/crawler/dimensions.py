"""
See https://app.dimensions.ai.

May need to query certain endpoints manually, such as

    https://app.dimensions.ai/discover/publication/results.json?cursor=<base64>&and_facet_researcher=ur.<id>.<n>

Both the cookie and X-CSRF-Token headers may also need to be necessary, with referer:

    https://app.dimensions.ai/discover/publication?and_facet_researcher=ur.<id>.<n>
"""
import urllib.parse
import logging
from typing import Generator, Tuple, Optional
from ..storage import Author, Publication
from .task import Task

_log = logging.getLogger(__name__)


async def fetch_author(session, author_id):
    # Alternative paths:
    # * facets/publication.json
    # * facets/publication/researcher/{author_id}/box.json
    async with session.get(
            'https://app.dimensions.ai/panel/publication/author/preview.json',
            params={'and_facet_researcher': author_id}
    ) as resp:
        return await resp.json()

def adapt_authors(data) -> Generator[Author, None, None]:
    for author in data['data']:
        author = author['details']
        yield Author(
            id=author['id'],
            first_name=author['first_name'],
            last_name=author['last_name'],
            extra={
                'organization': author['current_org_name'],
                'country': author['current_org_country'],
            }
        )

async def fetch_publications(session, author_id, cursor):
    async with session.get(
            'https://app.dimensions.ai/discover/publication/results.json',
            params={'and_facet_researcher': author_id, 'cursor': cursor or '*'}
    ) as resp:
        return await resp.json()

def adapt_publications(data) -> Generator[Publication, None, None]:
    for pub in data['docs']:
        yield Publication(
            id=pub['id'],
            name=pub['title'],
            authors=[Author(
                # TODO researcher_dim_id seem to match with the names in the author list
                full_name=author
            ) for author in pub['author_list'].split(', ')]
        )

async def fetch_citations(session, pub_id, cursor):
    async with session.get(
            'https://app.dimensions.ai/details/sources/publication/related/publication/cited-by.json',
            params={'id': pub_id, 'cursor': cursor or '*'}
    ) as resp:
        return await resp.json()

def adapt_citations(data) -> Generator[Publication, None, None]:
    for pub in data['docs']:
        first_page, last_page = map(int, pub['pages'].split('-'))
        yield Publication(
            id=pub['id'],
            name=pub['title'],
            authors=[Author(
                full_name=author
            ) for author in pub['author_list'].split(', ')],
            extra={
                'editors': pub['editor_list'].split(', '),
                'journal': pub['journal_title'],
                'book': pub['book_title'],
                'pdf': pub['linkout_oa'],
                'publisher': pub['publisher_source'],
                'doi': pub['doi'],
                'first-page': first_page,
                'last-page': last_page,
                'year': pub['pub_year'],
            }
        )

def author_id_from_url(url):
    url = urllib.parse.urlparse(url)
    assert url.netloc == 'app.dimensions.ai'
    assert url.path == '/discover/publication'
    query = urllib.parse.parse_qs(url.query)
    return query['and_facet_researcher'][0]


class CrawlDimensions(Task):
    def __init__(self, root):
        super().__init__(root)
        self._stage = 0
        self._offset = None
        self._cursor = None

    @classmethod
    def namespace(cls):
        return 'dimensions'

    @classmethod
    def fields(cls):
        return {
            'url':
                'Navigate to <a href="https://app.dimensions.ai/discover/publication">'
                'Dimension\'s search</a> and search for publications with your name. Open one '
                'of the publications and click on your name in the author list'
                'search for publications with your name. Click on your name in the list of '
                'authors of one of the publications, and copy that final URL.'
        }

    def set_field(self, key, value):
        assert key == 'url'
        self._storage.user_author_id = author_id_from_url(value)
        self._storage.user_pub_ids = []
        self._due = 0
        self._stage = 0
        self._offset = None
        self._cursor = None

    def _load(self, data):
        self._stage = data['stage']
        self._offset = data['offset']
        self._cursor = data['cursor']

    def _save(self):
        return {
            'stage': self._stage,
            'offset': self._offset,
            'cursor': self._cursor,
        }

    async def _step(self, session):
        if not self._storage.user_author_id:
            return 24 * 60 * 60

        # Primary authors
        if self._stage == 0:
            _log.debug('running stage 0')
            data = await fetch_author(session, self._storage.user_author_id)
            for author in adapt_authors(data):
                self._storage.save_author(author)

            self._stage = 1
            return 10 * 60

        # Publications
        elif self._stage == 1:
            _log.debug('running stage 1')
            data = await fetch_publications(session, self._storage.user_author_id, self._cursor)

            for pub in adapt_publications(data):
                self._storage.user_pub_ids.append(pub.id)
                self._storage.save_pub(pub)

            if data['next_cursor']:
                self._cursor = data['next_cursor']
                return 5 * 60
            else:
                self._stage = 2
                self._offset = 0
                self._cursor = None
                return 10 * 60

        # Citations per publication
        elif self._stage == 2:
            if self._offset >= len(self._storage.user_pub_ids):
                self._stage = 0
                self._offset = None
                self._cursor = None
                return 24 * 60 * 60

            pub_id = self._storage.user_pub_ids[self._offset]
            pub = self._storage.load_pub(pub_id)

            if pub.cit_paths is None:
                pub.cit_paths = []

            data = await fetch_citations(session, pub_id, self._cursor)

            for cit in adapt_citations(data):
                self._storage.save_pub(cit)
                pub.cit_paths.append(cit.unique_path_name())

            self._storage.save_pub(pub)

            if data['next_cursor']:
                self._cursor = data['next_cursor']
                return 5 * 60
            else:
                self._offset += 1
                self._cursor = None
                return 10 * 10
