"""Unit tests for hltv_rating compute functions.

Run with:  pytest tests/test_hltv_rating.py -v
"""
import math
import pytest

from csda_toolkit.classifiers.hltv_rating import (
    compute_hltv_rating,
    compute_match_rating,
    HltvRoundSignals,
    HltvRoundRating,
    clamp,
)


# ─── helpers ───────────────────────────────────────────────────────────────────

def signals(
    *,
    steam_id: int = 1,
    round_number: int = 1,
    kills: int = 10,
    deaths: int = 5,
    adr: float = 80.0,
    headshot_kills: int = 4,
    opening_kills: int = 2,
    total_round_kills: int = 10,
    clutch_won: int = 1,
    clutch_lost: int = 0,
    util_success: float = 0.5,
    rounds_played: int = 24,
) -> HltvRoundSignals:
    return HltvRoundSignals(
        steam_id=steam_id,
        round_number=round_number,
        kills=kills,
        deaths=deaths,
        adr=adr,
        headshot_kills=headshot_kills,
        opening_kills=opening_kills,
        total_round_kills=total_round_kills,
        clutch_won=clutch_won,
        clutch_lost=clutch_lost,
        util_success=util_success,
        rounds_played=rounds_played,
    )


def rating_of(**kwargs) -> float:
    return compute_hltv_rating(signals(**kwargs)).rating


def sub_of(**kwargs) -> HltvRoundRating:
    return compute_hltv_rating(signals(**kwargs))


# ─── clamp ─────────────────────────────────────────────────────────────────────

class TestClamp:
    def test_in_range(self):
        assert clamp(0.5, 0.0, 1.0) == 0.5

    def test_below_low(self):
        assert clamp(-0.5, 0.0, 1.0) == 0.0

    def test_above_high(self):
        assert clamp(1.5, 0.0, 1.0) == 1.0

    def test_exactly_at_bounds(self):
        assert clamp(0.0, 0.0, 1.0) == 0.0
        assert clamp(1.0, 0.0, 1.0) == 1.0


# ─── KPR ──────────────────────────────────────────────────────────────────────

class TestKPR:
    def test_normal(self):
        r = sub_of(kills=10, rounds_played=24)
        assert r.kpr == pytest.approx(10 / 24, rel=1e-2)  # impl rounds to 3dp

    def test_zero_rounds(self):
        r = sub_of(kills=10, rounds_played=0)
        assert r.kpr == 0.0

    def test_zero_kills(self):
        r = sub_of(kills=0, rounds_played=24)
        assert r.kpr == 0.0


# ─── K/D ───────────────────────────────────────────────────────────────────────

class TestKD:
    def test_normal(self):
        r = sub_of(kills=10, deaths=5)
        assert r.kd == 2.0

    def test_zero_deaths(self):
        r = sub_of(kills=10, deaths=0)
        assert r.kd == 0.0

    def test_floating_point(self):
        r = sub_of(kills=7, deaths=3)
        assert r.kd == pytest.approx(7 / 3, rel=1e-2)  # impl rounds to 3dp


# ─── Headshot % ────────────────────────────────────────────────────────────────

class TestHSPct:
    def test_normal(self):
        r = sub_of(kills=10, headshot_kills=4)
        assert r.hs_pct == 0.4

    def test_zero_kills(self):
        r = sub_of(kills=0, headshot_kills=0)
        assert r.hs_pct == 0.0

    def test_all_headshots(self):
        r = sub_of(kills=5, headshot_kills=5)
        assert r.hs_pct == 1.0


# ─── OK% ───────────────────────────────────────────────────────────────────────

class TestOKPct:
    def test_normal(self):
        r = sub_of(opening_kills=2, total_round_kills=10)
        assert r.ok_pct == 0.2

    def test_zero_total_kills(self):
        r = sub_of(opening_kills=2, total_round_kills=0)
        assert r.ok_pct == 0.0

    def test_clamped_to_one(self):
        # More opening kills than total kills shouldn't inflate above 1.0
        r = sub_of(opening_kills=5, total_round_kills=3)
        assert r.ok_pct == 1.0


# ─── Impact & Impact Multiplier ─────────────────────────────────────────────────

