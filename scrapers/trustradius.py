from scrapers.base import BaseScraper
from models.review import Review
from utils.logger import Logger
from utils.date_utils import parse_date, is_date_in_range
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

class TrustRadiusScraper(BaseScraper):
    def _scrape(self, company: str, start_date: str, end_date: str):
        reviews = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                ]
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = context.new_page()
            
            # TrustRadius URL structure: https://www.trustradius.com/products/{company}/reviews
            # Note: Company name format might differ (e.g. notion-so vs notion).
            # We'll try direct navigation.
            url = f"https://www.trustradius.com/products/{company}/reviews/all"
            Logger.info(f"Navigating to {url}")
            
            try:
                page.goto(url, timeout=60000)
                # Check for 404
                if "Page Not Found" in page.title():
                    Logger.warning(f"Product page not found for {company}")
                    browser.close()
                    return []
                
                page.wait_for_selector(".review-list, .serp-card, article", timeout=15000)
            except Exception as e:
                Logger.error(f"Failed to load TrustRadius: {e}")
                browser.close()
                return []

            # Pagination loop
            has_next = True
            current_page = 1
            
            while has_next:
                Logger.info(f"Processing page {current_page}")
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                # Extract reviews
                # Selectors guessed. TrustRadius uses semantic HTML often.
                # Look for article tags or class "review"
                review_cards = soup.select("article") or soup.select(".serp-card")
                
                if not review_cards:
                    Logger.warning("No reviews found.")
                    break
                    
                for card in review_cards:
                    review = self._parse_single_review(card, company)
                    if review:
                        if is_date_in_range(review.date, start_date, end_date):
                            reviews.append(review)
                        # Date logic for stopping?
                        
                # Next page
                # Look for "Next" button
                try:
                    next_link = page.locator("a[aria-label='Next Page']")
                    if next_link.is_visible():
                        next_link.click()
                        page.wait_for_timeout(3000)
                        current_page += 1
                    else:
                        has_next = False
                except:
                    has_next = False
                    
                if current_page > 50:
                    break

            browser.close()
            return reviews

    def _parse_single_review(self, soup, company) -> Review:
        try:
            # Extract Text for Regex
            text_content = soup.get_text(" ", strip=True)
            
            # Title
            # Usually h3 or h2
            title_tag = soup.find(['h2', 'h3', 'h4'], class_=lambda c: c and 'heading' in c.lower())
            if not title_tag:
                 title_tag = soup.find(['h2', 'h3'])
            title = title_tag.get_text(strip=True) if title_tag else "No Title"

            # Date
            # use regex on the whole text content of the article
            # Pattern: "October 22, 2025"
            import re
            date_pattern = re.compile(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}')
            date_match = date_pattern.search(text_content)
            date = parse_date(date_match.group(0)) if date_match else ""

            # Rating
            # Pattern: "Rating: 8 out of 10" or "Score 8 out of 10"
            rating = 0.0
            rating_match = re.search(r'Rating:\s*(\d+)', text_content, re.IGNORECASE)
            if rating_match:
                rating = float(rating_match.group(1))
            else:
                 # Try finding just the score "8 out of 10"
                 score_match = re.search(r'(\d+)\s+out of\s+10', text_content, re.IGNORECASE)
                 if score_match:
                     rating = float(score_match.group(1))

            # Review Body
            # TrustRadius reviews are split into questions/answers and pros/cons
            review_parts = []
            
            # 1. Long form answers (Use Case, etc)
            # Class looks like 'ReviewAnswer_longForm__wwyHy'
            answers = soup.find_all(class_=lambda c: c and 'ReviewAnswer_longForm' in c)
            for ans in answers:
                text = ans.get_text("\n", strip=True)
                if text:
                    review_parts.append(text)
            
            # 2. Pros and Cons
            # Class looks like 'ReviewAnswer_pros-list__LQAhd'
            pros_cons = soup.find_all(class_=lambda c: c and 'ReviewAnswer_review-answer' in c)
            for pc in pros_cons:
                text = pc.get_text("\n", strip=True)
                if text:
                    review_parts.append(text)

            review_text = "\n\n".join(review_parts)
            
            # Fallback 1: User reported 'Review_content' / data-testid='content' (Slack specific?)
            if not review_text:
                content_tag = soup.find(class_=lambda c: c and 'Review_content' in c)
                if not content_tag:
                    content_tag = soup.select_one("div[data-testid='content']")
                
                if content_tag:
                    review_text = content_tag.get_text("\n", strip=True)

            # Fallback 2: Old layout 'layout-body'
            if not review_text:
                content_tag = soup.find(class_=lambda c: c and 'layout-body' in c.lower())
                if content_tag:
                     review_text = content_tag.get_text(strip=True)

            # Clean duplicate title
            if title and title in review_text:
                review_text = review_text.replace(title, "").strip()

            # Reviewer Name and Role
            reviewer_name = "Anonymous"
            reviewer_role = None
            
            # 1. Try to find the detailed Byline container (Name + Role)
            # Class usually looks like 'Byline_byline__Wr1dg'
            byline = soup.find(class_=lambda c: c and 'Byline_byline' in c)
            if byline:
                # Expecting children: [Name, Role, Company]
                # Filter out pure verification badges if mixed
                children = list(byline.find_all("div", recursive=False))
                
                # Sometimes the first child is the name
                if children:
                    potential_name = children[0].get_text(strip=True)
                    if potential_name:
                         reviewer_name = potential_name
                    
                    if len(children) > 1:
                        reviewer_role = children[1].get_text(strip=True)

            # 2. Fallback: Look for "Verified User" in a simpler container if Byline failed or name is generic
            if reviewer_name == "Anonymous" or reviewer_name == "Verified User":
                 # Check if there is a more specific "Verified User" text that isn't the byline
                 # Actually, if we found Byline, we trust it even if it says "Verified User".
                 # If we didn't find Byline, look for generic verification
                 if not byline:
                     vu = soup.find(string=lambda t: "Verified User" in t if t else False)
                     if vu:
                         reviewer_name = "Verified User"

            # Clean name noise
            if reviewer_name:
                if "Verified User" in reviewer_name:
                    # Ensure it's clean (e.g. handle glued text)
                    if len(reviewer_name) > 20 and "Verified User" in reviewer_name[:15]:
                         reviewer_name = "Verified User"
                
                # Handle abbreviations
                if reviewer_name == "VU":
                    reviewer_name = "Verified User"

            if "Vetted Review" in reviewer_name:
                reviewer_name = reviewer_name.replace("Vetted Review", "").strip()

            return Review(
                source="trustradius",
                company=company,
                title=title,
                review=review_text.strip(),
                date=date,
                rating=rating,
                reviewer_name=reviewer_name,
                reviewer_role=None,
                additional_metadata={}
            )
        except Exception as e:
            Logger.warning(f"Error parsing review: {e}")
            return None
