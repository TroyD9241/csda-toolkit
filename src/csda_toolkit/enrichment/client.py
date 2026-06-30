"""HTTP client for HLTV website scraping."""

from __future__ import annotations

import time
import httpx


class HLTVClient:
    """Sync HTTP client for HLTV pages."""

    BASE_URL = "https://www.hltv.org"

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=30.0)

    def get_event_listings_page(self) -> str:
        """Fetch https://www.hltv.org/events"""
        time.sleep(1.1)  # polite rate limit
        resp = self._client.get(
            f"{self.BASE_URL}/events",
            headers={"User-Agent": "Mozilla/5.0 (compatible; csda-toolkit/1.0)"},
        )
        resp.raise_for_status()
        return resp.text

    def get_event_page(self, hltv_event_id: int) -> str:
        """Fetch https://www.hltv.org/events/{hltv_event_id}"""
        time.sleep(1.1)
        resp = self._client.get(
            f"{self.BASE_URL}/events/{hltv_event_id}",
            headers={"User-Agent": "Mozilla/5.0 (compatible; csda-toolkit/1.0)"},
        )
        resp.raise_for_status()
        return resp.text

    def close(self) -> None:
        self._client.close()
