import json
from pathlib import Path


class JsonFile:
    """
    Helper class that remembers its location on disk and allows dict-like access, capable of
    loading and saving itself as JSON.
    """
    def __init__(self, path: Path, data: dict):
        self._path = path
        self._data = data

    def load(self):
        try:
            with self._path.open(encoding='utf-8') as fd:
                self._data.update(json.load(fd))
        except FileNotFoundError:
            return

    def save(self):
        if not self._path.parent.is_dir():
            self._path.parent.mkdir()

        with self._path.open('w', encoding='utf-8') as fd:
            json.dump(self._data, fd)

    def as_dict(self):
        return self._data.copy()  # no immutable dicts so make a copy

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data
