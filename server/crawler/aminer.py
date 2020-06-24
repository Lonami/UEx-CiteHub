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
from typing import Generator, List, Tuple

from ..storage import Author, Publication
from .task import Task

_log = logging.getLogger(__name__)

class ArnetMiner:
    def __init__(self, session, base_url='https://apiv2.aminer.cn/magic'):
        self._session = session
        self._headers = {
            'Accept': 'application/json'
        }
        self._base_url = base_url

    async def search_person(self, query):
        return await self.query({
            'action': 'person7.SearchPersonWithDSL',
            'parameters': {
                'offset': 0,
                'size': 20,
                'query': query,
                'aggregation': [
                    'gender',
                    'h_index',
                    'nation',
                    'lang'
                ]
            },
            'schema': {
                'person': [
                    'id',
                    'name',
                    'name_zh',
                    'avatar',
                    'tags',
                    'is_follow',
                    'num_view',
                    'num_follow',
                    'is_upvoted',
                    'num_upvoted',
                    'is_downvoted',
                    'bind',
                    {
                        'profile': [
                            'position',
                            'position_zh',
                            'affiliation',
                            'affiliation_zh',
                            'org'
                        ]
                    },
                    {
                        'indices': [
                            'hindex',
                            'gindex',
                            'pubs',
                            'citations',
                            'newStar',
                            'risingStar',
                            'activity',
                            'diversity',
                            'sociability'
                        ]
                    }
                ]
            }
        })

    async def get_stats(self, author_id):
        return await self.query({
            'action': 'person.GetPersonPubsStats',
            'parameters': {
                'ids': [author_id]
            }
        })

    async def search_publications(self, author_id, offset):
        return await self.query({
            'action': 'person.GetPersonPubs',
            'parameters': {
                'offset': offset,
                'size': 100,
                'sorts': [
                    '!year'
                ],
                'ids': [
                    author_id
                ],
                'searchType': 'all'
            },
            'schema': {
                'publication': [
                    'id',
                    'year',
                    'title',
                    'title_zh',
                    'authors._id',
                    'authors.name',
                    'authors.name_zh',
                    'num_citation',
                    'venue.info.name',
                    'venue.volume',
                    'venue.info.name_zh',
                    'venue.issue',
                    'pages.start',
                    'pages.end',
                    'lang',
                    'pdf',
                    'doi',
                    'urls',
                    'versions'
                ]
            }
        })

    async def search_cited_by(self, paper_id, offset):
        return await self.query({
            'action': 'publication.CitedByPid',
            'parameters': {
                'offset': offset,
                'size': 100,
                'ids': [
                    paper_id
                ]
            }
        })

    async def query(self, data):
        url = self._base_url
        # Probably uses and returns a list so many can be invoked at once
        async with self._session.post(url, json=[data], headers=self._headers) as resp:
            if resp.status == 200:
                return (await resp.json())['data'][0]
            else:
                raise ValueError(f'HTTP {resp.status} fetching {url}:\n{await resp.text()}')


def author_id_from_url(url):
    url = urllib.parse.urlparse(url)
    assert url.netloc == 'www.aminer.cn'
    parts = url.path.split('/')
    assert parts[1] == 'profile'
    return parts[3]


def adapt_publications(data) -> Generator[Publication, None, None]:
    def maybe_int(value):
        return int(value) if value else None

    # If it has 0 keyValues then the items key will be missing
    for pub in data.get('items', ()):
        yield Publication(
            id=pub['id'],
            name=pub['title'],
            authors=[
                Author(
                    id=author.get('id'),
                    full_name=author['name'],
                    extra={
                        'organization': author.get('org'),
                    }
                )
                for author in pub['authors']
            ],
            extra={
                'cit-count': pub['num_citation'],  # used later
                'doi': pub['doi'],
                'language': pub.get('lang') or None,
                'first-page': maybe_int(pub.get('pages', {}).get('start')),
                'last-page': maybe_int(pub.get('pages', {}).get('end')),
                'urls': pub.get('urls'),
                'issue': pub.get('venue', {}).get('issue') or None,
                'volume': pub.get('venue', {}).get('volume') or None,
                'publisher': pub.get('venue', {}).get('info', {}).get('name'),
                'pdf': pub.get('pdf') or None,
            }
        )


