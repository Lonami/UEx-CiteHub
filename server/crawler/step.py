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

    # For convenience the authors are stored as `Author` in `Publication`, but before asving
    # them they should be converted to paths.
    #
    # The alternative is to create a separate list of when parsing everywhere, generate
    # the list of paths from there and use that in the publications, while also returning
    # the separate list. All in all it's a lot more cumbersome and error-prone, so instead
    # the types are violated for a bit here.
    def fix_authors(self):
        for pub in self.self_publications:
            for i, author in enumerate(pub.authors):
                if isinstance(author, Author):
                    self.authors.append(author)
                    pub.authors[i] = author.unique_path_name()

        for citations in self.citations.values():
            for cit in citations:
                for i, author in enumerate(cit.authors):
                    if isinstance(author, Author):
                        self.authors.append(author)
                        cit.authors[i] = author.unique_path_name()


# TODO would be interesting to have self-citations (in which cites you're an author too)
# TODO show total count of articles (maybe per-source too)
# TODO cites per year graph would be nice (along with hx)

# avg number of authors in pubs