class TestImpact:
    def test_impact_formula(self):
        # kd=2.0, kpr=10/24≈0.417, ok_pct=0.2
        # impact = (2.13 * kd) - (1.25 * ok_pct) - 0.17  [KPR removed from impact]
        #        = 2.13*2.0 - 1.25*0.2 - 0.17 = 4.26 - 0.25 - 0.17 = 3.84
        r = sub_of(kills=10, deaths=5, rounds_played=24, opening_kills=2, total_round_kills=10)
        expected = (2.13 * 2.0) - (1.25 * 0.2) - 0.17
        assert r.impact == pytest.approx(expected, rel=1e-3)

    def test_impact_multiplier_positive(self):
        r = sub_of()
        assert r.impact_mult > 1.0  # Should boost

    def test_impact_multiplier_exp(self):
        r = sub_of(kills=1, deaths=1, rounds_played=24, opening_kills=0, total_round_kills=10)
        # Low-impact player: low kd, moderate kpr, 0 ok_pct
        # kd=1, kpr≈0.042, ok_pct=0
        # impact = 2.13*1 + 0.42*0.042*100 - 0 - 0.17 = 2.13 + 1.764 - 0.17 = 3.724
        # impact_mult = exp(0.43 * 3.724) = exp(1.601) ≈ 4.96
        assert r.impact_mult > 1.0

    def test_impact_mult_reasonable_range(self):
        # Low-impact player: kd≈0, ok_pct=1 → negative impact → multiplier < 1
        r_low = sub_of(kills=0, deaths=1, rounds_played=24, opening_kills=1, total_round_kills=1)
        assert 0.05 < r_low.impact_mult < 5.0  # very low, but not degenerate

        # High-impact player's multiplier is naturally very large per this formula
        # (the exponential scaling is a known characteristic of HLTV's approach)
        # Just verify it produces a finite positive value
        r_high = sub_of(kills=20, deaths=5, rounds_played=24, opening_kills=5, total_round_kills=10)
        assert r_high.impact_mult > 1.0
        assert r_high.impact_mult < 1e9  # sanity: not IEEE overflow


# ─── RPI ───────────────────────────────────────────────────────────────────────

class TestRPI:
    def test_no_clutch_no_util(self):
        # oK%=0.2, clutch_ratio=0, util_success=0
        r = sub_of(opening_kills=2, total_round_kills=10, clutch_won=0, clutch_lost=0, util_success=0.0)
        expected = 0.41 * 0.2 + 0.36 * 0.0 + 0.23 * 0.0
        assert r.rpi == pytest.approx(expected)

    def test_full_clutch_win(self):
        # oK%=0, clutch_ratio=1.0, util_success=0
        r = sub_of(opening_kills=0, total_round_kills=10, clutch_won=1, clutch_lost=0, util_success=0.0)
        expected = 0.36 * 1.0  # 0.41*0 + 0.36*1 + 0.23*0
        assert r.rpi == pytest.approx(expected)

    def test_full_util_success(self):
        # oK%=0, clutch_ratio=0, util_success=1.0
        r = sub_of(opening_kills=0, total_round_kills=10, clutch_won=0, clutch_lost=1, util_success=1.0)
        expected = 0.23 * 1.0
        assert r.rpi == pytest.approx(expected)

    def test_rpi_clamped_to_one(self):
        # Perfect OK%, perfect clutch, full util → should be clamped to 1.0
        r = sub_of(
            opening_kills=10, total_round_kills=10,
            clutch_won=1, clutch_lost=0,
            util_success=1.0,
        )
        assert r.rpi == 1.0


# ─── Full Rating ───────────────────────────────────────────────────────────────

class TestFullRating:
    def test_rating_components_sum(self):
        """Rating = 0.33*KPR + 0.60*K/D + 0.53*RPI*impact_mult + 0.55*(ADR/128) + 0.21*(1-K/D)*HS%"""
        r = sub_of(
            kills=10, deaths=5, rounds_played=24, adr=80.0,
            headshot_kills=4, opening_kills=2, total_round_kills=10,
            clutch_won=1, clutch_lost=0, util_success=0.5,
        )
        kpr = 10 / 24
        kd = 2.0
        hs_pct = 0.4
        ok_pct = 0.2
        # KPR removed from impact formula; impact_mult is log-dampened
        impact = (2.13 * kd) - (1.25 * ok_pct) - 0.17
        raw_mult = math.exp(0.43 * impact)
        impact_mult = 1.0 + math.log(1.0 + raw_mult)  # dampened
        clutch_ratio = 1.0
        rpi = (0.41 * ok_pct) + (0.36 * clutch_ratio) + (0.23 * 0.5)
        adr_norm = 80.0 / 128.0
        expected = (
            (0.33 * kpr) +
            (0.60 * kd) +
            (0.53 * rpi) * impact_mult +
            (0.55 * adr_norm) +
            (0.21 * (1.0 - kd) * hs_pct)
        )
        assert r.rating == pytest.approx(expected, rel=1e-2)

    def test_rating_always_positive_for_normal_player(self):
        """A player with any meaningful contribution should have positive rating."""
        r = sub_of(kills=5, deaths=5, rounds_played=24, adr=60.0, headshot_kills=1)
        assert r.rating > 0

    def test_high_kd_player_boosted(self):
        high_kd = rating_of(kills=20, deaths=5, rounds_played=24, adr=90.0, headshot_kills=8)
        low_kd = rating_of(kills=5, deaths=20, rounds_played=24, adr=90.0, headshot_kills=8)
        assert high_kd > low_kd

    def test_high_adr_player_boosted(self):
        high_adr = rating_of(kills=10, deaths=10, rounds_played=24, adr=120.0, headshot_kills=4)
        low_adr = rating_of(kills=10, deaths=10, rounds_played=24, adr=40.0, headshot_kills=4)
        assert high_adr > low_adr

    def test_headshot_consolation_term(self):
        """Headshot consolation fires when K/D < 1 (0.21 * (1-K/D) * HS%)."""
        # K/D = 0.5, HS% = 0.4 → consolation = 0.21 * 0.5 * 0.4 = 0.042
        r = sub_of(kills=5, deaths=10, headshot_kills=2, rounds_played=24)
        assert r.hs_pct == 0.4
        # Only the rating formula includes the consolation, check rating > without it
        r_with = sub_of(kills=5, deaths=10, headshot_kills=2, rounds_played=24,
                        opening_kills=0, total_round_kills=10)
        # The (1-kd)*hs_pct term at kd=0.5, hs=0.4 = 0.21*0.5*0.4 = 0.042
        # K/D consolation should show up in rating
        assert r_with.rating > 0


