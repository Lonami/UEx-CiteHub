from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional
from ..storage import Author, Publication


@dataclass
class Step:
    # Delay, in seconds, before the next step should be taken
    delay: int

    # Next stage
    stage: Any

    # Information about the current user's `Author`
    self_author: Optional[Author] = None

    # Any other `Author` found along the way
    authors: List[Author] = field(default_factory=list)

    # Publications made by the current user
    self_publications: List[Publication] = field(default_factory=list)

    # Mapping ``{Publication ID: Publications citing the former}``
    citations: Mapping[str, List[Publication]] = field(default_factory=dict)
