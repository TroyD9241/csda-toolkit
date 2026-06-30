"""Tests for HLTV enrichment adapter."""

from __future__ import annotations

import json
import os
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from csda_toolkit.enrichment import (
    HLTVClient,
    EventParser,
    fetch_event_listings,
    fetch_series_for_event,
)
from csda_toolkit.domain.models import Event, EventSeries


# ── Fixture helpers ─────────────────────────────────────────────────────────

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name: str) -> str:
    path = os.path.join(FIXTURE_DIR, name)
    with open(path) as f:
        return f.read()


# ── JSON test data ──────────────────────────────────────────────────────────

MOCK_EVENTS_JSON = json.dumps([
    {
        "id": 1234,
        "name": "BLAST Rivals 2026",
        "slug": "blast-rivals-2026",
        "tier": 1,
        "country": "Brazil",
        "startDate": 1747267200000,
        "endDate": 1748044800000,
    },
    {
        "id": 5678,
        "name": "ESL Pro League Season 22",
        "slug": "esl-pro-league-s22",
        "tier": 2,
        "country": "Europe",
        "startDate": 1751241600000,
        "endDate": 1753056000000,
    },
])

MOCK_EVENT_PAGE_JSON = json.dumps([
    {
        "matchId": 9991,
        "team1": {"name": "Vitality", "id": 9565},
        "team2": {"name": "NaVi", "id": 4964},
        "result": {"score1": 2, "score2": 0},
        "matchType": "bo3",
        "round": "quarterfinal",
    },
    {
        "matchId": 9992,
        "team1": {"name": "Vitality", "id": 9565},
        "team2": {"name": "G2", "id": 4871},
        "result": {"score1": 2, "score2": 1},
        "matchType": "bo3",
        "round": "semifinal",
    },
])


# ── EventParser tests ────────────────────────────────────────────────────────

class TestEventParser:
    def _make_html(self, script_content: str) -> str:
        return (
            '<html><head>'
            f'<script id="events-data">{script_content}</script>'
            "</head></html>"
        )

    # ── JSON parsing ──────────────────────────────────────────────────────────

    def test_parse_events_json(self):
        html = self._make_html(MOCK_EVENTS_JSON)
        events = EventParser().parse_event_listings(html)
        assert len(events) == 2
        assert events[0].name == "BLAST Rivals 2026"
        assert events[0].slug == "blast-rivals-2026"
        assert events[0].tier == 1
        assert events[0].region == "Brazil"
        assert events[0].source == "hltv"

    def test_parse_events_tier_2(self):
        html = self._make_html(MOCK_EVENTS_JSON)
        events = EventParser().parse_event_listings(html)
        assert events[1].tier == 2
        assert events[1].region == "Europe"

    def test_parse_events_start_date_parsed(self):
        html = self._make_html(MOCK_EVENTS_JSON)
        events = EventParser().parse_event_listings(html)
        assert events[0].start_date is not None
        # Timestamp 1747267200000 ms = 2025-05-14 19:00 UTC
        assert events[0].start_date.year == 2025
        assert events[0].start_date.month == 5
        assert events[0].start_date.day == 14

    def test_parse_events_end_date_parsed(self):
        html = self._make_html(MOCK_EVENTS_JSON)
        events = EventParser().parse_event_listings(html)
        assert events[0].end_date is not None
        assert events[0].end_date.year == 2025
        assert events[0].end_date.month == 5

    def test_parse_series_json(self):
        html = self._make_html(MOCK_EVENT_PAGE_JSON)
        series = EventParser().parse_series_for_event(1234, html)
        assert len(series) == 2

        assert series[0].event_id == 1234
        assert series[0].team_a_name == "Vitality"
        assert series[0].team_b_name == "NaVi"
        assert series[0].team_a_score == 2
        assert series[0].team_b_score == 0
        assert series[0].series_type == "3"  # bo3 → "3"
        assert series[0].round_name == "quarterfinal"

    def test_parse_series_round_semifinal(self):
        html = self._make_html(MOCK_EVENT_PAGE_JSON)
        series = EventParser().parse_series_for_event(999, html)
        assert series[1].round_name == "semifinal"
        assert series[1].team_a_score == 2
        assert series[1].team_b_score == 1

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_empty_html_returns_empty_list(self):
        events = EventParser().parse_event_listings("<html><body></body></html>")
        assert events == []
        series = EventParser().parse_series_for_event(999, "<html><body></body></html>")
        assert series == []

    def test_malformed_json_falls_back_to_empty(self):
        html = '<html><body><script id="events-data">NOT VALID JSON</script></body></html>'
        events = EventParser().parse_event_listings(html)
        assert events == []

    def test_nested_json_events_key(self):
        nested = json.dumps({"events": json.loads(MOCK_EVENTS_JSON)})
        html = self._make_html(nested)
        events = EventParser().parse_event_listings(html)
        assert len(events) == 2

    def test_nested_json_matches_key(self):
        nested = json.dumps({"matches": json.loads(MOCK_EVENT_PAGE_JSON)})
        html = self._make_html(nested)
        series = EventParser().parse_series_for_event(99, html)
        assert len(series) == 2

    # ── Timestamp helper ──────────────────────────────────────────────────────

    def test_ts_to_dt_converts_milliseconds(self):
        ts = 1747267200000  # 2025-05-14 19:00:00 UTC
        dt = EventParser._ts_to_dt(ts)
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 5
        assert dt.day == 14

    def test_ts_to_dt_returns_none_for_zero(self):
        assert EventParser._ts_to_dt(0) is None
        assert EventParser._ts_to_dt(None) is None

    # ── Tier parsing ────────────────────────────────────────────────────────────

    def test_json_tier_to_int_s_tier(self):
        assert EventParser._json_tier_to_int("S-tier") == 1
        assert EventParser._json_tier_to_int("s") == 1
        assert EventParser._json_tier_to_int(1) == 1

    def test_json_tier_to_int_a_tier(self):
        assert EventParser._json_tier_to_int("tier2") == 2
        assert EventParser._json_tier_to_int("2") == 2
        assert EventParser._json_tier_to_int(2) == 2

    def test_json_tier_to_int_b_tier(self):
        assert EventParser._json_tier_to_int("tier3") == 3
        assert EventParser._json_tier_to_int("3") == 3
        assert EventParser._json_tier_to_int(3) == 3

    def test_json_tier_to_int_unknown(self):
        assert EventParser._json_tier_to_int("unknown") == 0
        assert EventParser._json_tier_to_int(99) == 0


