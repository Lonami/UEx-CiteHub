"""
https://www.aminer.cn/ requires login to view additional info.

Trying to login on aminer.cn seems to be a bit buggy.

They seem to have some (private?) APIs:
* apiv2.aminer.cn/magic
* api.aminer.cn/api

The network tab in web browsers displays a lot of interesting XHR.
"""

class ArnetMiner:
    def __init__(self, session, auth, base_url='https://apiv2.aminer.cn/magic'):
        self._session = session
        self._headers = {
            'Authorization': auth,
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

    async def search_publications(self, author_id):
        return await self.query({
            'action': 'person.GetPersonPubs',
            'parameters': {
                'offset': 0,
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

    async def query(self, data):
        url = self._base_url
        # Probably uses and returns a list so many can be invoked at once
        async with self._session.post(url, json=[data], headers=self._headers) as resp:
            if resp.status == 200:
                return (await resp.json())['data'][0]
            else:
                raise ValueError(f'HTTP {resp.status} fetching {url}:\n{await resp.text()}')
