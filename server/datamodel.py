from dataclasses import dataclass
from enum import Enum
from typing import List, Generator
import statistics
import itertools


def pairwise(iterable):
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


# Default threshold to consider two different data the same
SIMILARITY_THRESHOLD = 0.9


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


def merge_publications(
        publications: List[Publication],
        threshold: float = SIMILARITY_THRESHOLD,
) -> Generator[MergedPublication]:
    """
    Merges publications from various sources into one.
    """

    # Work on a copy, we will be deleting items from the list as we go.
    publications = publications[:]

    similar_groups = []

    while publications:
        pub_i = publications.pop()
        done = False

        # Check if it fits in any of the previous groups
        for group in similar_groups:
            sim = statistics.mean(pub_i.similarity(pub) for pub in group)
            if sim >= threshold:
                group.append(pub_i)
                done = True
                break

        if done:
            continue

        # If it doesn't fit in any of the previous groups try to pair it with
        # another individual publication.
        for j in range(len(publications)):
            pub_j = publications[j]
            sim = pub_i.similarity(pub_j)
            if sim >= threshold:
                similar_groups.append([pub_i, pub_j])
                del publications[j]
                done = True
                break

        if done:
            continue

        # If none of the other publications are similar to this one make a
        # group with this publication alone.
        similar_groups.append([pub_i])

    # Yield the merged results with the similar groups
    for group in similar_groups:
        for left, right in pairwise(group):
            yield MergedPublication(left=left, kind=MergeType.AUTOMATIC, right=right)