# ── HLTVClient tests ─────────────────────────────────────────────────────────

class TestHLTVClient:
    def test_base_url(self):
        client = HLTVClient()
        assert client.BASE_URL == "https://www.hltv.org"
        client.close()

    @patch("httpx.Client.get")
    @patch("time.sleep")
    def test_get_event_listings_page(self, mock_sleep, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "<html>events page</html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = HLTVClient()
        html = client.get_event_listings_page()
        client.close()

        assert html == "<html>events page</html>"
        mock_get.assert_called_once()
        assert "events" in mock_get.call_args[0][0]

    @patch("httpx.Client.get")
    @patch("time.sleep")
    def test_get_event_page(self, mock_sleep, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "<html>event 1234 page</html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = HLTVClient()
        html = client.get_event_page(1234)
        client.close()

        assert "1234" in html
        mock_get.assert_called_once()


# ── fetch_* integration tests (mocked HTTP) ──────────────────────────────────

class TestFetchFunctions:
    @patch("csda_toolkit.enrichment.hltv_adapter.HLTVClient")
    def test_fetch_event_listings(self, MockClient):
        instance = MockClient.return_value
        instance.get_event_listings_page.return_value = (
            f'<html><script id="events-data">{MOCK_EVENTS_JSON}</script></html>'
        )

        events = fetch_event_listings()
        assert len(events) == 2
        assert all(e.source == "hltv" for e in events)
        assert events[0].name == "BLAST Rivals 2026"

    @patch("csda_toolkit.enrichment.hltv_adapter.HLTVClient")
    def test_fetch_series_for_event(self, MockClient):
        instance = MockClient.return_value
        instance.get_event_page.return_value = (
            f'<html><script id="events-data">{MOCK_EVENT_PAGE_JSON}</script></html>'
        )

        series = fetch_series_for_event(1234)
        assert len(series) == 2
        assert all(s.source == "hltv" for s in series)
        assert series[0].team_a_name == "Vitality"


# ── Fixture file tests ─────────────────────────────────────────────────────────

class TestFixtures:
    def test_events_listing_fixture_loads(self):
        html = _load_fixture("events_listing.html")
        events = EventParser().parse_event_listings(html)
        assert len(events) == 2
        assert events[0].name == "BLAST Rivals 2026"
        assert events[0].tier == 1

    def test_event_page_fixture_loads(self):
        html = _load_fixture("event_page.html")
        series = EventParser().parse_series_for_event(1234, html)
        assert len(series) == 2
        assert series[0].team_a_name == "Vitality"
        assert series[0].team_b_name == "NaVi"
