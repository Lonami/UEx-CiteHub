# For simplicity, only one token per user. In the future we could save when the token was
# created, and if it's been unused for long enough revoke it, allowing also multiple tokens
# (letting the user login from multiple locations).
from . import utils
from aiohttp import web
from pathlib import Path
import os
import base64
import re


MIN_PASSWORD_LENGTH = 5
MAX_DETAILS_LENGTH = 128
USERNAME_RE = re.compile(r"[a-z]+")


def _check_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise web.HTTPBadRequest(
            reason=f"password must be at least {MIN_PASSWORD_LENGTH} characters long"
        )

    if len(password) > MAX_DETAILS_LENGTH:
        raise web.HTTPBadRequest(
            reason=f"password must be {MAX_DETAILS_LENGTH} characters long or less"
        )


class Users:
    def __init__(self, db):
        self._db = db

    async def register(self, username, password):
        if len(username) > MAX_DETAILS_LENGTH:
            raise web.HTTPBadRequest(
                reason=f"username must be {MAX_DETAILS_LENGTH} characters long or less"
            )

        if not USERNAME_RE.match(username):
            raise web.HTTPBadRequest(
                reason=f"username must use lowercase ascii letters only"
            )

        if await self._db.has_user(username=username):
            raise web.HTTPBadRequest(reason=f"username is already occupied")

        _check_password(password)

        password, salt = utils.hash_user_pass(password)
        token = await self._gen_token()
        await self._db.register_user(
            username=username, password=password, salt=salt, token=token,
        )
        return token

    async def login(self, username, password):
        bad_info = web.HTTPBadRequest(reason="invalid username or password")

        details = await self._db.get_user_password(username=username)
        if not details:
            raise bad_info

        saved_password, salt = details
        password, _ = utils.hash_user_pass(password, salt)

        if password != saved_password:
            raise bad_info

        token = await self._gen_token()
        await self._db.login_user(username=username, token=token)
        return token

    async def logout(self, username):
        return await self._db.logout_user(username=username)

    async def delete(self, username):
        return await self._db.delete_user(username=username)

    async def username_of(self, *, token):
        return await self._db.get_username(token=token)

    async def change_password(self, username, old_password, new_password):
        saved_password, salt = await self._db.get_user_password(username=username)

        old_password, _ = utils.hash_user_pass(old_password, salt)
        if old_password != saved_password:
            raise web.HTTPBadRequest(reason="old password did not match")

        _check_password(new_password)

        password, salt = utils.hash_user_pass(new_password)
        await self._db.update_user_password(
            username=username, password=password, salt=salt
        )
        return True

    async def _gen_token(self):
        while True:
            token = base64.b64encode(os.urandom(15)).decode("ascii")
            if (await self._db.get_username(token=token)) is None:
                return token
