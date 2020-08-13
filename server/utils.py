import hashlib
import os
import base64


PASSWORD_HASH_ITERATIONS = 100_000


def hash_user_pass(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    else:
        salt = base64.b64decode(salt)

    # https://nakedsecurity.sophos.com/2013/11/20/serious-security-how-to-store-your-users-passwords-safely/
    return (
        base64.b64encode(
            hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
            )
        ).decode("ascii"),
        base64.b64encode(salt).decode("ascii"),
    )


def parse_delay(delay):
    if not delay:
        return 0

    delay = delay.lower()

    if delay.endswith("s"):
        return int(delay[:-1])
    if delay.endswith("m"):
        return 60 * int(delay[:-1])
    if delay.endswith("h"):
        return 60 * 60 * int(delay[:-1])
    if delay.endswith("d"):
        return 24 * 60 * 60 * int(delay[:-1])

    return int(delay)
