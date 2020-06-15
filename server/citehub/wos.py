"""
http://wos.fecyt.es/
https://clarivate.com/webofsciencegroup/solutions/xml-and-apis/
https://developer.clarivate.com/
"""


class WebOfScience:
    def __init__(self, session, api_key):
        self._session = session
        self._headers = {
            'Accept': 'application/json'
        }
        raise NotImplementedError

    async def query(self, url, **params):
        async with self._session.get(url, params=params, headers=self._headers) as resp:
            if resp.status == 200:
                return (await resp.json())
            else:
                raise ValueError(f'HTTP {resp.status} fetching {url}:\n{await resp.text()}')
