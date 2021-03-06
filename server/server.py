import asyncio
import configparser
import logging
import os
import subprocess
import sys
import shutil
import stat

from pathlib import Path

import aiohttp
from aiohttp import web

from . import helpers, rest
from .crawler import Scheduler
from .merger import Merger
from .users import Users
from .auth import Auth
from .database import Database


def serve_index(request):
    return web.FileResponse(
        os.path.join(request.app["config"]["www"]["root"], "public/index.html")
    )


# Routes also in: App.svelte, Navigation-sveñte
APP_ROUTES = [
    web.get("/", serve_index),
    web.get("/login", serve_index),
    web.get("/register", serve_index),
    web.get("/metrics", serve_index),
    web.get("/publications", serve_index),
    web.get("/profile", serve_index),
    web.get("/logout", serve_index),
]


class Server:
    def __init__(self, app):
        self._app = app

    def run(self):
        try:
            asyncio.run(self._run())
        except KeyboardInterrupt:
            pass

    async def _run(self):
        cfg = self._app["config"]
        self._app["db"] = Database(self._app["config"]["storage"]["path"])
        self._app["users"] = Users(self._app["db"])
        self._app["auth"] = Auth(
            fail_retry_delay=cfg["auth"].get("fail_retry_delay"),
            csv_whitelist=cfg["auth"].get("whitelist"),
        )
        self._app["scheduler"] = Scheduler(
            self._app["db"], enabled=cfg["storage"].getboolean("crawler"),
        )
        self._app["merger"] = Merger(self._app["db"])

        # Have to do this inside a coroutine to keep `aiohttp` happy
        runner = web.AppRunner(
            self._app,
            access_log_class=aiohttp.web_log.AccessLogger,
            access_log_format=aiohttp.web_log.AccessLogger.LOG_FORMAT,
            access_log=aiohttp.log.access_logger,
        )

        await runner.setup()

        sites = [aiohttp.web_runner.TCPSite(runner)]

        unix_socket_path = cfg["www"].get("unix_socket_path") or None
        if unix_socket_path:
            sites.append(aiohttp.web_runner.UnixSite(runner, unix_socket_path))

        try:
            async with self._app["db"], self._app["scheduler"], self._app["merger"]:
                print("Running on:")
                for site in sites:
                    await site.start()
                    print("*", site.name)

                if unix_socket_path:
                    chown_unix_socket = cfg["www"].get("chown_unix_socket") or None
                    if chown_unix_socket:
                        user, group = chown_unix_socket.split(":")
                        shutil.chown(unix_socket_path, user, group)

                    os.chmod(unix_socket_path, stat.S_IRGRP | stat.S_IWGRP)

                while True:
                    await asyncio.sleep(60 * 60)
        except KeyboardInterrupt:
            pass
        finally:
            await runner.cleanup()


def create_app():
    # Determine config path
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = "server-config.ini"
        print(
            f"note:  loaded config from {config_path}, pass a "
            f"command-line argument to override",
            file=sys.stderr,
        )

    # Open and read config
    try:
        with open(config_path, encoding="utf-8") as fd:
            config_str = fd.read()
            if not config_str or config_str.isspace():
                print(
                    f"fatal: config file {config_path} is empty, "
                    f"please copy and modify the template",
                    file=sys.stderr,
                )
                exit(1)
    except OSError as e:
        print(
            f"fatal: could not open config file {config_path}:\n"
            f"       {e.__class__.__name__} {e}".strip(),
            file=sys.stderr,
        )
        exit(1)

    # Parse config
    try:
        config = configparser.ConfigParser()
        config.read(config_path)
    except (OSError, configparser.Error) as e:
        print(
            f"fatal: could not load config file {config_path}:\n"
            f"       {e.__class__.__name__} {e}".strip(),
            file=sys.stderr,
        )
        exit(1)

    # Setup logging
    logging.basicConfig(
        level=helpers.get_log_level(config["logging"].get("level") or "WARNING"),
        filename=config["logging"].get("file") or None,
        format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s",
    )

    for option, value in config.items("logging.levels"):
        logging.getLogger(option).setLevel(level=helpers.get_log_level(value))

    # Create the aiohttp-based backend server
    logging.info("creating aiohttp server...")
    app = web.Application()
    app["config"] = config

    # Define routes
    app.router.add_routes(
        [
            *APP_ROUTES,
            *rest.ROUTES,
            web.static("/", os.path.join(config["www"]["root"], "public")),
        ]
    )
    return Server(app)
