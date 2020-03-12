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


async def fetch_ms_academics(session, key, name_query):
    from .msacademics import Academics

    cached = STORAGE_ROOT / f'msacademics {name_query}'
    if cached.is_file():
        LOGGER.info('Loading cached author %s', name_query)
        with cached.open(encoding='utf-8') as fd:
            return json.load(fd)

    academics = Academics(session, key)

    PAPER_ATTRIBUTES = 'AA.AfId,AA.AfN,AA.AuId,AA.AuN,AA.DAuN,AA.DAfN,AA.S,BT,BV,C.CId,C.CN,CC,CitCon,D,DN,DOI,E,ECC,F.DFN,F.FId,F.FN,FP,I,IA,Id,J.JId,J.JN,LP,PB,Pt,RId,S,Ti,V,VFN,VSN,W,Y'
    author = await academics.evaluate(
        expr=f"Composite(AA.AuN='{name_query}')",
        attributes=PAPER_ATTRIBUTES,
        count=1000
    )
    LOGGER.info('Saving author to cache %s', name_query)
    with cached.open('w', encoding='utf-8') as fd:
        json.dump(author, fd)
    return author
