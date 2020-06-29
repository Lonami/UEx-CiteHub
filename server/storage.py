import hashlib
import json
import uuid

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from . import utils


def filename_for(identifier):
    # `identifier` may consist of invalid path characters such as '/', but the paths still need
    # to be unique. We can't use `base64` because paths are case insensitive on some systems so
    # there could be collisions. We just go on the safe side and use the sha256 sum.
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


# What data we store is inherently tied to the storage itself so we put it here
@dataclass
class Author:
    full_name: str
    id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    extra: Optional[dict] = None

    def unique_path_name(self) -> str:
        if self.id:
            return f"author/{filename_for(self.id)}"
        else:
            return f"author/uniden/{filename_for(self.full_name)}"


@dataclass
class Publication:
    name: str
    id: Optional[str] = None  # must be present for self publications
    # TODO review how we're saving authors
    # TODO probably better saving paths (as references) here?
    authors: Optional[List[Author]] = None
    cit_paths: Optional[
        List[str]
    ] = None  # unique_path_name of publications citing this source
    extra: Optional[dict] = None

    def unique_path_name(self) -> str:
        if self.id:
            return f"pub/{filename_for(self.id)}"
        else:
            return f"pub/uniden/{filename_for(self.name)}"


class Storage:
    # Class responsible for storing all information from various sources
    def __init__(self, root: Path):
        self._root = root
        self._profile_file = root / "profile.json"
        self._profile = {
            "user-author-id": None,
            "user-pub-ids": [],
        }

    @property
    def user_author_id(self):
        """Author identifier of the current user."""
        return self._profile["user-author-id"]

    @user_author_id.setter
    def user_author_id(self, value):
        self._profile["user-author-id"] = value

    @property
    def user_pub_ids(self):
        """Publication identifiers owned by the current user."""
        return self._profile["user-pub-ids"]

    @user_pub_ids.setter
    def user_pub_ids(self, value):
        self._profile["user-pub-ids"] = value

    def save_author(self, author: Author):
        path = self._root / author.unique_path_name()
        utils.save_json(asdict(author), path)

    def save_pub(self, pub: Publication):
        # TODO currently we overwrite but maybe we could have smarter merging?
        path = self._root / pub.unique_path_name()
        utils.save_json(asdict(pub), path)

    def load_pub(self, iden=None, path=None) -> Publication:
        assert iden is not None or path is not None
        data = {}
        # TODO not ideal to make a pub instance just for the name
        if path is None:
            path = Publication(id=iden, name="").unique_path_name()
        path = self._root / path
        utils.try_load_json(data, path)
        # TODO the nested author doesn't get loaded correctly
        return Publication(**data)

    def load(self):
        utils.try_load_json(self._profile, self._profile_file)

    def save(self):
        utils.save_json(self._profile, self._profile_file)
