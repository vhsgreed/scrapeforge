"""scrapeforge: config-driven tiered scraper."""

__version__ = "0.3.0"

from .api import ScrapeResult, load_config, scrape  # noqa: E402

__all__ = ["ScrapeResult", "load_config", "scrape", "__version__"]