# TODO this is very similar to msacademics, maybe we can reuse
class CrawlArnetMiner(Task):
    def __init__(self, root):
        super().__init__(root)
        self._stage = 0
        self._offset = None
        self._pub_count = None
        self._cit_offset = None
        self._cit_count = None

    @classmethod
    def namespace(cls):
        return 'aminer'

    @classmethod
    def fields(cls):
        return {
            'url':
                'Navigate to <a href="https://www.aminer.cn/">AMiner\'s home</a> and search for '
                'your profile. Click on it when you find it and copy the URL.'
        }

    def set_field(self, key, value):
        assert key == 'url'
        self._storage.user_author_id = author_id_from_url(value)
        self._storage.user_pub_ids = []
        self._due = 0
        self._stage = 0
        self._offset = 0
        self._pub_count = None
        self._cit_offset = None
        self._cit_count = None

    def _load(self, data):
        self._stage = data['stage']
        self._offset = data['offset']
        self._pub_count = data['pub-count']
        self._cit_offset = data['cit-offset']
        self._cit_count = data['cit-count']

    def _save(self):
        return {
            'stage': self._stage,
            'offset': self._offset,
            'pub-count': self._pub_count,
            'cit-offset': self._cit_offset,
            'cit-count': self._cit_count,
        }

    async def _step(self, session):
        if not self._storage.user_author_id:
            return 24 * 60 * 60

        miner = ArnetMiner(session)

        # Fetching publications
        if self._stage == 0:
            _log.debug('running stage 0 at offset %d', self._offset)
            data = await miner.search_publications(self._storage.user_author_id, self._offset)
            self._pub_count = data['keyValues']['total']

            empty = True
            for pub in adapt_publications(data):
                empty = False
                self._offset += 1
                self._storage.user_pub_ids.append(pub.id)
                self._storage.save_pub(pub)

            if empty:
                _log.info('stage 0 came out empty at %d/%d', self._offset, self._pub_count)
                self._offset = self._pub_count
            else:
                _log.debug('stage 0 at %d/%d', self._offset, self._pub_count)

            if self._offset < self._pub_count:
                return 5 * 60
            else:
                self._stage = 1
                self._offset = 0
                self._cit_offset = 0
                return 30 * 60

            return 60

        # Fetching citations
        elif self._stage == 1:
            _log.debug('running stage 1 at offset %d, %d', self._offset, self._cit_offset)

            if self._offset >= len(self._storage.user_pub_ids):
                _log.debug('checked all publications')
                self._stage = 0
                self._offset = 0
                return 24 * 60 * 60

            pub_id = self._storage.user_pub_ids[self._offset]
            pub = self._storage.load_pub(pub_id)

            if pub.extra['cit-count'] == 0:
                _log.debug('no citations to check for this publication')
                self._offset += 1
                return 1

            if pub.cit_paths is None:
                pub.cit_paths = []

            data = await miner.search_cited_by(pub_id, self._cit_offset)

            # The listed citations are less than the found count for some reason; however it's
            # unlikely that they are greater (so if we previously fetched 0 we don't bother
            # making additional network requests).
            self._cit_count = data['keyValues']['total']

            empty = True
            for cit in adapt_publications(data):
                empty = False
                self._cit_offset += 1
                self._storage.save_pub(cit)
                pub.cit_paths.append(cit.unique_path_name())

            self._storage.save_pub(pub)

            if empty:
                _log.info('stage 1 came out empty at %d/%d', self._cit_offset, self._cit_count)
                self._cit_offset = self._cit_count
            else:
                _log.debug('stage 1 at %d/%d', self._cit_offset, self._cit_count)

            if self._cit_offset < self._cit_count:
                return 5 * 60
            else:
                self._offset += 1
                self._cit_offset = 0
                return 30 * 60
