"""
See https://app.dimensions.ai.

May need to query certain endpoints manually, such as

    https://app.dimensions.ai/discover/publication/results.json?cursor=<base64>&and_facet_researcher=ur.<id>.<n>

Both the cookie and X-CSRF-Token headers may also need to be necessary, with referer:

    https://app.dimensions.ai/discover/publication?and_facet_researcher=ur.<id>.<n>
"""

class Dimensions:
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
