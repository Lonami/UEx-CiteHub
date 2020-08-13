from .aminer import CrawlArnetMiner
from .dimensions import CrawlDimensions
from .ieeexplore import CrawlExplore
from .msacademics import CrawlAcademics
from .researchgate import CrawlResearchGate
from .scholar import CrawlScholar


def _get_crawlers():
    crawlers = {}
    for cls in (
        CrawlArnetMiner,
        CrawlDimensions,
        CrawlExplore,
        CrawlAcademics,
        CrawlResearchGate,
        CrawlScholar,
    ):
        ns = cls.namespace()
        dup = crawlers.get(ns)
        if dup is None:
            crawlers[ns] = cls
        else:
            raise RuntimeError(f"crawlers key {ns} is not unique ({cls} and {dup})")
    return crawlers


CRAWLERS = _get_crawlers()
