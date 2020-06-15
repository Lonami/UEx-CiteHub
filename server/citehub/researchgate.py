"""
Possibly no API, but https://www.researchgate.net/profile/ has info.

See https://www.researchgate.net/profile/<profile name>
"""



class ResearchGate:
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
