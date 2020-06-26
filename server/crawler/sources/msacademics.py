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
import logging
from typing import Generator, List, Tuple

from ...storage import Author, Publication
from ..task import Task

_log = logging.getLogger(__name__)

def new_filtered_dict(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}


class Academics:
    def __init__(self, session, api_key, base_url='https://api.labs.cognitive.microsoft.com/academic/v1.0/'):
        self._session = session
        self._headers = {
            'Ocp-Apim-Subscription-Key': api_key,
            'Accept': 'application/json'
        }
        self._base_url = base_url

    async def interpret(self, query):
        url = self._base_url + 'interpret'
        async with self._session.get(url, params={'query': query}, headers=self._headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise ValueError(f'HTTP {resp.status} fetching {url}')

    async def evaluate(
            self,
            expr: str,
            *,
            model: str = None,
            count: int = None,
            offset: int = None,
            orderby: str = None,
            attributes: str = None
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
        url = self._base_url + 'evaluate'
        async with self._session.get(url, params=new_filtered_dict(
            expr=expr,
            model=model,
            count=count,
            offset=offset,
            orderby=orderby,
            attributes=attributes
        ), headers=self._headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise ValueError(f'HTTP {resp.status} fetching {url}')


def author_id_from_url(url):
    url = urllib.parse.urlparse(url)
    assert url.netloc == 'academic.microsoft.com'
    parts = url.path.split('/')
    assert parts[1] == 'profile'
    return parts[2]


async def fetch_profile(session, iden):
    # Note: the author ID from here is not the one we actually expect and using it in the real API will fail
    async with session.post('https://academic.microsoft.com/api/user/profile', json=iden) as resp:
        return await resp.json()

def adapt_profile(profile) -> Author:
    entity = profile['entity']
    inst = entity.get('i', {})
    return Author(
        # An author may have actually published papers under a different ID
        id=str(entity['id']),
        full_name=entity['dn'],
        extra={
            'profile-id': entity['profileId'],
            'latitude': inst.get('lat'),
            'longitude': inst.get('lon'),
            'institution': inst.get('dn'),
            'institution-desc': inst.get('d'),
            'institution-logo': inst.get('iurl'),
            'alternate-name': entity.get('an'),
            'web-profiles': entity.get('w'),
        }
    )

_FETCH_SIZE = 10  # capped to 10

def _expr_query(expr, query, offset):
    return {
        'query': query,  # seems needed to get original papers when fetching citations
        'queryExpression': expr,
        'filters': [],
        'orderBy': 0,
        'skip': offset,
        'sortAscending': True,
        'take': _FETCH_SIZE,
        'includeCitationContexts': True,
        # 'profileId': '<uuid4 from expr>',
    }


async def fetch_publications(session, expr, query, offset):
    async with session.post('https://academic.microsoft.com/api/search', json=_expr_query(expr, query, offset)) as resp:
        return await resp.json()

def _adapt_paper(paper) -> Publication:
    publisher = paper['v']
    _sources = paper['s']  # source type 0 and 1 has link
    authors = paper['a']
    return Publication(
        id=str(paper['id']),
        name=paper['dn'],
        authors=[
            Author(
                full_name=author['dn'],
                extra={
                    'institutions': [inst['dn'] for inst in author['i']],
                }
            )
            for author in authors
        ],
        extra={
            'description': paper['d'],
            'publisher': publisher.get('displayName'),  # id 0 won't have this field and the rest empty
            'volume': publisher['volume'] or None,
            'issue': publisher['issue'] or None,
            'first-page': publisher['firstPage'] or None,
            'last-page': publisher['lastPage'] or None,
            'date': publisher['publishedDate'],
        }
    )

def adapt_publications(data) -> Generator[Publication, None, None]:
    paper_results = data['pr']
    for paper in paper_results:
        yield _adapt_paper(paper['paper'])

async def fetch_citations(session, expr, query, offset):
    async with session.post('https://academic.microsoft.com/api/edpsearch/citations', json=_expr_query(expr, query, offset)) as resp:
        return await resp.json()

def adapt_citations(data) -> Generator[Tuple[Publication, List[str]], None, None]:
    for paper in data['rpi']:
        yield _adapt_paper(paper['paper']), [paper['paperId'] for paper in paper['originalPaperLinks']]

class CrawlAcademics(Task):
    def __init__(self, root):
        super().__init__(root)
        self._stage = 0
        self._offset = None
        self._pub_count = None
        self._pub_expr = None
        self._cit_count = None
        self._cit_expr = None
        self._query = None

    @classmethod
    def namespace(cls):
        return 'academics'

    @classmethod
    def fields(cls):
        return {
            'url':
                'Navigate to <a href="https://academic.microsoft.com/home">Microsoft Academic\'s '
                'home</a> and search for your profile. Click on it when you find it and copy the '
                'URL.'
        }

    def set_field(self, key, value):
        assert key == 'url'
        self._storage.user_author_id = author_id_from_url(value)
        self._storage.user_pub_ids = []
        self._due = 0
        self._stage = 0
        self._offset = None
        self._pub_count = None
        self._pub_expr = None
        self._cit_count = None
        self._cit_expr = None
        self._query = None

    def _load(self, data):
        self._stage = data['stage']
        self._offset = data['offset']
        self._pub_count = data['pub-count']
        self._pub_expr = data['pub-expr']
        self._cit_count = data['cit-count']
        self._cit_expr = data['cit-expr']
        self._query = data['query']

    def _save(self):
        return {
            'stage': self._stage,
            'offset': self._offset,
            'pub-count': self._pub_count,
            'pub-expr': self._pub_expr,
            'cit-count': self._cit_count,
            'cit-expr': self._cit_expr,
            'query': self._query,
        }

    async def _step(self, session):
        if not self._storage.user_author_id:
            return 24 * 60 * 60

        # Determine the true queries to make
        if self._stage == 0:
            _log.debug('running stage 0 on %s', self._storage.user_author_id)
            data = await fetch_profile(session, self._storage.user_author_id)
            self._pub_count = data['entity']['pc']
            self._pub_expr = data['publicationsExpression']
            self._cit_expr = data['citedByExpression']
            self._query = data['entity']['dn']
            self._stage = 1
            self._offset = 0
            return 1

        # Fetching publications
        elif self._stage == 1:
            _log.debug('running stage 1 on %s (%s), offset %d', self._pub_expr, self._query, self._offset)
            data = await fetch_publications(session, self._pub_expr, self._query, self._offset)

            empty = True
            for pub in adapt_publications(data):
                empty = False
                self._offset += 1
                self._storage.user_pub_ids.append(pub.id)
                self._storage.save_pub(pub)

            if empty:
                _log.info('stage 1 came out empty at %d/%d', self._offset, self._pub_count)
                self._offset = self._pub_count
            else:
                _log.debug('stage 1 at %d/%d', self._offset, self._pub_count)

            if self._offset < self._pub_count:
                return 2 * 60
            else:
                self._stage = 2
                self._offset = 0
                return 30 * 60

        # Fetching citations
        elif self._stage == 2:
            _log.debug('running stage 2 on %s (%s), offset %d', self._pub_expr, self._query, self._offset)
            data = await fetch_citations(session, self._cit_expr, self._query, self._offset)
            self._cit_count = data['sr']['t']

            empty = True
            for cit, cites_ids in adapt_citations(data):
                empty = False
                self._offset += 1
                self._storage.save_pub(cit)

                for cites_id in cites_ids:
                    pub = self._storage.load_pub(cites_id)
                    if pub.cit_paths is None:
                        pub.cit_paths = []

                    pub.cit_paths.append(cit.unique_path_name())
                    self._storage.save_pub(pub)

            if empty:
                _log.info('stage 2 came out empty at %d/%d', self._offset, self._cit_count)
                self._offset = self._cit_count
            else:
                _log.debug('stage 2 at %d/%d', self._offset, self._cit_count)

            if self._offset < self._cit_count:
                return 2 * 60
            else:
                self._stage = 0
                self._offset = None
                return 30 * 60

            return 60
