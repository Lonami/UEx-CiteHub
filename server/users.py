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
    def __init__(self, root):
        self._file = root / "users.json"

        # {username: {salt, password, token}}
        self._users = {}
        utils.try_load_json(self._users, self._file)

        self._token_to_user = {
            v["token"]: u for u, v in self._users.items() if v["token"]
        }

    def register(self, username, password):
        if len(username) > MAX_DETAILS_LENGTH:
            raise web.HTTPBadRequest(
                reason=f"username must be {MAX_DETAILS_LENGTH} characters long or less"
            )

        if not USERNAME_RE.match(username):
            raise web.HTTPBadRequest(
                reason=f"username must use lowercase ascii letters only"
            )

        if username in self._users:
            raise web.HTTPBadRequest(reason=f"username is already occupied")

        _check_password(password)

        salt, password = utils.hash_user_pass(password)
        token = self._gen_token()
        self._users[username] = {
            "salt": salt,
            "password": password,
            "token": token,
        }
        self._token_to_user[token] = username
        self._save()
        return token

    def login(self, username, password):
        bad_info = web.HTTPBadRequest(reason="invalid username or password")

        details = self._users.get(username)
        if not details:
            raise bad_info

        _, password = utils.hash_user_pass(password, details["salt"])
        if password != details["password"]:
            raise bad_info

        token = self._gen_token()
        details["token"] = token
        self._users[username] = details
        self._token_to_user[token] = username
        self._save()
        return token

    def logout(self, token):
        user = self._token_to_user.pop(token, None)
        if not user:
            return False

        self._users[user]["token"] = None
        self._save()
        return True

    def delete(self, token):
        user = self._token_to_user.pop(token, None)
        if not user:
            return False

        del self._users[user]
        self._save()
        return True

    def username_of(self, *, token):
        return self._token_to_user.get(token)

    def change_password(self, old_password, new_password, *, token):
        username = self._token_to_user.get(token)
        if not username:
            raise web.HTTPForbidden()

        details = self._users[username]
        _, password = utils.hash_user_pass(old_password, details["salt"])
        if password != details["password"]:
            raise web.HTTPBadRequest(reason="old password did not match")

        _check_password(new_password)

        salt, password = utils.hash_user_pass(new_password)
        details["salt"] = salt
        details["password"] = password
        self._save()
        return True

    def _gen_token(self):
        while True:
            token = base64.b64encode(os.urandom(15)).decode("ascii")
            if token not in self._token_to_user:
                return token

    def _save(self):
        utils.save_json(self._users, self._file)
