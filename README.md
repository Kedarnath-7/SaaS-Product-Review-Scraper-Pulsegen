# SaaS Product Review Scraper

A Python-based scraping system to collect product reviews from **G2**, **Capterra**, and **TrustRadius**.
The system outputs structured JSON data containing reviews filtered by a specified date range.

## Features
- **Multi-Source**: Scrapes G2, Capterra, and TrustRadius (Bonus).
- **Date Filtering**: Strictly includes reviews within the provided start and end dates.
- **Structured Output**: Returns a unified JSON schema across all sources.
- **Anti-Bot Evasion**: Uses Playwright with stealth techniques (User-Agent, Viewport, Chrome Args) to attempt Cloudflare bypass.

## Prerequisites
- Python 3.10+
- Playwright Browsers

## Installation

1. Clone the repository.
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install Playwright browsers:
   ```bash
   python -m playwright install chromium
   ```

## Usage

Run the `main.py` script with the required arguments:

```bash
python main.py --company "notion" --start-date 2024-01-01 --end-date 2025-03-31 --source all --output output/reviews.json
```

### Arguments
- `--company`: Name of the company/product to scrape (e.g., "notion", "slack").
- `--start-date`: Start date for reviews (format: YYYY-MM-DD).
- `--end-date`: End date for reviews (format: YYYY-MM-DD).
- `--source`: Source to scrape. Options: `g2`, `capterra`, `trustradius`, `all`.
- `--output`: Path to the output JSON file.

### Example Output
```json
[
  {
    "source": "trustradius",
    "company": "Notion",
    "title": "Notion is the best tool for documentation",
    "review": "I have been using Notion for 2 years...",
    "date": "2024-02-15",
    "rating": 9.0,
    "reviewer_name": "Jane Doe",
    "reviewer_role": "Product Manager",
    "additional_metadata": {}
  }
]
```

## Anti-Scraping & Limitations

**Important**: G2 and Capterra employ aggressive anti-bot protection (Cloudflare, heavily obfuscated DOM, Captchas).
- This scraper uses `playwright` with `headless=True` and evasion arguments.
- **Success is not guaranteed** for G2 and Capterra in a purely automated, headless environment without residential proxies or captcha solving services.
- If you encounter 403/429 errors or empty results, it is likely a Cloudflare block.
- **TrustRadius** is generally more lenient and is provided as a robust bonus source.

## Future Improvements
- Integrate 3rd-party Captcha solving APIs (e.g., 2Captcha).
- Support for rotating residential proxies.
