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


class Server:
    def __init__(self, app):
        self._app = app

    def run(self):
        try:
            asyncio.run(self._run())
        except KeyboardInterrupt:
            pass

    async def _run(self):
        runner = web.AppRunner(
            self._app,
            access_log_class=aiohttp.web_log.AccessLogger,
            access_log_format=aiohttp.web_log.AccessLogger.LOG_FORMAT,
            access_log=aiohttp.log.access_logger
        )

        await runner.setup()
        site = aiohttp.web_runner.TCPSite(runner)

        try:
            async with self._app['crawler']:
                await site.start()
                print('Running on:', site.name)
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
        config_path = 'server-config.ini'
        print(f'note:  loaded config from {config_path}, pass a '
              f'command-line argument to override', file=sys.stderr)

    # Open and read config
    try:
        with open(config_path, encoding='utf-8') as fd:
            config_str = fd.read()
            if not config_str or config_str.isspace():
                print(f'fatal: config file {config_path} is empty, '
                      f'please copy and modify the template', file=sys.stderr)
                exit(1)
    except OSError as e:
        print(f'fatal: could not open config file {config_path}:\n'
              f'       {e.__class__.__name__} {e}'.strip(), file=sys.stderr)
        exit(1)

    # Parse config
    try:
        config = configparser.ConfigParser()
        config.read(config_path)
    except (OSError, configparser.Error) as e:
        print(f'fatal: could not load config file {config_path}:\n'
              f'       {e.__class__.__name__} {e}'.strip(), file=sys.stderr)
        exit(1)

    # Setup logging
    logging.basicConfig(
        level=helpers.get_log_level(config['logging'].get('level') or 'WARNING'),
        filename=config['logging'].get('file') or None,
        format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s'
    )

    for option, value in config.items('logging.levels'):
        logging.getLogger(option).setLevel(level=helpers.get_log_level(value))

    # Build svelte-based frontend application
    logging.info('building frontend...')
    ret = subprocess.run(['npm', 'run', 'build'], cwd=config['www']['root']).returncode
    if ret != 0:
        exit(ret)

    # Create the aiohttp-based backend server
    logging.info('creating aiohttp server...')
    app = web.Application()
    app['config'] = config
    app['crawler'] = Crawler(Path(config['storage']['root']))

    # Define routes
    app.router.add_routes([
        web.get('/', lambda r: web.HTTPSeeOther('/index.html')),
        *rest.ROUTES,
        web.static('/', os.path.join(config['www']['root'], 'public')),
    ])
    return Server(app)
