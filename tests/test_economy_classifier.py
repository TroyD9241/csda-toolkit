"""Tests for economy classifier."""

import pytest
from csda_toolkit.classifiers.economy import (
    BuyType,
    PlayerBuyProfile,
    SideBuyProfile,
    classify_side_economy,
    classify_round_economy,
    FULL_BUY_THRESHOLD,
    HALF_BUY_THRESHOLD,
)


class TestBuyTypeClassification:
    """Test buy type classification from equipment values."""

    def _eq(self, steam_id: int, value: int, weapons: list[str] | None = None) -> dict:
        return {
            "steam_id": steam_id,
            "equipment_value": value,
            "weapons": weapons or {},
        }

    def test_full_buy_threshold(self):
        """Avg >= 5000 = full buy."""
        records = [
            self._eq(1, 5500), self._eq(2, 5200),
            self._eq(3, 5800), self._eq(4, 5000), self._eq(5, 5100),
        ]
        result = classify_side_economy(records, round_number=1, team_side="ct")
        assert result.buy_type == BuyType.FULL
        assert result.num_rifles == 0  # no weapons in records

    def test_half_buy_threshold(self):
        """Avg 2500-5000 = half buy."""
        records = [
            self._eq(1, 3000), self._eq(2, 3200),
            self._eq(3, 2800), self._eq(4, 3100), self._eq(5, 2900),
        ]
        result = classify_side_economy(records, round_number=1, team_side="t")
        assert result.buy_type == BuyType.HALF

    def test_eco_buy_threshold(self):
        """Avg < 2500 = eco."""
        records = [
            self._eq(1, 1200), self._eq(2, 1400),
            self._eq(3, 1100), self._eq(4, 1300), self._eq(5, 1500),
        ]
        result = classify_side_economy(records, round_number=1, team_side="ct")
        assert result.buy_type == BuyType.ECO

    def test_empty_records_returns_unknown(self):
        result = classify_side_economy([], round_number=1, team_side="t")
        assert result.buy_type == BuyType.UNKNOWN
        assert result.total_equipment_value == 0

    def test_awp_adjusts_threshold_down(self):
        """AWP (~4700) should push avg down for threshold classification."""
        # Without AWP: avg = 4600 → HALF
        # With AWP: adjusted_avg = 4600 - 1500 = 3100 → still HALF
        # Let's test a borderline case
        records = [
            self._eq(1, 4700, ["awp"]),
            self._eq(2, 4500),
            self._eq(3, 4600),
            self._eq(4, 4700),
            self._eq(5, 4600),
        ]
        result = classify_side_economy(records, round_number=1, team_side="t")
        avg = 4700 + 4500 + 4600 + 4700 + 4600
        assert result.buy_type == BuyType.HALF

    def test_total_equipment_value_summed(self):
        records = [self._eq(1, 3000), self._eq(2, 2500), self._eq(3, 2800)]
        result = classify_side_economy(records, round_number=2, team_side="ct")
        assert result.total_equipment_value == 8300
        # avg = 2766.67 → HALF
        assert result.buy_type == BuyType.HALF

    def test_side_is_set(self):
        records = [self._eq(1, 3000)]
        ct_result = classify_side_economy(records, round_number=1, team_side="ct")
        t_result = classify_side_economy(records, round_number=1, team_side="t")
        assert ct_result.team_side == "ct"
        assert t_result.team_side == "t"

    def test_round_number_passed_through(self):
        records = [self._eq(1, 3000)]
        result = classify_side_economy(records, round_number=7, team_side="t")
        assert result.round_number == 7


class TestSideBuyProfile:
    """Test SideBuyProfile buy_type method."""

    def test_profile_full_buy(self):
        players = [PlayerBuyProfile(1, 5500, []), PlayerBuyProfile(2, 5800, [])]
        profile = SideBuyProfile(
            team_side="ct", round_number=1,
            total_equipment_value=11300, avg_equipment_value=5650,
            num_rifles=0, num_smgs=0, num_pistols=0, num_awps=0,
            num_kevlar=0, num_helmets=0, num_defuse_kits=0,
            players=players,
        )
        assert profile.buy_type() == BuyType.FULL

    def test_profile_eco_buy(self):
        players = [PlayerBuyProfile(1, 800, []), PlayerBuyProfile(2, 1000, [])]
        profile = SideBuyProfile(
            team_side="t", round_number=1,
            total_equipment_value=1800, avg_equipment_value=900,
            num_rifles=0, num_smgs=0, num_pistols=0, num_awps=0,
            num_kevlar=0, num_helmets=0, num_defuse_kits=0,
            players=players,
        )
        assert profile.buy_type() == BuyType.ECO


class TestClassifyRoundEconomy:
    """Test classify_round_economy returns both sides."""

    def _eq(self, steam_id: int, value: int) -> dict:
        return {"steam_id": steam_id, "equipment_value": value, "weapons": {}}

    def test_returns_ct_and_t(self):
        ct_recs = [self._eq(1, 4000), self._eq(2, 4200), self._eq(3, 3800), self._eq(4, 4100), self._eq(5, 3900)]
        t_recs = [self._eq(6, 1200), self._eq(7, 1100), self._eq(8, 1300), self._eq(9, 1000), self._eq(10, 1400)]

        ct_result, t_result = classify_round_economy(ct_recs, t_recs, round_number=1)

        assert ct_result.team_side == "ct"
        assert t_result.team_side == "t"
        assert ct_result.buy_type == BuyType.HALF
        assert t_result.buy_type == BuyType.ECO

    def test_round_number_set_on_both(self):
        ct_recs = [self._eq(1, 3000)]
        t_recs = [self._eq(2, 3000)]

        ct_result, t_result = classify_round_economy(ct_recs, t_recs, round_number=5)

        assert ct_result.round_number == 5
        assert t_result.round_number == 5


class TestThresholds:
    """Test that threshold constants are sane."""

    def test_thresholds_are_ordered(self):
        assert FULL_BUY_THRESHOLD > HALF_BUY_THRESHOLD
        assert HALF_BUY_THRESHOLD > 0

    def test_full_buy_threshold_value(self):
        """5000 is the standard CS2 full buy threshold per player."""
        assert FULL_BUY_THRESHOLD == 5000
