from scrapers.base import BaseScraper
from models.review import Review
from utils.logger import Logger
from utils.date_utils import parse_date, is_date_in_range
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time

class CapterraScraper(BaseScraper):
    def _scrape(self, company: str, start_date: str, end_date: str):
        reviews = []
        
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
            # Search
            search_url = f"https://www.capterra.com/search/?query={company}"
            Logger.info(f"Searching Capterra: {search_url}")
            
            try:
                page.goto(search_url, timeout=60000)
                # Wait for results - catch block here
                product_link_loc = page.locator("a[href*='/p/']").first
                product_link_loc.wait_for(timeout=15000)
            except Exception as e:
                Logger.error(f"Search failed or no results found.")
                # check for cloudflare title
                title = page.title()
                if "Just a moment" in title or "Attention Required" in title:
                    Logger.warning("Cloudflare blocking detected on Capterra!")
                    Logger.warning("  -> Please run with --headful to manually solve the CAPTCHA.")
                else:
                    Logger.warning("  -> Possible reasons: No results for company name, or layout change.")
                browser.close()
                return []
            
            # Find the first product link
            try:
                # Get the first link containing /p/ which is the product page pattern
                href = product_link_loc.get_attribute("href")
                
                if not href:
                    Logger.warning("Found selector but no href.")
                    browser.close()
                    return []
                
                if href.startswith("http"):
                    base_url = href
                else:
                    base_url = f"https://www.capterra.com{href}"
                # Optimization: Try to go to /reviews directly
                if base_url.endswith("/"):
                    reviews_url = f"{base_url}reviews/"
                else:
                    reviews_url = f"{base_url}/reviews/"
                
                Logger.info(f"Navigating to reviews page: {reviews_url}")
                try:
                     page.goto(reviews_url, timeout=60000)
                except Exception as e:
                     Logger.warning(f"Failed to navigate to reviews page, falling back to main product page: {base_url}")
                     page.goto(base_url, timeout=60000)

                # Scroll to load lazy content
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)

                
            except Exception as e:
                Logger.error(f"Error navigating to product: {e}")
                browser.close()
                return []

            # 2. Extract Reviews (Pagination)
            # Capterra often uses "Load More" or pagination numbers.
            
            has_more = True
            current_page = 1
            
            while has_more:
                Logger.info(f"Scraping page {current_page}...")
                
                # Parse current view
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                # Extract reviews
                # Strategy 1: Generic card selector (Notion style - Main Page)
                cards = soup.select("div.shadow-elevation-2.bg-card")
                review_cards = []
                for card in cards:
                    text = card.get_text()
                    if "Overall Rating" in text or "Pros" in text:
                        review_cards.append(card)
                
                # Strategy 2: ID-based selector (Codecademy style)
                if not review_cards:
                    reviews_container = soup.find(id="reviews")
                    if reviews_container:
                        # Get direct children divs
                        cards = reviews_container.find_all("div", recursive=False)
                        for card in cards:
                            text = card.get_text()
                            if "Overall Rating" in text or "Pros" in text:
                                review_cards.append(card)

                # Strategy 3: Dedicated Reviews Page Selector (Hash Class)
                # Found class: e1xzmg0z c1ofrhif typo-10...
                # We use the hash class e1xzmg0z which seems to be the card identifier
                if not review_cards:
                     cards = soup.select("div[class*='e1xzmg0z']")
                     for card in cards:
                        text = card.get_text()
                        if "Overall Rating" in text or "Pros" in text:
                            review_cards.append(card)

                # Strategy 4: Text-based Heuristic (Last Resort)
                if not review_cards:
                    # Find all "Pros" labels, traverse up to find container
                    pros_labels = soup.find_all(string=lambda t: "Pros" in t if t else False)
                    seen_cards = set()
                    for label in pros_labels:
                        # Safety check for short label to avoid matching long paragraph text
                        if len(label) > 50: continue
                        
                        parent = label.parent
                        # Traverse up 4-5 levels to find a likely container (div)
                        curr = parent
                        for _ in range(5):
                            if curr and curr.name == 'div':
                                # Heuristic: Review cards usually have multiple children (rating, date, body)
                                if len(list(curr.children)) > 3:
                                    if curr not in seen_cards:
                                        review_cards.append(curr)
                                        seen_cards.add(curr)
                                    break
                            if curr: curr = curr.parent
                            else: break

                if not review_cards:
                     # Fallback to old selector if new one fails (unlikely given analysis)
                    review_cards = soup.select("div[data-testid='review-card']")
                
                if not review_cards:
                    Logger.warning("No reviews found on page.")
                    # Check for blocking again just in case
                    if "Just a moment" in page.title():
                         Logger.warning("  -> Cloudflare blocking active.")
                    break
                
                for card in review_cards:
                    review = self._parse_single_review(card, company)
                    if review:
                        if is_date_in_range(review.date, start_date, end_date):
                            reviews.append(review)
                
                # Pagination
                # Look for "Next" button or "Show More"
                # Button usually has "Next" text or class.
                try:
                    next_btn = page.locator("button:has-text('Next')")
                    if next_btn.is_visible() and next_btn.is_enabled():
                        next_btn.click()
                        page.wait_for_timeout(3000) # wait for ajax
                        current_page += 1
                    else:
                        has_more = False
                except:
                    has_more = False
                
                if current_page > 50: # Safety
                    break

            browser.close()
            
        return reviews

    def _parse_single_review(self, soup, company) -> Review:
        try:
            # 1. Author and Metadata
            # Look for the author section: <span class="typo-20 text-neutral-99 font-semibold">Marko S.</span>
            reviewer_name = "Anonymous"
            reviewer_role = None
            
            author_span = soup.select_one("span.typo-20.font-semibold.text-neutral-99")
            if author_span:
                reviewer_name = author_span.get_text(strip=True)
                
                # Check siblings for role/industry (text nodes after BRs in parent)
                parent_div = author_span.parent
                if parent_div:
                    # Get all text separator by newlines
                    full_text = parent_div.get_text("\n", strip=True)
                    parts = full_text.split('\n')
                    # parts[0] is name. parts[1] might be role.
                    if len(parts) > 1 and parts[1] != reviewer_name:
                         # Filter out "Used the software for"
                         if "Used the software" not in parts[1]:
                             reviewer_role = parts[1]

            # 2. Title and Date
            # <h3 class="typo-20 font-semibold">"Title"</h3>
            # <div class="typo-0 text-neutral-90">Date</div>
            title_tag = soup.select_one("h3.typo-20.font-semibold")
            title = title_tag.get_text(strip=True).strip('"') if title_tag else "No Title"
            
            date = ""
            date_div = soup.select_one("div.typo-0.text-neutral-90")
            if date_div:
                date_str = date_div.get_text(strip=True)
                date = parse_date(date_str)

            # 3. Rating
            # We can stick to valid regex or look for the numeric value
            rating = 0.0
            rating_container = soup.select_one("div[data-testid='Overall Rating-rating'] span.e1xzmg0z.sr2r3oj")
            if not rating_container:
                 # Try the main rating at top if semantic one is missing
                 rating_container = soup.select_one("div[data-testid='rating'] span.e1xzmg0z.sr2r3oj")
            
            if rating_container:
                try:
                    rating = float(rating_container.get_text(strip=True))
                except:
                    pass
            
            if rating == 0.0:
                 # Fallback to regex
                 text_content = soup.get_text("\n", strip=True)
                 import re
                 rating_match = re.search(r'(\d+(?:\.\d+)?)\s*Overall Rating', text_content, re.IGNORECASE)
                 if rating_match:
                     rating = float(rating_match.group(1))

            # 4. Review Body (Pros/Cons/General)
            # General text: <p>...</p> inside <div class="!mt-4 space-y-6">
            review_parts = []
            
            # Initial summary text
            summary_div = soup.select_one("div.\\!mt-4.space-y-6")
            if summary_div:
                review_parts.append(summary_div.get_text(strip=True))

            # Pros/Cons
            # Look for spans with "Pros" or "Cons" text
            pros_span = soup.find("span", string=lambda t: "Pros" in t if t else False)
            if pros_span:
                 # The text is usually in a sibling <p> or parent's sibling
                 # Based on HTML: span.parent is div.space-y-2. Sibling is p.
                 pros_container = pros_span.find_parent("div", class_="space-y-2")
                 if pros_container:
                     p_tag = pros_container.find("p")
                     if p_tag:
                         review_parts.append(f"Pros: {p_tag.get_text(strip=True)}")

            cons_span = soup.find("span", string=lambda t: "Cons" in t if t else False)
            if cons_span:
                 cons_container = cons_span.find_parent("div", class_="space-y-2")
                 if cons_container:
                     p_tag = cons_container.find("p")
                     if p_tag:
                         review_parts.append(f"Cons: {p_tag.get_text(strip=True)}")

            review_text = "\n".join(review_parts)
            
            # Fallback if specific extraction failed
            if not review_text or len(review_text) < 10:
                review_text = soup.get_text("\n", strip=True)[:500] + "..."

            return Review(
                source="capterra",
                company=company,
                title=title,
                review=review_text.strip(),
                date=date,
                rating=rating,
                reviewer_name=reviewer_name,
                reviewer_role=reviewer_role,
                additional_metadata={}
            )
        except Exception as e:
            Logger.warning(f"Error parsing Capterra review: {e}")
            return None
