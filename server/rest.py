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

def adapt_academics_publication(data):
    return {
        'id': data.get('Id'),
        'name': data.get('DN'),
        'cites': data.get('CC'),
        'year': data.get('Y'),
        'authors': list(filter(None, (d.get('DAuN') for d in data.get('AA', ())))),
        'publisher': data.get('PB'),
        'sources': ['ms-academics'],
    }

async def get_publications(request):
    result = []

    data = await citehub.fetch_google_scholar(request.app['client'], 'Cristina Vicente-Chicote')
    result.extend(map(adapt_scholar_publication, data['publications']))

    data = await citehub.fetch_ms_academics(
        request.app['client'],
        request.app['config']['api-keys']['msacademics'],
        '***REMOVED***'
    )
    result.extend(map(adapt_academics_publication, data['entities']))

    return web.json_response(result)

ROUTES = [
    web.get('/rest/publications', get_publications)
]
