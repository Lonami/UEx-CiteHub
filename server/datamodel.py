from dataclasses import dataclass
from enum import Enum
from typing import List, Generator, Iterable
import statistics
import itertools
import abc


def pairwise(iterable):
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


# Default threshold to consider two different data the same
SIMILARITY_THRESHOLD = 0.9


class Comparable(abc.ABC):
    """
    Indicates that two models are comparable with instances of itself.
    """

    @abc.abstractmethod
    def similarity(self, other: 'Comparable') -> float:
        """
        Returns the similarity percentage between this item
        and another one as a real number between 0 and 1 inclusive.
        """


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
class Author(Comparable):
    """
    Original author data from a certain `Source`.
    """

    iden: Identifier
    first_name: str
    last_name: str
    aliases: List[str]

    def similarity(self, other: 'Author') -> float:
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

    def similarity(self, other: 'Publication') -> float:
        raise NotImplementedError


@dataclass
class Merge:
    """
    Represents a merge between two `Comparable` items.
    """
    left: Comparable
    kind: MergeType
    right: Comparable


def merge_items(
        items: Iterable[Comparable],
        threshold: float = SIMILARITY_THRESHOLD,
) -> Generator[Merge]:
    """
    Merges items from various sources into one.
    """

    # Work on a copy, we will be deleting items from the list as we go.
    items = items[:]

    similar_groups = []

    while items:
        item_i = items.pop()
        done = False

        # Check if it fits in any of the previous groups
        for group in similar_groups:
            sim = statistics.mean(item_i.similarity(pub) for pub in group)
            if sim >= threshold:
                group.append(item_i)
                done = True
                break

        if done:
            continue

        # If it doesn't fit in any of the previous groups try to pair it with
        # another individual publication.
        for j in range(len(items)):
            item_j = items[j]
            sim = item_i.similarity(item_j)
            if sim >= threshold:
                similar_groups.append([item_i, item_j])
                del items[j]
                done = True
                break

        if done:
            continue

        # If none of the other publications are similar to this one make a
        # group with this publication alone.
        similar_groups.append([item_i])

    # Yield the merged results with the similar groups
    for group in similar_groups:
        for left, right in pairwise(group):
            yield Merge(left=left, kind=MergeType.AUTOMATIC, right=right)
