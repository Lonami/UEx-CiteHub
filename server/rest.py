from aiohttp import web

async def get_publications(request):
    # TODO fetch publications from various sources
    return web.json_response([])

ROUTES = [
    web.get('/rest/publications', get_publications)
]
