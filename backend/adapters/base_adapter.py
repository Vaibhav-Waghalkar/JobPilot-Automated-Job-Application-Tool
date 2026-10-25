from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class DiscoveredJob:
    platform: str
    external_id: str
    company: str
    title: str
    location: str
    salary_raw: Optional[str] = None
    apply_url: str = ""
    description: str = ""
    posted_date: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class BaseJobAdapter:
    """Base interface for all platform job scrapers and adapters."""
    def __init__(self, platform_name: str):
        self.platform_name = platform_name

    async def search_jobs(self, keywords: List[str], locations: List[str], limit: int = 20) -> List[DiscoveredJob]:
        raise NotImplementedError
