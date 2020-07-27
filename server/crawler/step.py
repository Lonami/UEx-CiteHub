from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional
from ..storage import Author, Publication


@dataclass
class Step:
    # Delay, in seconds, before the next step should be taken
    delay: int

    # Next stage
    stage: Any

    # Any `Author` found along the way
    authors: List[Author] = field(default_factory=list)

    # Publications made by the current user
    self_publications: List[Publication] = field(default_factory=list)

    # Mapping ``{Publication ID: Publications citing the former}``
    citations: Mapping[str, List[Publication]] = field(default_factory=dict)


# TODO would be interesting to have self-citations (in which cites you're an author too)
# TODO capitalize first letter of names for consistency
# TODO show total count of articles (maybe per-source too)
# TODO cites per year graph would be nice (along with hx)

# avg number of authors in pubs
