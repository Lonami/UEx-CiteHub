import itertools
import uuid
import json
from pathlib import Path

from aiohttp import web

from . import utils


async def get_publications(request):
    result = []
    for source, storage in request.app['crawler'].storages().items():
        for pub_id in storage.user_pub_ids:
            pub = storage.load_pub(pub_id)
            result.append({
                'sources': [source],
                'name': pub.name,
                'authors': pub.authors,
                'cites': len(pub.cit_paths or ()),
            })

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
