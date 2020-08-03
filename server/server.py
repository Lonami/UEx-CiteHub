import asyncio
import configparser
import logging
import os
import subprocess
import sys

from pathlib import Path

import aiohttp
from aiohttp import web

from . import helpers, rest
from .crawler import Crawler
from .merger import Merger
from .users import Users


def serve_index(request):
    return web.FileResponse(
        os.path.join(request.app["config"]["www"]["root"], "public/index.html")
    )


APP_ROUTES = [
    web.get("/", serve_index),
    web.get("/register", serve_index),
    web.get("/login", serve_index),
    web.get("/metrics", serve_index),
    web.get("/publications", serve_index),
    web.get("/settings", serve_index),
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
        root = Path(self._app["config"]["storage"]["root"])
        self._app["users"] = Users(root)

        # TODO there will need to be a crawler and merger per user..
        self._app["crawler"] = Crawler(
            root, enabled=self._app["config"]["storage"].getboolean("crawler"),
        )

        self._app["merger"] = Merger(root, self._app["crawler"].storages())

        # Have to do this inside a coroutine to keep `aiohttp` happy
        runner = web.AppRunner(
            self._app,
            access_log_class=aiohttp.web_log.AccessLogger,
            access_log_format=aiohttp.web_log.AccessLogger.LOG_FORMAT,
            access_log=aiohttp.log.access_logger,
        )

        await runner.setup()
        sites = [
            aiohttp.web_runner.TCPSite(runner),
            aiohttp.web_runner.UnixSite(
                runner, self._app["config"]["www"]["unix_socket_path"]
            ),
        ]

        try:
            async with self._app["crawler"], self._app["merger"]:
                print("Running on:")
                for site in sites:
                    await site.start()
                    print("*", site.name)

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
