from aiohttp import web

from . import citehub

def adapt_scholar_publication(data):
    return {
        'id': data['id'],
        'name': data['name'],
        'cites': data['cites'],
        'year': data['year'],
        'authors': data['authors'],
        'publisher': data['publisher'],
        'sources': ['google-scholar'],
    }

async def get_publications(request):
    result = []

    data = await citehub.fetch_google_scholar(request.app['client'], 'Cristina Vicente-Chicote')
    result.extend(map(adapt_scholar_publication, data['publications']))

    return web.json_response(result)

ROUTES = [
    web.get('/rest/publications', get_publications)
]
