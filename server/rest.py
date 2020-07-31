import itertools
import uuid
import json
import statistics
from pathlib import Path

from aiohttp import web

from . import utils


MAX_I_INDEX = 20


async def get_publications(request):
    publications = []
    cit_count = []
    author_count = []
    stats = {}

    used = set()
    merge_checker = request.app["merger"].checker()
    storages = request.app["crawler"].storages()
    for source, storage in storages.items():
        for pub_id in storage.user_pub_ids:
            pub = storage.load_pub(pub_id)
            path = pub.unique_path_name()

            sources = [{"key": source, "ref": pub.ref,}]
            used.add(path)
            for ns, p in merge_checker.get_related(source, path):
                # TODO having to load each related publication is quite expensive
                # probably the entire storage should be in memory AND disk because
                # it's not that much data (even less if "extra" is not in memory since
                # we don't use it).
                sources.append({"key": ns, "ref": storages[ns].load_pub(path=p).ref})
                used.add(p)

            # TODO also merge cites and other stats like author count
            cites = len(pub.cit_paths or ())
            cit_count.append(cites)
            author_count.append(len(pub.authors))
            # TODO this should be smarter and if anyhas missing data (e.g. year) use a different source
            publications.append(
                {
                    "sources": sources,
                    "name": pub.name,
                    "authors": [
                        {"full_name": storage.load_author(a).full_name}
                        for a in pub.authors
                    ],
                    "cites": cites,
                    "year": pub.year,
                }
            )

    cit_count.sort(reverse=True)

    # Largest number "h" such that "h" publications have "h" or more citations.
    h_index = 0
    for i, cc in enumerate(cit_count, start=1):
        if cc >= i:
            h_index = i
        else:
            break

    # Number of publications with at least # citations (this list starts at 1).
    i_indices = [0] * MAX_I_INDEX
    for cc in cit_count:
        if cc != 0:
            i_indices[min(cc, MAX_I_INDEX) - 1] += 1

    # `i` or more cites also count in `i - 1` tally since `i > i - 1`.
    for i in reversed(range(1, MAX_I_INDEX)):
        i_indices[i - 1] += i_indices[i]

    # Largest number "g" such that "g" articles have "g²" or more citations in total.
    g_index = 0
    g_sum = 0
    for i, cc in enumerate(cit_count, start=1):
        g_sum += cc
        if g_sum >= i ** 2:
            g_index = i
        else:
            break

    # e² = sum[j in 1..h](cit_j - h)
    e_index = (sum(cit_count[:h_index]) - h_index ** 2) ** 0.5

    stats["avg_author_count"] = statistics.mean(author_count)
    stats["pub_count"] = len(publications)

    return web.json_response(
        {
            "e_index": e_index,
            "g_index": g_index,
            "h_index": h_index,
            "i_indices": i_indices,
            "stats": stats,
            "publications": publications,
        }
    )


def get_sources(request):
    # TODO authentication
    return web.json_response(request.app["crawler"].get_source_fields())


@utils.locked
async def save_sources(request):
    result = request.app["crawler"].update_source_fields(await request.json())
    return web.json_response(result)


async def force_merge(request):
    ok = request.app["merger"].force_merge()
    return web.json_response({"ok": ok})


def register_user(request):
    pass


def login_user(request):
    pass


def logout_user(request):
    pass


def delete_user(request):
    pass


ROUTES = [
    web.get("/rest/publications", get_publications),
    web.get("/rest/sources", get_sources),
    web.post("/rest/sources", save_sources),
    web.post("/rest/force-merge", force_merge),
    web.post("/rest/user/register", register_user),
    web.post("/rest/user/login", login_user),
    web.post("/rest/user/logout", logout_user),
    web.post("/rest/user/delete", delete_user),
]
