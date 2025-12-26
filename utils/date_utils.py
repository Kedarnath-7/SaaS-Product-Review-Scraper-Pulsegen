from datetime import datetime
from typing import Optional

def parse_date(date_str: str) -> Optional[str]:
    """
    Parses a date string into YYYY-MM-DD format.
    Handles various formats like "October 24, 2023", "2023-10-24", etc.
    Returns None if parsing fails.
    """
    try:
        # Try ISO format first
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        pass

    try:
        # Try "Month DD, YYYY" (e.g., "October 24, 2023")
        return datetime.strptime(date_str, "%B %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
        
    try:
        # Try "Mon DD, YYYY" (e.g., "Oct 24, 2023")
        return datetime.strptime(date_str, "%b %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        pass

    return None

def is_date_in_range(date_str: str, start_date: str, end_date: str) -> bool:
    """
    Checks if date_str is within [start_date, end_date] inclusive.
    All dates must be in YYYY-MM-DD format.
    """
    if not date_str or not start_date or not end_date:
        return False
    return start_date <= date_str <= end_date