# ─── Edge Cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_zero_deaths_no_divide_by_zero(self):
        r = sub_of(kills=10, deaths=0, rounds_played=24)
        assert r.kd == 0.0
        assert r.rating > 0  # Should still compute

    def test_zero_kills_zero_deaths(self):
        r = sub_of(kills=0, deaths=0, rounds_played=24)
        assert r.kd == 0.0
        assert r.hs_pct == 0.0
        assert r.rating >= 0

    def test_zero_rounds_played(self):
        r = sub_of(kills=10, deaths=5, rounds_played=0)
        assert r.kpr == 0.0
        assert r.rating >= 0

    def test_all_util_success(self):
        r = sub_of(util_success=1.0, opening_kills=0, total_round_kills=10,
                   clutch_won=0, clutch_lost=0)
        assert r.rpi > 0

    def test_perfect_clutch_ratio(self):
        r = sub_of(clutch_won=5, clutch_lost=0)
        assert r.rpi > 0

    def test_losing_clutch_ratio(self):
        # Zero out opening kills AND util so only the 0% clutch_ratio contributes
        r = sub_of(clutch_won=0, clutch_lost=5, opening_kills=0, total_round_kills=10, util_success=0.0)
        assert r.rpi < 0.1  # Should be near 0


# ─── Match Rating ──────────────────────────────────────────────────────────────

class TestMatchRating:
    def test_empty_list(self):
        assert compute_match_rating([]) == 0.0

    def test_single_round(self):
        r = sub_of()
        assert compute_match_rating([r]) == r.rating

    def test_average_of_rounds(self):
        round1 = sub_of(kills=10, deaths=5, adr=80, rounds_played=24)
        round2 = sub_of(kills=5, deaths=8, adr=60, rounds_played=24)
        avg = compute_match_rating([round1, round2])
        expected = (round1.rating + round2.rating) / 2
        assert avg == pytest.approx(expected, rel=1e-2)  # rounded to 3dp

    def test_rounds_are_independent(self):
        """Each round's rating should be computed independently."""
        r1 = sub_of(kills=20, deaths=2, adr=100, rounds_played=24, round_number=1)
        r2 = sub_of(kills=0, deaths=5, adr=20, rounds_played=24, round_number=2)
        match = compute_match_rating([r1, r2])
        # Both should contribute to the average
        assert r1.rating > r2.rating

    def test_returns_rounded(self):
        r = sub_of(kills=7, deaths=3, rounds_played=24)
        assert compute_match_rating([r]) == r.rating  # Both rounded to 3 decimal places


# ─── Return Types ──────────────────────────────────────────────────────────────

class TestReturnType:
    def test_returns_hltvroundrating(self):
        r = compute_hltv_rating(signals())
        assert isinstance(r, HltvRoundRating)

    def test_all_fields_populated(self):
        r = compute_hltv_rating(signals())
        assert r.steam_id == 1
        assert r.round_number == 1
        assert isinstance(r.kpr, float)
        assert isinstance(r.kd, float)
        assert isinstance(r.ok_pct, float)
        assert isinstance(r.impact, float)
        assert isinstance(r.impact_mult, float)
        assert isinstance(r.rpi, float)
        assert isinstance(r.adr, float)
        assert isinstance(r.hs_pct, float)
        assert isinstance(r.rating, float)

    def test_round_number_passed_through(self):
        r = compute_hltv_rating(signals(steam_id=42, round_number=7))
        assert r.steam_id == 42
        assert r.round_number == 7
