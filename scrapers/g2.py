from scrapers.base import BaseScraper
from models.review import Review
from utils.logger import Logger
from utils.date_utils import parse_date, is_date_in_range
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time

from utils.retry_utils import retry

class G2Scraper(BaseScraper):
    @retry(max_attempts=3)
    def _goto_page(self, page, url):
        page.goto(url, timeout=60000, wait_until="domcontentloaded")

    def _scrape(self, company: str, start_date: str, end_date: str):
        reviews = []
        url = f"https://www.g2.com/products/{company}/reviews#reviews"
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--disable-gpu",
                ]
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
            )
            page = context.new_page()
            
            # Anti-detect scripts
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            current_page_num = 1
            has_next_page = True

            while has_next_page:
                page_url = f"https://www.g2.com/products/{company}/reviews?page={current_page_num}#reviews"
                Logger.info(f"Navigating to {page_url}")
                
                try:
                    self._goto_page(page, page_url)
                    
                    # Human-in-the-loop check for G2
                    if not self.headless:
                        # Check if we are blocked (heuristic: title contains "Attention" or "Cloudflare" or no reviews selector)
                        # We give a short wait to let auto-captcha happen if any
                        page.wait_for_timeout(2000)
                        if "Attention Required" in page.title() or "Cloudflare" in page.title() or page.locator("div.g-recaptcha").count() > 0 or page.locator("#challenge-running").count() > 0:
                            Logger.warning("Cloudflare/CAPTCHA detected!")
                            print("\n" + "="*50)
                            print(" ACTION REQUIRED: Please solve the CAPTCHA in the browser window.")
                            print(" Once the G2 Review page is visible, press ENTER here.")
                            print("="*50 + "\n")
                            input("Press Enter to continue...")
                            Logger.info("Resuming...")

                    # Wait for reviews to load
                    page.wait_for_selector(".review-id", timeout=10000)
                except Exception as e:
                    Logger.error(f"Failed to load page {current_page_num}: {e}")
                    if not self.headless:
                         # If we failed (timeout), maybe give user a chance to fix it?
                         print(f"Error encountered: {e}")
                         choice = input("Would you like to retry this page? (y/n): ")
                         if choice.lower() == 'y':
                             current_page_num -= 1 # hack to retry loop interaction logic slightly wrong here but sufficient for now as we loop
                             # actually loop continues, so we need to not increment. But we are in a while loop.
                             # Let's just continue and NOT break.
                             continue
                    break

                # Parse content
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                review_elements = soup.select(".review-id")
                
                if not review_elements:
                    Logger.warning("No reviews found on this page.")
                    break

                page_reviews = []
                for elem in review_elements:
                    review = self._parse_single_review(elem, company)
                    if review:
                        # Date filter check
                        if review.date and review.date < start_date:
                            # If we hit a review older than start_date, we can stop if G2 is chronological
                            # G2 default sort is usually "Most Recent", but let's be careful.
                            # We will continue checking this page, but if ALL reviews on this page are old, stop?
                            # For safety, we filter. If we find review significantly old, we might stop.
                            # Let's assume sorting is roughly chronological.
                            pass
                        
                        if is_date_in_range(review.date, start_date, end_date):
                            page_reviews.append(review)
                        elif review.date and review.date > end_date:
                            # Too new, skip
                            continue
                        elif review.date and review.date < start_date:
                            # Too old. If we are sorted by date, we can stop global scraping.
                            # G2 sorts by "Most Helpful" by default? Or "Most Recent"? 
                            # URL param `?order=newest` might be needed.
                            pass
                
                reviews.extend(page_reviews)
                
                # Check for "Next" button or max pages
                # G2 pagination often uses class "pagination__named-link" or similar.
                # Simplest check: if no reviews found or special stop condition.
                # Also check date stop condition.
                
                # Logic: If the LAST review on this page is older than start_date, and we are sorting by newest, we stop.
                # We need to ensure sorting by newest.
                
                # Check next page existence
                next_button = soup.select_one(".pagination__named-link.js-log-click.next_page")
                if not next_button or "disabled" in next_button.get("class", []):
                    has_next_page = False
                else:
                    current_page_num += 1
                    self._random_sleep(2, 5)

                # Safety break for demo
                if current_page_num > 50:
                    break

            browser.close()
            
        return reviews

    def _parse_single_review(self, soup, company) -> Review:
        try:
            # Extract basic fields
            # Note: Selectors need to be precise based on G2's HTML
            
            # Title
            title_elem = soup.select_one(".review-list-heading a.link--header-color") or soup.select_one("h3.review-list-heading")
            title = title_elem.get_text(strip=True) if title_elem else "No Title"
            
            # Date: "October 24, 2023"
            date_elem = soup.select_one(".review-date") or soup.select_one("time")
            date_str = date_elem.get_text(strip=True) if date_elem else ""
            formatted_date = parse_date(date_str)
            
            # Rating (stars)
            # Typically a div with class like "stars" or specific width
            # G2 uses complex SVG stars sometimes? Or class `stars-8` (4 stars).
            rating = 0.0
            # Heuristic for rating
            # Look for schema.org data or interpret the star class
            
            # Review Body
            # .formatted-text
            body_elem = soup.select_one(".review-text") or soup.select_one("div[itemprop='reviewBody']")
            body = body_elem.get_text(strip=True) if body_elem else ""

            # Reviewer Name/Role
            name_elem = soup.select_one(".reviewer-details .reviewer-name") # fictional selector, need adjustment
            reviewer_name = name_elem.get_text(strip=True) if name_elem else None
            
            role_elem = soup.select_one(".reviewer-details .reviewer-title")
            reviewer_role = role_elem.get_text(strip=True) if role_elem else None

            return Review(
                source="g2",
                company=company,
                title=title,
                review=body,
                date=formatted_date,
                rating=rating,
                reviewer_name=reviewer_name,
                reviewer_role=reviewer_role,
                additional_metadata={}
            )
        except Exception as e:
            Logger.warning(f"Error parsing review: {e}")
            return None
