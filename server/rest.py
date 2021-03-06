import itertools
import uuid
import json
import statistics
import functools
import time
from pathlib import Path

from aiohttp import web

from . import utils


MAX_I_INDEX = 20
AUTH_TOKEN_COOKIE = "token"


def _require_user(func):
    """
    Decorator to mark functions that need the user to be logged in.
    The `username` argument will be provided.
    """

    @functools.wraps(func)
    async def wrapped(request, *args, **kwargs):
        token = request.cookies.get(AUTH_TOKEN_COOKIE)
        username = await request.app["users"].username_of(token=token)
        if username:
            return await func(request, *args, username=username, **kwargs)
        else:
            raise web.HTTPForbidden()

    return wrapped


def _require_json_payload(payload_check=None, **key_checks):
    def decorator(func):
        @functools.wraps(func)
        async def wrapped(request, *args, **kwargs):
            try:
                payload = await request.json()
            except json.JSONDecodeError:
                raise web.HTTPBadRequest()

            if payload_check:
                if not payload_check(payload):
                    raise web.HTTPBadRequest()

            for key, check in key_checks.items():
                if key not in payload:
                    raise web.HTTPBadRequest()

                value = payload[key]
                if isinstance(check, type):
                    if not isinstance(value, check):
                        raise web.HTTPBadRequest()
                else:
                    if not check(value):
                        raise web.HTTPBadRequest()

            return await func(request, *args, payload=payload, **kwargs)

        return wrapped

    return decorator


@_require_user
async def get_metrics(request, username):
    publications = await request.app["db"].get_publications(username)

    pub_count = len(publications)
    cit_count = [p["cites"] for p in publications]
    author_count = [len(p["authors"]) for p in publications]

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

    return web.json_response(
        {
            "e_index": e_index,
            "g_index": g_index,
            "h_index": h_index,
            "i_indices": i_indices,
            "avg_author_count": statistics.mean(author_count) if author_count else 0.0,
            "pub_count": pub_count,
        }
    )


@_require_user
async def get_publications(request, username):
    return web.json_response(await request.app["db"].get_publications(username))


@_require_user
async def get_user_profile(request, username):
    return web.json_response(
        {
            "username": username,
            "sources": await request.app["scheduler"].get_source_fields(username),
        }
    )


@_require_user
@_require_json_payload(
    lambda p: isinstance(p, dict) and all(isinstance(v, dict) for v in p.values())
)
async def update_user_profile(request, username, payload):
    result = await request.app["scheduler"].update_source_fields(username, payload)
    return web.json_response(result)


@_require_user
async def force_merge(request, username):
    ok = request.app["merger"].force_merge()
    return web.json_response({"ok": ok})


@_require_json_payload(
    username=str, password=str,
)
async def register_user(request, payload):
    request.app["auth"].check_whitelist(payload["username"])
    request.app["auth"].apply_rate_limit(request)
    token = await request.app["users"].register(
        payload["username"], payload["password"]
    )
    resp = web.json_response(True)
    resp.set_cookie(
        AUTH_TOKEN_COOKIE,
        token,
        httponly=True,
        secure=request.app["config"]["www"].getboolean("secure", True),
    )
    return resp


@_require_json_payload(
    username=str, password=str,
)
async def login_user(request, payload):
    request.app["auth"].apply_rate_limit(request)
    token = await request.app["users"].login(payload["username"], payload["password"])
    resp = web.json_response(True)
    resp.set_cookie(
        AUTH_TOKEN_COOKIE,
        token,
        httponly=True,
        secure=request.app["config"]["www"].getboolean("secure", True),
    )
    return resp


@_require_user
async def logout_user(request, username):
    result = await request.app["users"].logout(username)
    resp = web.json_response(result)
    resp.del_cookie(AUTH_TOKEN_COOKIE)
    return resp


@_require_user
async def delete_user(request, username):
    result = await request.app["users"].delete(username)
    resp = web.json_response(result)
    resp.del_cookie(AUTH_TOKEN_COOKIE)
    return resp


@_require_user
@_require_json_payload(
    old_password=str, new_password=str,
)
async def update_password(request, username, payload):
    result = await request.app["users"].change_password(
        username, payload["old_password"], payload["new_password"]
    )
    return web.json_response(result)


@_require_user
async def takeout_data(request, username):
    body = await request.app["db"].export_data_as_zip(username)
    filename = f"uex-citehub-takeout-{int(time.time())}.zip"
    return web.Response(
        body=body,
        content_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


ROUTES = [
    web.get("/rest/metrics", get_metrics),
    web.get("/rest/publications", get_publications),
    web.get("/rest/user/profile", get_user_profile),
    web.post("/rest/user/profile", update_user_profile),
    web.post("/rest/force-merge", force_merge),
    web.post("/rest/user/register", register_user),
    web.post("/rest/user/login", login_user),
    web.post("/rest/user/logout", logout_user),
    web.post("/rest/user/delete", delete_user),
    web.post("/rest/user/update-password", update_password),
    web.get("/rest/takeout", takeout_data),
]
