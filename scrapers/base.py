from abc import ABC, abstractmethod
from typing import List, Optional
from models.review import Review
from utils.logger import Logger
import requests
from time import sleep
import random

class BaseScraper(ABC):
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.session = requests.Session()
        # Common headers to look like a browser
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def fetch_reviews(self, company: str, start_date: str, end_date: str) -> List[Review]:
        """
        Main entry point for scraping reviews.
        """
        Logger.info(f"Starting scrape for {company} from {start_date} to {end_date}")
        reviews = []
        try:
            reviews = self._scrape(company, start_date, end_date)
        except Exception as e:
            Logger.error(f"Error scraping {company}: {str(e)}")
        
        if not reviews:
            Logger.warning(f"Collected 0 reviews for {company}. Possible reasons:")
            Logger.warning("  - No reviews found for the specified date range (try widening the range).")
            Logger.warning("  - No reviews exist for this product.")
            Logger.warning("  - Network issue or Anti-bot blocking (try --headful mode).")
            Logger.warning("  - Selector mismatch (site layout changed).")
        else:
            Logger.info(f"Collected {len(reviews)} reviews for {company}")
        return reviews

    @abstractmethod
    def _scrape(self, company: str, start_date: str, end_date: str) -> List[Review]:
        """
        To be implemented by subclasses.
        Should handle pagination and stop when dates are out of range.
        """
        pass

    def _random_sleep(self, min_seconds: float = 2.0, max_seconds: float = 5.0):
        sleep_time = random.uniform(min_seconds, max_seconds)
        Logger.info(f"Sleeping for {sleep_time:.2f} seconds...")
        sleep(sleep_time)

    def _get_page(self, url: str) -> Optional[str]:
        """
        Helper to fetch a page with error handling.
        """
        try:
            Logger.info(f"Fetching {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            Logger.error(f"Failed to fetch {url}: {e}")
            return None
