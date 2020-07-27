import itertools
import uuid
import json
from pathlib import Path

from aiohttp import web

from . import utils


async def get_publications(request):
    publications = []
    cit_count = []

    used = set()
    merge_checker = request.app["merger"].checker()
    for source, storage in request.app["crawler"].storages().items():
        for pub_id in storage.user_pub_ids:
            pub = storage.load_pub(pub_id)
            path = pub.unique_path_name()

            sources = [{"key": source, "ref": pub.ref,}]
            used.add(path)
            for ns, p in merge_checker.get_related(source, path):
                sources.append(
                    {"key": ns, "ref": p.ref,}
                )
                used.add(p)

            cites = len(pub.cit_paths or ())  # TODO also merge cites
            cit_count.append(cites)
            # TODO this should be smarter and if anyhas missing data (e.g. year) use a different source
            publications.append(
                {
                    "sources": sources,
                    "name": pub.name,
                    "authors": pub.authors,
                    "cites": cites,
                    "year": pub.year,
                }
            )

    cit_count.sort(reverse=True)
    h_index = 0
    for i, cc in enumerate(cit_count, start=1):
        if cc >= i:
            h_index = i
        else:
            break

    # TODO include more indices (such as i10-index, h10, hx (articulos con x citas en forma grafico))
    # maybe look something similar to bar graph by scholar

    return web.json_response({"h_index": h_index, "publications": publications,})


def get_sources(request):
    # TODO authentication
    return web.json_response(request.app["crawler"].get_source_fields())


@utils.locked
async def save_sources(request):
    request.app["crawler"].update_source_fields(await request.json())
    return web.json_response({})


async def force_merge(request):
    ok = request.app["merger"].force_merge()
    return web.json_response({"ok": ok})


ROUTES = [
    web.get("/rest/publications", get_publications),
    web.get("/rest/sources", get_sources),
    web.post("/rest/sources", save_sources),
    web.post("/rest/force-merge", force_merge),
]
