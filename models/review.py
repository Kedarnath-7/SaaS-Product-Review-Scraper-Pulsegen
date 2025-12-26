from dataclasses import dataclass
from typing import Optional, Any, Dict

@dataclass
class Review:
    source: str
    company: str
    title: str
    review: str
    date: str  # YYYY-MM-DD
    rating: float
    reviewer_name: Optional[str] = None
    reviewer_role: Optional[str] = None
    additional_metadata: Optional[Dict[str, Any]] = None

    def to_dict(self):
        return {
            "source": self.source,
            "company": self.company,
            "title": self.title,
            "review": self.review,
            "date": self.date,
            "rating": self.rating,
            "reviewer_name": self.reviewer_name,
            "reviewer_role": self.reviewer_role,
            "additional_metadata": self.additional_metadata or {}
        }
