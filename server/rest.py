import itertools
import uuid
import json
from pathlib import Path

from aiohttp import web

from . import utils

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

def adapt_aminer_publication(data):
    return {
        'id': data['id'],
        'name': data['title'],
        'cites': data['num_citation'],
        'year': data['year'],
        'authors': [x['name'] for x in data['authors']],
        'publisher': data.get('venue', {}).get('info', {}).get('name', ''),
        'sources': ['aminer'],
    }

def merge_data(*data):
    assert len(data) != 0
    return {
        'id': f'merged-{uuid.uuid4()}',
        'name': data[0]['name'],
        'cites': next((d['cites'] for d in data if d['cites']), None),
        'year': next((d['year'] for d in data if d['year']), None),
        'authors': list(itertools.chain(*(d['authors'] for d in data))),
        'publisher': next((d['publisher'] for d in data if d['publisher']), None),
        'sources': list(itertools.chain(*(d['sources'] for d in data))),
    }

def merge_sorted_result(result):
    # Merge may be automatic based on some similarity threshold,
    # or interactive by asking the user to merge, in which case
    # they choose what version to keep or even edit the details.
    #
    # For example, author names may vary a bit, or the publication
    # title, but exact match should definitely be automatic.
    #
    # If we have the DOI, then it's clear when to merge.
    #
    # Ideally, when merging, we need the DOI of the cites.
    # See also DBLP for articles (sadly, has no cite information.)
    i = 0
    limit = len(result) - 1
    while i < limit:
        a, b = result[i], result[i + 1]
        if a['name'] == b['name']:
            result[i] = merge_data(a, b)
            result.pop(i + 1)
            limit -= 1

        i += 1

async def get_publications(request):
    raise NotImplementedError
    result = []

    # Google Scholar
    data = await citehub.fetch_google_scholar(
        request.app['client'],
        'Cristina Vicente-Chicote'
    )
    result.extend(map(adapt_scholar_publication, data['publications']))

    # Microsoft Academics
    data = await citehub.fetch_ms_academics(
        request.app['client'],
        request.app['config']['api-keys']['msacademics'],
        '***REMOVED***'
    )
    result.extend(map(adapt_academics_publication, data['entities']))

    # Arnet Miner
    data = await citehub.fetch_aminer(
        request.app['client'],
        request.app['config']['api-keys']['aminer'],
        '***REMOVED***'
    )
    result.extend(map(adapt_aminer_publication, data['items']))

    # Sort, merge
    result.sort(key=lambda x: x['name'])
    merge_sorted_result(result)

    # TODO Objective: Gather data from more sources
    return web.json_response(result)


def get_sources(request):
    return web.json_response(request.app['crawler'].get_source_fields())


@utils.locked
async def save_sources(request):
    request.app['crawler'].update_source_fields(await request.json())
    return web.json_response({})


ROUTES = [
    web.get('/rest/publications', get_publications),
    web.get('/rest/sources', get_sources),
    web.post('/rest/sources', save_sources),
]
