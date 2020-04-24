from dataclasses import dataclass
from enum import Enum
from typing import List, Generator, Iterable, Optional
import difflib
import statistics
import itertools
import abc
from . import utils

# Default threshold to consider two different data the same
SIMILARITY_THRESHOLD = 0.8

# Different weights when comparing data

# The titles should be nearly identical so it has the most weight
WEIGHT_SIMILAR_TITLE = 0.6

# It's important that authors match, however they may go by different names
WEIGHT_SIMILAR_AUTHORS = 0.3

# The problem is different sources have different cites
WEIGHT_SIMILAR_CITES = 0.1

# If this ratio of cites is reached, the weight for cites will be maximum
MAX_SIMILAR_CITES_RATIO = 0.2

# If a shorter title's length is not "close enough" to the length of
# a longer title's length, then they won't be considered equal at all.
MAX_TITLE_LENGTH_DIFF_RATIO = 0.1


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
    source: Source
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
    cited_by: Optional[List['Publication']]

    def similarity(self, other: 'Publication') -> float:
        shorter, longer = sorted(map(len, (self.title, other.title)))
        if (longer - shorter) < (longer * MAX_TITLE_LENGTH_DIFF_RATIO):
            return 0

        title_score = WEIGHT_SIMILAR_TITLE * difflib.SequenceMatcher(
            None, self.title, other.title).ratio()

        author_score = WEIGHT_SIMILAR_AUTHORS * self.author.similarity(other.author)

        # TODO this may recurse for a very long time if we have
        #      `cited_by` data for the cites, and those do too, etc.
        #
        # TODO the above is addressed by having cited_by optional but we don't handle it
        similar_cites = sum(
            1
            for a, b in itertools.product(self.cited_by, other.cited_by)
            if a.similarity(b) >= SIMILARITY_THRESHOLD
        )

        most_cites = max(map(len, self.cited_by, other.cited_by))

        cite_score = WEIGHT_SIMILAR_CITES * utils.clamp(
            utils.map_range(
                similar_cites / most_cites,
                0,
                1,
                0,
                MAX_SIMILAR_CITES_RATIO
            ),
            0,
            1
        )

        score = sum((title_score, author_score, cite_score))
        return utils.clamp(score, 0, 1)


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
        for left, right in utils.pairwise(group):
            yield Merge(left=left, kind=MergeType.AUTOMATIC, right=right)
