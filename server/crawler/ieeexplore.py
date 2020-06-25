"""
https://ieeexplore.ieee.org/
"""
import urllib.parse
import logging
from typing import Generator
from ..storage import Author, Publication
from .task import Task

_log = logging.getLogger(__name__)


async def fetch_author(session, author_id):
    async with session.post('https://ieeexplore.ieee.org/rest/search', json={
        'searchWithin': [f'"Author Ids":{author_id}'],
        'history': 'no',
        'sortType': 'newest',
        'highlight': True,
        'returnFacets': ['ALL'],
        'returnType': 'SEARCH',
        'matchPubs': True,
    }, headers={
        'Referer': f'https://ieeexplore.ieee.org/author/{author_id}',
    }) as resp:
        return await resp.json()


async def fetch_citations(session, document_id):
    async with session.get(f'https://ieeexplore.ieee.org/rest/document/{document_id}/citations', headers={
        'Referer': f'https://ieeexplore.ieee.org/document/{document_id}/citations?tabFilter=papers',
    }) as resp:
        return await resp.json()


def author_id_from_url(url):
    url = urllib.parse.urlparse(url)
    assert url.netloc == 'ieeexplore.ieee.org'
    parts = url.path.split('/')
    assert parts[1] == 'author'
    return parts[2]


def adapt_publications(data) -> Generator[Publication, None, None]:
    for paper in data['records']:
        yield Publication(
            id=paper['articleNumber'],
            name=paper['articleTitle'],
            authors=[Author(
                id=str(author['id']),
                full_name=author['preferredName'],
                first_name=author['firstName'],
                last_name=author['lastName'],
                extra={
                    'normalized-name': author['normalizedName'],
                }
            ) for author in paper['authors']],
            extra={
                'doi': paper['doi'],
                'year': paper['publicationYear'],
                'volume': paper.get('volume'),
                'issue': paper.get('issue'),
                'first-page': paper['startPage'],
                'last-page': paper['endPage'],
                'date': paper['publicationDate'],
                'publisher': paper['publisher'],
                'abstract': paper['abstract'],
            }
        )


def _remove_enclosed(parts, sep, prefix, suffix):
    end_i = len(parts)
    while end_i != 0:
        end_i -= 1
        if parts[end_i].endswith(suffix):
            start_i = end_i
            while not parts[start_i].startswith(prefix):
                start_i -= 1  # we won't handle malformed enclosings

            result = sep.join(parts[start_i:end_i + 1])
            del parts[start_i:]
            return result

    return None


def adapt_citations(data) -> Generator[Publication, None, None]:
    citations = data['paperCitations']
    citations = citations.get('ieee', ()) + citations.get('nonIeee', ())
    for cit in citations:
        iden = cit['links'].get('documentLink') or None
        if iden:
            iden = iden.split('/')[-1]

        # Display seemingly comes in two forms:
        # 'Author Name, Author Name, "Publication Title", <i>Publication Location</i>, pp. start page-end page, year'
        # 'Author Name, Author Name, <i>Publication Title</i>, vol. 51, no. 4, pp. page, year'
        #
        # Try to extract the information from here first.
        display = cit['displayText']
        sep = ', '
        parts = display.split(sep)

        if parts[-1].endswith('.') and parts[-1][:-1].isdigit():
            year = int(parts.pop()[:-1])
        else:
            year = None

        if parts[-1].startswith('pp. '):
            pages = parts.pop()[4:]
            if '-' in pages:
                start_page, end_page = map(int, pages.split('-'))
            else:
                start_page = int(pages)
                end_page = start_page
        else:
            start_page = end_page = None

        if parts[-1].startswith('no. '):
            issue = int(parts.pop()[4:])
        else:
            issue = None

        if parts[-1].startswith('vol. '):
            volume = int(parts.pop()[5:])
        else:
            volume = None

        # Anything else we don't handle, so we can move on to handling the enclosed parts
        italics = _remove_enclosed(parts, sep, '<i>', '</i>')
        enquoted = _remove_enclosed(parts, sep, '"', '"')
        author_names = parts

        # A proper title has priority over whatever we came up with
        if cit.get('title'):
            title = cit['title']
            location = italics
        elif enquoted:
            title = enquoted
            location = italics
        else:
            title = italics
            location = None

        yield Publication(
            id=iden,
            name=title,
            authors=[Author(full_name=name) for name in author_names],
            extra={
                'google-scholar-url': cit.get('googleScholarLink'),
                'start-page': start_page,
                'end-page': end_page,
                'issue': issue,
                'volume': volume,
                'year': year,
                'location': location,
            }
        )


class CrawlExplore(Task):
    def __init__(self, root):
        super().__init__(root)
        self._stage = 0
        self._offset = None

    @classmethod
    def namespace(cls):
        return 'ieeexplore'

    @classmethod
    def fields(cls):
        return {
            'url':
                'Navigate to <a href="https://ieeexplore.ieee.org/">IEEE Xplore\'s home</a> and'
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

    def _load(self, data):
        self._stage = data['stage']
        self._offset = data['offset']

    def _save(self):
        return {
            'stage': self._stage,
            'offset': self._offset,
        }

    async def _step(self, session):
        if not self._storage.user_author_id:
            return 24 * 60 * 60

        # TODO not sure how offsets work here, there's so little data for the author we care in this site so can't test

        # Fetching publications
        if self._stage == 0:
            _log.debug('running stage 0')
            data = await fetch_author(session, self._storage.user_author_id)

            for pub in adapt_publications(data):
                self._storage.user_pub_ids.append(pub.id)
                self._storage.save_pub(pub)

            self._stage = 1
            self._offset = 0
            return 10 * 60

        # Fetching publications
        elif self._stage == 1:
            if self._offset >= len(self._storage.user_pub_ids):
                self._stage = 0
                self._offset = None
                return 24 * 60 * 60

            _log.debug('running stage 1 at %d', self._offset)

            pub_id = self._storage.user_pub_ids[self._offset]
            pub = self._storage.load_pub(pub_id)

            if pub.cit_paths is None:
                pub.cit_paths = []

            data = await fetch_citations(session, pub_id)
            self._offset += 1

            for cit in adapt_citations(data):
                self._storage.save_pub(cit)
                pub.cit_paths.append(cit.unique_path_name())

            self._storage.save_pub(pub)

            return 10 * 60
