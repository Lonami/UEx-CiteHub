from dataclasses import dataclass
from enum import Enum
from typing import List


class Source(Enum):
    """
    Indicates where does the data come from.
    """

    # https://scholar.google.com
    GOOGLE_SCHOLAR = 'google_scholar'

    # https://academic.microsoft.com
    MICROSOFT_ACADEMICS = 'microsoft_academics'

    # https://dev.elsevier.com
    SCOPUS = 'scopus'


class MergeType(Enum):
    """
    Indicates how a merge was made.
    """

    # The merge was made automatically
    AUTOMATIC = 'automatic'

    # The merge was made manually
    MANUAL = 'manual'

    # An automatic merge was split manually
    SPLIT = 'split'


# Identifier type used by original data
Identifier = str


@dataclass
class Author:
    """
    Original author data from a certain `Source`.
    """

    iden: Identifier
    first_name: str
    last_name: str
    aliases: List[str]

    def similarity(self, other) -> float:
        """
        Returns the similarity percentage between this `Author`
        and another one as a real number between 0 and 1 inclusive.
        """
        raise NotImplementedError


@dataclass
class Publication:
    """
    Original publication data from a certain `Source`.
    """

    iden: Identifier
    author: Author
    source: Source
    title: str
    year: int
    cited_by: List['Publication']

    def similarity(self, other) -> float:
        """
        Returns the similarity percentage between this `Publication`
        and another one as a real number between 0 and 1 inclusive.
        """
        raise NotImplementedError


@dataclass
class MergedAuthor:
    """
    Indicates that two `Author` are bound together.
    """
    left: Author
    kind: MergeType
    right: Author


@dataclass
class MergedPublication:
    """
    Indicates that two `Publication` are bound together.
    """
    left: Publication
    kind: MergeType
    right: Publication
