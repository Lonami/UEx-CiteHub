import asyncio
from . import utils
from aiohttp import web
from collections import deque

_CLEAN_RATE_LIMIT_THRESHOLD = 1000
_CLEAN_RATE_LIMIT_DELAY = 10


class Auth:
    def __init__(self, *, fail_retry_delay, csv_whitelist):
        self._fail_retry_delay = utils.parse_delay(fail_retry_delay)
        self._whitelist = set(
            filter(bool, map(str.strip, (csv_whitelist or "").split(",")))
        )

        self._rate_limit_ip_to_due = {}
        self._rate_limit_last_cleaned = 0

    def check_whitelist(self, username):
        if self._whitelist and username not in self._whitelist:
            # pretend we're having issues to give no clues to potential attackers
            raise web.HTTPInternalServerError()

    def apply_rate_limit(self, request):
        if self._fail_retry_delay == 0:
            return

        now = asyncio.get_event_loop().time()

        if (
            len(self._rate_limit_ip_to_due) >= _CLEAN_RATE_LIMIT_THRESHOLD
            and (now - self._rate_limit_last_cleaned) > _CLEAN_RATE_LIMIT_DELAY
        ):
            remove = [k for k, v in self._rate_limit_ip_to_due.items() if now >= v]
            for k in remove:
                del self._rate_limit_ip_to_due[k]
            self._rate_limit_last_cleaned = now

        # we use the ip address; this can easily be faked with proxies but it's already putting
        # enough hassle on potential attackers
        due = self._rate_limit_ip_to_due.get(request.remote, 0)
        if now >= due:
            self._rate_limit_ip_to_due[request.remote] = now + self._fail_retry_delay
        else:
            raise web.HTTPTooManyRequests()
