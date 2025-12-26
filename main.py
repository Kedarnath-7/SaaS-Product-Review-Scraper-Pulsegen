import argparse
import json
import os
from datetime import datetime
from scrapers.g2 import G2Scraper
from scrapers.capterra import CapterraScraper
from scrapers.trustradius import TrustRadiusScraper
from utils.logger import Logger

def main():
    parser = argparse.ArgumentParser(description="SaaS Product Review Scraper")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--source", required=True, choices=["g2", "capterra", "trustradius", "all"], help="Source to scrape")
    parser.add_argument("--headful", action="store_true", help="Run browser in headful mode (useful for debugging)")
    parser.add_argument("--output", required=True, help="Output JSON file path")

    args = parser.parse_args()

    # Validate dates
    try:
        datetime.strptime(args.start_date, "%Y-%m-%d")
        datetime.strptime(args.end_date, "%Y-%m-%d")
    except ValueError:
        Logger.error("Dates must be in YYYY-MM-DD format")
        return

    headless_mode = not args.headful
    
    scrapers = []
    if args.source == "g2":
        scrapers.append(G2Scraper(headless=headless_mode))
    elif args.source == "capterra":
        scrapers.append(CapterraScraper(headless=headless_mode))
    elif args.source == "trustradius":
        scrapers.append(TrustRadiusScraper(headless=headless_mode))
    elif args.source == "all":
        scrapers.append(G2Scraper(headless=headless_mode))
        scrapers.append(CapterraScraper(headless=headless_mode))
        scrapers.append(TrustRadiusScraper(headless=headless_mode))

    all_reviews = []
    for scraper in scrapers:
        try:
            reviews = scraper.fetch_reviews(args.company, args.start_date, args.end_date)
            all_reviews.extend(reviews)
        except Exception as e:
            Logger.error(f"Scraper failed: {e}")

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Save to JSON
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in all_reviews], f, indent=2, ensure_ascii=False)
    
    Logger.info(f"Saved {len(all_reviews)} reviews to {args.output}")

if __name__ == "__main__":
    main()
