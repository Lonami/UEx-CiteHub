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
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    ref: Optional[str] = None
    extra: Optional[dict] = None

    def unique_path_name(self) -> str:
        if self.id:
            return f"pub/{filename_for(self.id)}"
        else:
            return f"pub/uniden/{filename_for(self.name)}"
