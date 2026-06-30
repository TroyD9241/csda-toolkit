"""Parse HLTV HTML pages into domain Event / EventSeries objects."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from csda_toolkit.domain.models import Event, EventSeries
from csda_toolkit.enrichment.client import HLTVClient


class EventParser:
    """Parses HLTV HTML into domain objects."""

    def parse_event_listings(self, html: str) -> list[Event]:
        """Extract event listings from HLTV events page HTML.

        HLTV embeds event data as JSON in a <script> tag.
        Fall back to HTML table parsing if JSON not found.
        """
        # Try JSON embedded in script tag
        script_match = re.search(
            r'<script[^>]*id=["\']events-data["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if script_match:
            try:
                data = json.loads(script_match.group(1))
                if isinstance(data, list):
                    return [self._json_to_event(e) for e in data if isinstance(e, dict)]
                elif isinstance(data, dict) and "events" in data:
                    return [self._json_to_event(e) for e in data["events"] if isinstance(e, dict)]
            except (json.JSONDecodeError, KeyError):
                pass

        # HTML fallback: parse .events-master-table rows
        soup = BeautifulSoup(html, "html.parser")
        events = []
        for row in soup.select("tr[data-event-id]"):
            events.append(self._html_row_to_event(row))
        return [e for e in events if e.name]

    def parse_series_for_event(self, hltv_event_id: int, html: str) -> list[EventSeries]:
        """Extract match/series listings from an HLTV event page HTML."""
        script_match = re.search(
            r'<script[^>]*id=["\']events-data["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if script_match:
            try:
                data = json.loads(script_match.group(1))
                if isinstance(data, list):
                    return [self._json_to_series(s, hltv_event_id) for s in data if isinstance(s, dict)]
                elif isinstance(data, dict) and "matches" in data:
                    return [self._json_to_series(s, hltv_event_id) for s in data["matches"] if isinstance(s, dict)]
            except (json.JSONDecodeError, KeyError):
                pass

        # HTML fallback
        soup = BeautifulSoup(html, "html.parser")
        series = []
        for row in soup.select(".match-table tr[data-match-id]"):
            series.append(self._html_row_to_series(row, hltv_event_id))
        return [s for s in series if s.team_a_name or s.team_b_name]

    # ── JSON helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _ts_to_dt(ts: Optional[int]) -> Optional[datetime]:
        """Convert Unix millisecond timestamp to datetime."""
        if not ts:
            return None
        try:
            return datetime.fromtimestamp(ts / 1000)
        except (ValueError, OSError):
            return None

    def _json_to_event(self, d: dict) -> Event:
        return Event(
            name=d.get("name", ""),
            slug=d.get("slug", ""),
            tier=self._json_tier_to_int(d.get("tier")),
            region=d.get("country", "") or d.get("location", ""),
            source="hltv",
            start_date=self._ts_to_dt(d.get("startDate")) or self._ts_to_dt(d.get("start_date")),
            end_date=self._ts_to_dt(d.get("endDate")) or self._ts_to_dt(d.get("end_date")),
        )

    @staticmethod
    def _json_tier_to_int(tier_val) -> int:
        if isinstance(tier_val, int):
            return tier_val if tier_val in (1, 2, 3) else 0
        if isinstance(tier_val, str):
            t = tier_val.lower()
            if "s" in t or "tier1" in t or "1" in t:
                return 1
            if "tier2" in t or "2" in t:
                return 2
            if "tier3" in t or "3" in t:
                return 3
        return 0

    def _json_to_series(self, d: dict, event_id: int) -> EventSeries:
        team_a = d.get("team1", {}) if isinstance(d.get("team1"), dict) else {}
        team_b = d.get("team2", {}) if isinstance(d.get("team2"), dict) else {}
        result = d.get("result", {}) if isinstance(d.get("result"), dict) else {}
        return EventSeries(
            event_id=event_id,
            series_type=d.get("matchType", "").lower().replace("bo", "").strip(),
            round_name=d.get("round", "").lower().strip(),
            team_a_name=team_a.get("name", ""),
            team_b_name=team_b.get("name", ""),
            team_a_score=int(result.get("score1", 0) or 0),
            team_b_score=int(result.get("score2", 0) or 0),
            map_veto_json=json.dumps(d.get("veto", [])),
            source="hltv",
        )

    # ── HTML helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _html_row_to_event(row) -> Event:
        name_el = row.select_one(".event-name-cell a") or row.select_one(".event-name")
        tier_el = row.select_one(".event-tier-cell")
        loc_el = row.select_one(".event-location-cell")
        slug_el = row.select_one(".event-name-cell a[href]")
        href = slug_el.get("href", "") if slug_el else ""
        slug = href.strip("/").split("/")[-1] if href else ""

        return Event(
            name=name_el.get_text(strip=True) if name_el else "",
            slug=slug,
            tier=EventParser._html_tier_to_int(tier_el.get_text(strip=True) if tier_el else ""),
            region=loc_el.get_text(strip=True) if loc_el else "",
            source="hltv",
        )

    @staticmethod
    def _html_row_to_series(row, event_id: int) -> EventSeries:
        team_a_el = row.select_one(".team-name-cell:first-child")
        team_b_el = row.select_one(".team-name-cell:last-child")
        score_el = row.select_one(".match-score-cell")
        format_el = row.select_one(".match-format-cell")
        round_el = row.select_one(".match-round-cell")

        score_text = score_el.get_text(strip=True) if score_el else ""
        scores = [int(x) for x in re.findall(r"\d+", score_text)]
        team_a_score = scores[0] if len(scores) > 0 else 0
        team_b_score = scores[1] if len(scores) > 1 else 0

        format_text = format_el.get_text(strip=True).lower() if format_el else ""
        series_type = re.sub(r"bo(\d)", r"\1", format_text).strip()

        return EventSeries(
            event_id=event_id,
            series_type=series_type,
            round_name=round_el.get_text(strip=True).lower() if round_el else "",
            team_a_name=team_a_el.get_text(strip=True) if team_a_el else "",
            team_b_name=team_b_el.get_text(strip=True) if team_b_el else "",
            team_a_score=team_a_score,
            team_b_score=team_b_score,
            source="hltv",
        )

    @staticmethod
    def _html_tier_to_int(tier_text: str) -> int:
        t = tier_text.lower()
        if any(x in t for x in ("s-tier", "s tier", "tier 1", "tier1")) or ("1" in t and "tier" in t):
            return 1
        if any(x in t for x in ("a-tier", "a tier", "tier 2", "tier2")) or ("2" in t and "tier" in t):
            return 2
        if any(x in t for x in ("b-tier", "b tier", "tier 3", "tier3")) or ("3" in t and "tier" in t):
            return 3
        return 0


def fetch_event_listings() -> list[Event]:
    """Fetch and parse current event listings from HLTV."""
    client = HLTVClient()
    try:
        html = client.get_event_listings_page()
        return EventParser().parse_event_listings(html)
    finally:
        client.close()


def fetch_series_for_event(hltv_event_id: int) -> list[EventSeries]:
    """Fetch and parse series for a specific HLTV event."""
    client = HLTVClient()
    try:
        html = client.get_event_page(hltv_event_id)
        return EventParser().parse_series_for_event(hltv_event_id, html)
    finally:
        client.close()
