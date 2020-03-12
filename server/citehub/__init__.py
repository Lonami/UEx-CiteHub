import json
import logging
from pathlib import Path


LOGGER = logging.getLogger('citehub')
STORAGE_ROOT = Path('data')


def ensure_storage_root_exists():
    STORAGE_ROOT.mkdir(exist_ok=True, parents=True)


async def fetch_google_scholar(session, full_name):
    from . import scholar

    cached = STORAGE_ROOT / f'gscholar {full_name}'
    if cached.is_file():
        LOGGER.info('Loading cached author %s', full_name)
        with cached.open(encoding='utf-8') as fd:
            return json.load(fd)

    async for author in scholar.search_author(session, full_name):
        LOGGER.info('Saving author to cache %s', full_name)
        with cached.open('w', encoding='utf-8') as fd:
            json.dump(author, fd)
        return author
