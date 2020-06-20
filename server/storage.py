import hashlib
import json
import uuid

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from . import utils


# What data we store is inherently tied to the storage itself so we put it here
@dataclass
class Author:
    id: Optional[str]
    full_name: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    extra: Optional[dict]

    def name(self):
        if self.full_name:
            return self.full_name

        first = self.first_name or ''
        last = self.last_name or ''
        full = f'{first} {last}'.strip()
        if full:
            return full

        # Python's `id()` is not guaranteed to be unique forever but we want a consistent name
        gen_name = getattr(self, '_gen_name', None)
        if not gen_name:
            gen_name = f'(unnamed {uuid.uuid4().hex})'
            self._gen_name = gen_name
        return gen_name


@dataclass
class Publication:
    id: Optional[str]
    authors_ids: Optional[List[str]]
    citations: Optional[List['Publication']]
    extra: Optional[dict]


def filename_for(identifier):
    # `identifier` may consist of invalid path characters such as '/', but the paths still need
    # to be unique. We can't use `base64` because paths are case insensitive on some systems so
    # there could be collisions. We just go on the safe side and use the sha256 sum.
    return hashlib.sha256(identifier.encode('utf-8')).hexdigest()


class Storage:
    # Class responsible for storing all information from various sources
    # TODO maybe the url should be stored here and used as path?
    def __init__(self, root: Path):
        self._root = root
        self._profile_file = root / 'profile.json'
        self._profile = {
            'user-author-id': None,
            'user-pub-ids': [],
        }

    @property
    def user_author_id(self):
        return self._profile['user-author-id']

    @user_author_id.setter
    def user_author_id(self, value):
        self._profile['user-author-id'] = value

    @property
    def user_pub_ids(self):
        return self._profile['user-pub-ids']

    @user_pub_ids.setter
    def user_pub_ids(self, value):
        self._profile['user-pub-ids'] = value

    def save_author(self, author: Author):
        if author.id:
            path = self._root / filename_for(author.id)
        else:
            path = self._root / 'uniden' / filename_for(author.name())

        utils.save_json(asdict(author), path)

    def save_pub(self, pub: Publication):
        path = self._root / filename_for(pub.id)
        utils.save_json(asdict(pub), path)

    def load(self):
        utils.try_load_json(self._profile, self._profile_file)

    def save(self):
        utils.save_json(self._profile, self._profile_file)
