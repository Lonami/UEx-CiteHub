from .aminer import CrawlArnetMiner
from .dimensions import CrawlDimensions
from .ieeexplore import CrawlExplore
from .msacademics import CrawlAcademics
from .researchgate import CrawlResearchGate
from .scholar import CrawlScholar

CRAWLERS = (
    CrawlArnetMiner,
    CrawlDimensions,
    CrawlExplore,
    CrawlAcademics,
    CrawlResearchGate,
    CrawlScholar,
)
