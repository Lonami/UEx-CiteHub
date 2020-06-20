import json

from dataclasses import dataclass
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


@dataclass
class Publication:
    id: Optional[str]
    author: Optional[Author]
    citations: Optional[List['Publication']]


class Storage:
    # Class responsible for storing all information from various sources
    # TODO maybe the url should be stored here and used as path?
    def __init__(self, root: Path):
        self._root = root
        self._profile_file = root / 'profile.json'
        self._profile = {
            'user-author-id': None,
            'user-publications': [],
        }

    @property
    def user_author_id(self):
        return self._profile['user-author-id']

    @user_author_id.setter
    def user_author_id(self, value):
        self._profile['user-author-id'] = value

    @property
    def user_publications(self):
        return self._profile['user-publications']

    @user_publications.setter
    def user_publications(self, value):
        self._profile['user-publications'] = value

    def load(self):
        utils.try_load_json(self._profile, self._profile_file)

    def save(self):
        utils.save_json(self._profile, self._profile_file)
