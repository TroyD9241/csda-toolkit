"""Tests for role classifier."""

import pytest

from csda_toolkit.classifiers.role_classifier import (
    AwperProfile,
    EntryFraggerProfile,
    LurkerProfile,
    PlayerKillProfile,
    PlayerWeaponProfile,
    PlayerUtilityProfile,
    PlayerPositionProfile,
    PlayerEconomyProfile,
    PlayerRoleSignals,
    RiflerProfile,
    SupportProfile,
    classify_player_role,
    build_player_role_signals,
    _score_broad_roles,
    _position_match_score,
    _most_common_position,
    _infer_zone_role,
    _evidence_strength,
    _build_entry_frag_profile,
    _build_awper_profile,
    _build_support_profile,
    _build_rifler_profile,
    _build_lurker_profile,
    score_entry_quality,
    score_awper_quality,
    score_support_quality,
    score_rifler_quality,
    score_lurker_quality,
)
from csda_toolkit.classifiers.role_taxonomy import BROAD_ROLES


class TestScoreBroadRoles:
    """Tests for per-role scoring logic."""

    def _signals(self, kills=None, weapons=None, utility=None, position=None) -> PlayerRoleSignals:
        return PlayerRoleSignals(
            steam_id=12345,
            kills=kills or PlayerKillProfile(steam_id=12345),
            weapons=weapons or PlayerWeaponProfile(steam_id=12345),
            utility=utility or PlayerUtilityProfile(steam_id=12345),
            position=position,
        )

    def test_entry_role_with_first_bloods(self):
        kp = PlayerKillProfile(steam_id=12345)
        kp.total_kills = 8
        kp.first_bloods = 4  # Above MIN_ENTRY_KILLS = 3
        kp.awp_kills = 0
        signals = self._signals(kills=kp)
        scores = _score_broad_roles(signals, "dust2", "t")
        assert scores["entry"] > 0

    def test_awper_role_with_awp_kills(self):
        kp = PlayerKillProfile(steam_id=12345)
        kp.total_kills = 10
        kp.awp_kills = 5  # Above MIN_AWP_KILLS = 3
        signals = self._signals(kills=kp)
        scores = _score_broad_roles(signals, "dust2", "t")
        assert scores["awper"] > 0

    def test_support_role_with_utility(self):
        up = PlayerUtilityProfile(steam_id=12345)
        up.flashes_thrown = 8
        up.he_detonations = 3
        up.smokes_thrown = 2
        up.total_utility_score = 8.0
        signals = self._signals(utility=up)
        scores = _score_broad_roles(signals, "dust2", "ct")
        assert scores["support"] > 0

    def test_anchor_role_ct_side(self):
        pp = PlayerPositionProfile(
            steam_id=12345, map_name="dust2", side="ct",
            position_counts={"long_a": 5, "short_a": 2},
            zone_counts={"long_a": 7},
            anchor_rounds=4,
        )
        signals = self._signals(position=pp)
        scores = _score_broad_roles(signals, "dust2", "ct")
        assert scores["anchor"] > 0

    def test_rotator_role_ct_side(self):
        pp = PlayerPositionProfile(
            steam_id=12345, map_name="dust2", side="ct",
            position_counts={"mid": 3, "long_a": 2, "b_tunnels": 2},
            zone_counts={"mid": 3, "long_a": 2, "b_tunnels": 2},
            rotator_rounds=3,
        )
        signals = self._signals(position=pp)
        scores = _score_broad_roles(signals, "dust2", "ct")
        assert scores["rotator"] > 0

    def test_second_awper_occasional_awp(self):
        wp = PlayerWeaponProfile(steam_id=12345)
        wp.awp_picks = 2  # Below MIN_AWP_KILLS = 3
        wp.awp_kills = 2
        kp = PlayerKillProfile(steam_id=12345)
        kp.awp_kills = 2
        signals = self._signals(kills=kp, weapons=wp)
        scores = _score_broad_roles(signals, "dust2", "t")
        assert scores["second_awper"] > 0

    def test_igl_override(self):
        result = classify_player_role(
            signals=PlayerRoleSignals(
                steam_id=999,
                kills=PlayerKillProfile(steam_id=999, total_kills=1),
                weapons=PlayerWeaponProfile(steam_id=999),
                utility=PlayerUtilityProfile(steam_id=999),
            ),
            map_name="dust2",
            side="t",
            igl_steam_id=999,
        )
        assert result.broad_role == "igl"
        assert result.confidence == 0.95

    def test_rifler_baseline(self):
        # Rifle player with no strong signals gets rifler score
        wp = PlayerWeaponProfile(steam_id=12345)
        wp.rifle_picks = 8
        wp.awp_picks = 0
        kp = PlayerKillProfile(steam_id=12345)
        kp.total_kills = 6
        kp.awp_kills = 0
        kp.first_bloods = 0
        signals = self._signals(kills=kp, weapons=wp)
        scores = _score_broad_roles(signals, "dust2", "t")
        assert scores["rifler"] > 0


class TestClassifyPlayerRole:
    """Tests for the main classify_player_role function."""

    def test_unknown_when_no_position(self):
        result = classify_player_role(
            signals=PlayerRoleSignals(
                steam_id=12345,
                kills=PlayerKillProfile(steam_id=12345, total_kills=0),
                weapons=PlayerWeaponProfile(steam_id=12345),
                utility=PlayerUtilityProfile(steam_id=12345),
            ),
            map_name="dust2",
            side="t",
        )
        assert result.broad_role in BROAD_ROLES
        assert result.map_position == "unknown"

    def test_position_from_position_profile(self):
        pp = PlayerPositionProfile(
            steam_id=12345, map_name="dust2", side="ct",
            position_counts={"long_a": 10, "short_a": 3},
            zone_counts={"long_a": 13},
        )
        signals = PlayerRoleSignals(
            steam_id=12345,
            kills=PlayerKillProfile(steam_id=12345),
            weapons=PlayerWeaponProfile(steam_id=12345),
            utility=PlayerUtilityProfile(steam_id=12345),
            position=pp,
        )
        result = classify_player_role(signals, "dust2", "ct")
        assert result.map_position == "long_a"

    def test_zone_role_inferred(self):
        pp = PlayerPositionProfile(
            steam_id=12345, map_name="mirage", side="ct",
            position_counts={"a_site": 8},
            zone_counts={"a_site": 8},
        )
        signals = PlayerRoleSignals(
            steam_id=12345,
            kills=PlayerKillProfile(steam_id=12345),
            weapons=PlayerWeaponProfile(steam_id=12345),
            utility=PlayerUtilityProfile(steam_id=12345),
            position=pp,
        )
        result = classify_player_role(signals, "mirage", "ct")
        assert result.zone_role == "a_anchor"

    def test_confidence_bounded(self):
        result = classify_player_role(
            signals=PlayerRoleSignals(
                steam_id=12345,
                kills=PlayerKillProfile(steam_id=12345, total_kills=20),
                weapons=PlayerWeaponProfile(steam_id=12345, awp_picks=15),
                utility=PlayerUtilityProfile(steam_id=12345),
            ),
            map_name="dust2",
            side="t",
        )
        assert 0.0 <= result.confidence <= 0.95


class TestBuildPlayerRoleSignals:
    """Tests for building PlayerRoleSignals from raw events."""

    def test_aggregates_kills(self):
        kills = [
            {"killer_steam_id": 999, "victim_steam_id": 1, "round_number": 1, "tick": 5000,
             "weapon_name": "ak47", "is_first_blood": True},
            {"killer_steam_id": 999, "victim_steam_id": 2, "round_number": 2, "tick": 60000,
             "weapon_name": "awp", "is_first_blood": False},
        ]
        signals = build_player_role_signals(kills, [], [], [], 999)
        assert signals.kills.total_kills == 2
        assert signals.kills.first_bloods == 1
        assert signals.kills.awp_kills == 1

    def test_aggregates_weapons(self):
        weapons = [
            {"steam_id": 999, "weapon_name": "ak47", "round_number": 1, "tick": 10000},
            {"steam_id": 999, "weapon_name": "awp", "round_number": 2, "tick": 60000},
            {"steam_id": 999, "weapon_name": "ak47", "round_number": 3, "tick": 110000},
        ]
        signals = build_player_role_signals([], weapons, [], [], 999)
        assert signals.weapons.rifle_picks == 2
        assert signals.weapons.awp_picks == 1

    def test_aggregates_utility(self):
        utilities = [
            {"thrower_steam_id": 999, "grenade_type": "flashbang", "round_number": 1, "tick": 5000},
            {"thrower_steam_id": 999, "grenade_type": "hegrenade", "damage": 50, "round_number": 1, "tick": 5000},
            {"thrower_steam_id": 999, "grenade_type": "smokegrenade", "round_number": 2, "tick": 60000},
        ]
        signals = build_player_role_signals([], [], utilities, [], 999)
        assert signals.utility.flashes_thrown == 1
        assert signals.utility.he_detonations == 1
        assert signals.utility.he_damage_dealt == 50.0
        assert signals.utility.smokes_thrown == 1

    def test_lurk_kill_detection(self):
        # Kill after round has been going > 10s = lurk candidate
        kills = [
            {"killer_steam_id": 999, "victim_steam_id": 1, "round_number": 1, "tick": 50000,  # > 10000 = lurk
             "weapon_name": "ak47", "is_first_blood": False},
            {"killer_steam_id": 999, "victim_steam_id": 2, "round_number": 1, "tick": 3000,   # early = not lurk
             "weapon_name": "ak47", "is_first_blood": False},
        ]
        signals = build_player_role_signals(kills, [], [], [], 999)
        assert signals.kills.lurk_kills == 1


class TestPositionMatchScore:
    """Tests for position preference matching."""

    def test_full_match(self):
        counts = {"short_a": 5, "b_tunnels": 3}
        prefs = ["short_a", "b_tunnels"]
        score = _position_match_score(counts, prefs)
        assert score == 1.0

    def test_partial_match(self):
        counts = {"short_a": 5, "mid": 5}
        prefs = ["short_a", "b_tunnels"]
        score = _position_match_score(counts, prefs)
        assert 0.0 < score < 1.0

    def test_no_match(self):
        counts = {"mid": 10}
        prefs = ["short_a", "b_tunnels"]
        score = _position_match_score(counts, prefs)
        assert score == 0.0

    def test_empty_counts(self):
        score = _position_match_score({}, ["short_a"])
        assert score == 0.0


class TestInferZoneRole:
    """Tests for zone role inference."""

    def test_a_site_ct(self):
        pp = PlayerPositionProfile(steam_id=1, map_name="dust2", side="ct",
                                   position_counts={}, zone_counts={"long_a": 5})
        assert _infer_zone_role(pp, "ct") == "sniper_lane"

    def test_a_site_t(self):
        pp = PlayerPositionProfile(steam_id=1, map_name="dust2", side="t",
                                   position_counts={}, zone_counts={"long_a": 5})
        assert _infer_zone_role(pp, "t") == "entry"

    def test_mid(self):
        pp = PlayerPositionProfile(steam_id=1, map_name="dust2", side="ct",
                                   position_counts={}, zone_counts={"mid": 8})
        assert _infer_zone_role(pp, "ct") == "mid_control"

    def test_b_site_ct(self):
        pp = PlayerPositionProfile(steam_id=1, map_name="mirage", side="ct",
                                   position_counts={}, zone_counts={"a_site": 10})
        assert _infer_zone_role(pp, "ct") == "a_anchor"


class TestEvidenceStrength:
    """Tests for evidence strength scoring."""

    def test_high_evidence(self):
        signals = PlayerRoleSignals(
            steam_id=1,
            kills=PlayerKillProfile(steam_id=1, total_kills=10),
            weapons=PlayerWeaponProfile(steam_id=1),
            utility=PlayerUtilityProfile(steam_id=1, total_utility_score=5.0),
        )
        assert _evidence_strength(signals) > 0.5

    def test_low_evidence(self):
        signals = PlayerRoleSignals(
            steam_id=1,
            kills=PlayerKillProfile(steam_id=1, total_kills=0),
            weapons=PlayerWeaponProfile(steam_id=1),
            utility=PlayerUtilityProfile(steam_id=1, total_utility_score=0.0),
        )
        assert _evidence_strength(signals) == 0.0


class TestTradeOpportunities:
    """Tests for trade_opportunities field in build_player_role_signals."""

    def test_trade_opportunity_kill_then_quick_death(self):
        """Player gets a kill then dies within 8s = trade opportunity."""
        kills_data = [
            {
                "killer_steam_id": 99,
                "victim_steam_id": 1,
                "tick": 5000,
                "round_number": 1,
                "weapon_name": "ak47",
                "is_first_blood": True,
            },
        ]
        deaths_data = [
            {
                "killer_steam_id": 2,
                "victim_steam_id": 99,
                "tick": 5800,  # 800 ticks later (~6s) = trade window
                "round_number": 1,
            },
        ]
        # Mix kills + deaths so build_player_role_signals sees both
        all_kills = kills_data + deaths_data
        signals = build_player_role_signals(
            kills_data=all_kills,
            weapon_events=[],
            utility_events=[],
            position_classifications=[],
            steam_id=99,
        )
        assert signals.kills.trade_opportunities == 1

    def test_no_trade_opportunity_death_too_late(self):
        """Player gets a kill then dies after 8s -> no trade opportunity."""
        all_kills = [
            {
                "killer_steam_id": 99,
                "victim_steam_id": 1,
                "tick": 5000,
                "round_number": 1,
                "weapon_name": "ak47",
                "is_first_blood": True,
            },
            {
                "killer_steam_id": 2,
                "victim_steam_id": 99,
                "tick": 8000,  # 3000 ticks later (>8s window)
                "round_number": 1,
            },
        ]
        signals = build_player_role_signals(
            kills_data=all_kills,
            weapon_events=[],
            utility_events=[],
            position_classifications=[],
            steam_id=99,
        )
        assert signals.kills.trade_opportunities == 0

    def test_trade_opportunity_multiple_kills_only_counts_once(self):
        """In a multi-kill round, only count one trade opportunity per round."""
        all_kills = [
            {
                "killer_steam_id": 99,
                "victim_steam_id": 1,
                "tick": 5000,
                "round_number": 1,
                "weapon_name": "ak47",
                "is_first_blood": True,
            },
            {
                "killer_steam_id": 99,
                "victim_steam_id": 3,
                "tick": 5200,
                "round_number": 1,
                "weapon_name": "ak47",
                "is_first_blood": False,
            },
            {
                "killer_steam_id": 2,
                "victim_steam_id": 99,
                "tick": 5800,
                "round_number": 1,
            },
        ]
        signals = build_player_role_signals(
            kills_data=all_kills,
            weapon_events=[],
            utility_events=[],
            position_classifications=[],
            steam_id=99,
        )
        assert signals.kills.trade_opportunities == 1


class TestEntryRoleEnhanced:
    """Tests for enhanced entry fragger scoring signals."""

    def test_entry_score_increases_with_trade_opportunities(self):
        """High trade opportunity ratio boosts entry score."""
        # Player with high trade opportunity / first blood ratio
        kills = PlayerKillProfile(
            steam_id=1,
            total_kills=10,
            first_bloods=5,
            trade_opportunities=4,  # 80% ratio -> strong entry signal
        )
        weapons = PlayerWeaponProfile(steam_id=1, rifle_picks=10, total_rounds=10)
        utility = PlayerUtilityProfile(steam_id=1)
        signals = PlayerRoleSignals(steam_id=1, kills=kills, weapons=weapons, utility=utility)
        scores = _score_broad_roles(signals, "mirage", "t")
        # With 5 first bloods and 80% trade opp ratio, entry should be high
        assert scores["entry"] > 0

    def test_first_blood_ratio_entry_signal(self):
        """High first_bloods / total_kills ratio is a dedicated entry signal."""
        # Player with 40% first blood rate -> strong entry identity
        kills = PlayerKillProfile(
            steam_id=1,
            total_kills=10,
            first_bloods=4,  # 40% ratio
            trade_opportunities=0,
        )
        weapons = PlayerWeaponProfile(steam_id=1, rifle_picks=10, total_rounds=10)
        utility = PlayerUtilityProfile(steam_id=1)
        signals = PlayerRoleSignals(steam_id=1, kills=kills, weapons=weapons, utility=utility)
        scores = _score_broad_roles(signals, "mirage", "t")
        assert scores["entry"] > 0

    def test_entry_score_low_first_blood_ratio_not_entry(self):
        """Low first_bloods / total_kills ratio -> not an entry."""
        # Player with only 10% first blood rate -> not an entry fragger
        kills = PlayerKillProfile(
            steam_id=1,
            total_kills=20,
            first_bloods=2,  # 10% ratio
            trade_opportunities=0,
        )
        weapons = PlayerWeaponProfile(steam_id=1, rifle_picks=15, total_rounds=15)
        utility = PlayerUtilityProfile(steam_id=1)
        signals = PlayerRoleSignals(steam_id=1, kills=kills, weapons=weapons, utility=utility)
        scores = _score_broad_roles(signals, "mirage", "t")
        # Entry score should be minimal or zero with only 2 first bloods
        entry_kill_bonus = 0.30 * min(1.0, 2 / 5)  # 0.12
        fb_ratio_bonus = 0.15 * min(1.0, (2 / 20) / 0.30)  # 0.15 * 0.33 = 0.05
        assert scores["entry"] < entry_kill_bonus + fb_ratio_bonus + 0.01


class TestBuildEntryFragProfile:
    """Tests for _build_entry_frag_profile."""

    def _kills(self, kills: list[dict]) -> list[dict]:
        """Return kills_data as a mix of kill events (killer and victim sides)."""
        return kills

    def test_first_blood_equals_entry_attempt(self):
        """First kill of round = entry attempt."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 1000, "round_number": 1},
            {"killer_steam_id": 99, "victim_steam_id": 2, "tick": 2000, "round_number": 1},
        ]
        ep = _build_entry_frag_profile(kills_data, [], 99)
        assert ep.entry_attempts == 1
        assert ep.successful_entries == 1
        assert ep.entry_deaths_no_kill == 0

    def test_first_death_equals_entry_attempt_no_kill(self):
        """Player dies first in round without getting a kill = entry attempt, not successful."""
        # Player 99 dies first, enemy 1 kills them
        kills_data = [
            {"killer_steam_id": 1, "victim_steam_id": 99, "tick": 1000, "round_number": 1},
            {"killer_steam_id": 2, "victim_steam_id": 3, "tick": 2000, "round_number": 1},
        ]
        ep = _build_entry_frag_profile(kills_data, [], 99)
        assert ep.entry_attempts == 1
        assert ep.successful_entries == 0
        assert ep.entry_deaths_no_kill == 1

    def test_flash_pop_kill_detected(self):
        """Teammate flash within 3s of entry kill = flash-pop."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 5000, "round_number": 1},
        ]
        # Teammate 88 throws flash at tick 4700, entry kill at tick 5000 (300 ticks = 2.3s)
        utility_events = [
            {"thrower_steam_id": 88, "grenade_type": "flashbang", "tick": 4700, "round_number": 1},
        ]
        ep = _build_entry_frag_profile(kills_data, utility_events, 99)
        assert ep.flash_pop_kills == 1

    def test_self_flash_not_counted(self):
        """Self-flash (player throws their own flash before entry kill) does not count."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 5000, "round_number": 1},
        ]
        utility_events = [
            {"thrower_steam_id": 99, "grenade_type": "flashbang", "tick": 4700, "round_number": 1},
        ]
        ep = _build_entry_frag_profile(kills_data, utility_events, 99)
        assert ep.flash_pop_kills == 0

    def test_flash_too_late_not_counted(self):
        """Flash thrown after the kill = not a flash-pop."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 5000, "round_number": 1},
        ]
        utility_events = [
            {"thrower_steam_id": 88, "grenade_type": "flashbang", "tick": 5200, "round_number": 1},
        ]
        ep = _build_entry_frag_profile(kills_data, utility_events, 99)
        assert ep.flash_pop_kills == 0

    def test_survived_post_entry(self):
        """Player got entry kill and survived the round."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 2000, "round_number": 1},
        ]
        # No death events for player 99 this round
        ep = _build_entry_frag_profile(kills_data, [], 99)
        assert ep.rounds_survived_post_entry == 1

    def test_died_after_entry_kill_no_survival(self):
        """Player got entry kill then died = no survival credit."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 2000, "round_number": 1},
            {"killer_steam_id": 2, "victim_steam_id": 99, "tick": 4000, "round_number": 1},
        ]
        ep = _build_entry_frag_profile(kills_data, [], 99)
        assert ep.rounds_survived_post_entry == 0
        assert ep.successful_entries == 1

    def test_multi_kill_entry_round(self):
        """Round with multiple kills from same player counts as one entry attempt."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 2000, "round_number": 1},
            {"killer_steam_id": 99, "victim_steam_id": 2, "tick": 2200, "round_number": 1},
            {"killer_steam_id": 99, "victim_steam_id": 3, "tick": 2400, "round_number": 1},
        ]
        ep = _build_entry_frag_profile(kills_data, [], 99)
        assert ep.entry_attempts == 1
        assert ep.successful_entries == 1
        assert ep.total_kills_in_entry_rounds == 3

    def test_opening_duel_win(self):
        """First kill of the round = opening duel win."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 1000, "round_number": 1},
            {"killer_steam_id": 3, "victim_steam_id": 4, "tick": 2000, "round_number": 1},
        ]
        ep = _build_entry_frag_profile(kills_data, [], 99)
        assert ep.opening_duel_wins == 1


class TestScoreEntryQuality:
    """Tests for score_entry_quality function."""

    def test_elite_entry(self):
        """Elite entry: 50%+ kill rate, high flash-pop, survives often."""
        ep = EntryFraggerProfile(
            steam_id=1,
            entry_attempts=20,
            successful_entries=10,       # 50% kill rate
            flash_pop_kills=6,           # 60% flash-pop rate
            opening_duel_wins=10,
            rounds_survived_post_entry=7,
            total_kills_in_entry_rounds=12,
            rounds_with_entry_attempt=20,
        )
        score = score_entry_quality(ep)
        # entry_kill_rate = 10/20 = 0.50 -> score 1.0
        # flash_pop = 6/10 = 0.60 -> score 1.0
        # survival = 7/10 = 0.70 -> capped at 1.0
        # opening_duel = 10/20 = 0.50 -> score 1.0
        assert score == 1.0

    def test_average_entry(self):
        """Average entry: ~30% kill rate, some flash-pops, moderate survival."""
        ep = EntryFraggerProfile(
            steam_id=1,
            entry_attempts=20,
            successful_entries=6,        # 30% kill rate
            flash_pop_kills=2,
            opening_duel_wins=6,
            rounds_survived_post_entry=3,
            total_kills_in_entry_rounds=6,
            rounds_with_entry_attempt=20,
        )
        score = score_entry_quality(ep)
        assert 0.6 < score < 0.8

    def test_zero_attempts(self):
        """No entry attempts = 0 quality."""
        ep = EntryFraggerProfile(steam_id=1)
        assert score_entry_quality(ep) == 0.0

    def test_liability_entry_no_kills(self):
        """Entry who never gets a kill = liability."""
        ep = EntryFraggerProfile(
            steam_id=1,
            entry_attempts=10,
            successful_entries=0,
            entry_deaths_no_kill=10,
            flash_pop_kills=0,
            opening_duel_wins=0,
            rounds_survived_post_entry=0,
            total_kills_in_entry_rounds=0,
            rounds_with_entry_attempt=10,
        )
        assert score_entry_quality(ep) == 0.0

    def test_components_weighted_correctly(self):
        """Score reflects weighted contributions of all 4 components."""
        ep = EntryFraggerProfile(
            steam_id=1,
            entry_attempts=10,
            successful_entries=4,        # 40% kill rate -> entry_kill_score = 1.0
            flash_pop_kills=0,            # 0% flash-pop
            opening_duel_wins=5,          # 50% opening duel rate -> score = 1.0
            rounds_survived_post_entry=4, # 100% survival -> score = 1.0
            total_kills_in_entry_rounds=4,
            rounds_with_entry_attempt=10,
        )
        # Expected: 0.40*1.0 + 0.20*0 + 0.20*1.0 + 0.20*1.0 = 0.40 + 0 + 0.20 + 0.20 = 0.80
        assert score_entry_quality(ep) == 0.80


class TestEntryFragProfileInSignals:
    """Tests that entry frag profile is properly embedded in PlayerRoleSignals."""

    def test_build_player_role_signals_includes_entry_frag(self):
        """build_player_role_signals returns PlayerRoleSignals with entry_frag populated."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 1000, "round_number": 1},
        ]
        signals = build_player_role_signals(
            kills_data=kills_data,
            weapon_events=[],
            utility_events=[],
            position_classifications=[],
            steam_id=99,
        )
        assert signals.entry_frag is not None
        assert signals.entry_frag.steam_id == 99
        assert signals.entry_frag.successful_entries == 1
        assert signals.entry_frag.entry_attempts == 1


class TestBuildAwperProfile:
    """Tests for _build_awper_profile."""

    def test_first_pick_detected(self):
        """Player AWP kill is first kill of round = first pick."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 2000, "round_number": 1},
            {"killer_steam_id": 2, "victim_steam_id": 3, "tick": 3000, "round_number": 1},
        ]
        weapon_events = [
            {"steam_id": 99, "weapon_name": "AWP", "round_number": 1},
        ]
        ap = _build_awper_profile(kills_data, weapon_events, [], 99)
        assert ap.awp_rounds == 1
        assert ap.first_pick_rounds == 1

    def test_no_awp_no_profile(self):
        """No AWP equipped = 0 awp_rounds."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 2000, "round_number": 1},
        ]
        weapon_events = [
            {"steam_id": 99, "weapon_name": "AK47", "round_number": 1},
        ]
        ap = _build_awper_profile(kills_data, weapon_events, [], 99)
        assert ap.awp_rounds == 0


class TestBuildSupportProfile:
    """Tests for _build_support_profile."""

    def test_trade_detected(self):
        """Teammate dies first (tick 2000), player gets kill within 5s (tick 2400) = successful trade."""
        # Player 99 gets a kill first (tick 2000, victim=1)
        # Teammate player 2 dies (tick 2200)
        # Player 99 gets second kill (tick 2400, victim=3) — trade!
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 2000, "round_number": 1},
            {"killer_steam_id": 3, "victim_steam_id": 2, "tick": 2200, "round_number": 1},
            {"killer_steam_id": 99, "victim_steam_id": 3, "tick": 2400, "round_number": 1},
        ]
        sp = _build_support_profile(kills_data, [], 99)
        assert sp.trade_opportunities == 1
        assert sp.successful_trades == 1

    def test_no_trade_when_player_dies_first(self):
        """Player dies first = no trade opportunity, even if they get a kill later."""
        kills_data = [
            {"killer_steam_id": 3, "victim_steam_id": 99, "tick": 2000, "round_number": 1},
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 2400, "round_number": 1},
        ]
        sp = _build_support_profile(kills_data, [], 99)
        assert sp.trade_opportunities == 0

    def test_utility_rounds_counted(self):
        """Smoke/flash/he rounds counted in utility_rounds."""
        utility_events = [
            {"thrower_steam_id": 99, "grenade_type": "smokegrenade", "tick": 1000, "round_number": 1},
            {"thrower_steam_id": 99, "grenade_type": "flashbang", "tick": 1100, "round_number": 1},
        ]
        sp = _build_support_profile([], utility_events, 99)
        assert sp.support_rounds == 1
        assert sp.utility_rounds == 1
        assert sp.smoke_rounds == 1
        assert sp.flash_rounds == 1


class TestBuildRiflerProfile:
    """Tests for _build_rifler_profile."""

    def test_multi_kill_round_detected(self):
        """Two kills in one round = multi_kill_rounds."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 2000, "round_number": 1},
            {"killer_steam_id": 99, "victim_steam_id": 2, "tick": 2200, "round_number": 1},
        ]
        weapon_events = [
            {"steam_id": 99, "weapon_name": "AK47", "round_number": 1},
        ]
        rp = _build_rifler_profile(kills_data, weapon_events, [], 99)
        assert rp.rifler_rounds == 1
        assert rp.multi_kill_rounds == 1

    def test_trade_kill_detected(self):
        """Teammate dies first (tick 2000), player gets kill within 5s (tick 2400) = trade."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 2000, "round_number": 1},
            {"killer_steam_id": 3, "victim_steam_id": 2, "tick": 2200, "round_number": 1},
            {"killer_steam_id": 99, "victim_steam_id": 3, "tick": 2400, "round_number": 1},
        ]
        weapon_events = [
            {"steam_id": 99, "weapon_name": "AK47", "round_number": 1},
        ]
        rp = _build_rifler_profile(kills_data, weapon_events, [], 99)
        assert rp.trade_kills == 1

    def test_multi_kill_round_detected(self):
        """Two kills in one round = multi_kill_rounds."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 2000, "round_number": 1},
            {"killer_steam_id": 99, "victim_steam_id": 2, "tick": 2300, "round_number": 1},
        ]
        weapon_events = [
            {"steam_id": 99, "weapon_name": "AK47", "round_number": 1},
        ]
        rp = _build_rifler_profile(kills_data, weapon_events, [], 99)
        assert rp.rifler_rounds == 1
        assert rp.multi_kill_rounds == 1  # 2 kills in round 1


class TestBuildLurkerProfile:
    """Tests for _build_lurker_profile."""

    def test_late_round_kill_detected_as_lurk(self):
        """Late-round kill (tick > 15000) in isolated round = lurk attempt."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 16000, "round_number": 1},
        ]
        # No teammate deaths before kill tick, so it's treated as late-round solo
        lp = _build_lurker_profile(kills_data, [], 99)
        assert lp.lurk_attempts == 1
        assert lp.solo_kills == 1


class TestScoreAwperQuality:
    """Tests for score_awper_quality."""

    def test_elite_awper(self):
        """Elite AWP: high first pick rate, survives on CT."""
        ap = AwperProfile(
            steam_id=1,
            awp_rounds=20,
            first_pick_rounds=8,       # 40% first pick
            ct_hold_picks=5,
            ct_survived_after_pick=4,  # 80% survival
            awp_saves=3,
            awp_deaths_on_eco=1,
        )
        score = score_awper_quality(ap)
        assert 0.6 < score <= 1.0

    def test_zero_awp_rounds(self):
        """No AWP rounds = 0 quality."""
        ap = AwperProfile(steam_id=1)
        assert score_awper_quality(ap) == 0.0


class TestScoreSupportQuality:
    """Tests for score_support_quality."""

    def test_elite_support(self):
        """Elite support: high trade success, flash assists, utility."""
        sp = SupportProfile(
            steam_id=1,
            support_rounds=20,
            successful_trades=12,
            trade_opportunities=15,     # 80% trade success
            flash_assisted_kills=8,
            utility_rounds=18,
            smoke_rounds=10,
            flash_rounds=12,
            he_rounds=6,
            economy_sacrifice_rounds=4,
        )
        score = score_support_quality(sp)
        assert 0.5 < score <= 1.0

    def test_zero_support_rounds(self):
        """No support rounds = 0 quality."""
        sp = SupportProfile(steam_id=1)
        assert score_support_quality(sp) == 0.0


class TestScoreRiflerQuality:
    """Tests for score_rifler_quality."""

    def test_elite_rifler(self):
        """Elite rifler: multi-kill rounds, trade kills, high HS rate."""
        rp = RiflerProfile(
            steam_id=1,
            rifler_rounds=20,
            multi_kill_rounds=8,     # 40% multi-kill
            trade_kills=6,          # 30% trade
            headshot_rate=0.45,     # 45% HS
            ct_site_anchor_rounds=5,
            ct_survived_anchor=4,  # 80% anchor survival
        )
        score = score_rifler_quality(rp)
        assert 0.6 < score <= 1.0

    def test_zero_rifler_rounds(self):
        """No rifle rounds = 0 quality."""
        rp = RiflerProfile(steam_id=1)
        assert score_rifler_quality(rp) == 0.0


class TestScoreLurkerQuality:
    """Tests for score_lurker_quality."""

    def test_elite_lurker(self):
        """Elite lurker: high solo kill rate, survives, clutch ability."""
        lp = LurkerProfile(
            steam_id=1,
            lurk_attempts=10,
            solo_kills=6,          # 60% solo kill
            rotation_cut_kills=3,
            flank_kills=4,
            survived_lurk_rounds=7,  # 70% survival
            clutch_rounds=3,
            clutch_rounds_won=2,     # 67% clutch win
        )
        score = score_lurker_quality(lp)
        assert 0.6 < score <= 1.0

    def test_zero_lurk_attempts(self):
        """No lurk attempts = 0 quality."""
        lp = LurkerProfile(steam_id=1)
        assert score_lurker_quality(lp) == 0.0


class TestAllProfilesInSignals:
    """Tests that build_player_role_signals populates all role profiles."""

    def test_all_profiles_populated(self):
        """build_player_role_signals returns PlayerRoleSignals with all 5 profiles."""
        kills_data = [
            {"killer_steam_id": 99, "victim_steam_id": 1, "tick": 1000, "round_number": 1},
        ]
        weapon_events = [
            {"steam_id": 99, "weapon_name": "AK47", "round_number": 1},
        ]
        signals = build_player_role_signals(
            kills_data=kills_data,
            weapon_events=weapon_events,
            utility_events=[],
            position_classifications=[],
            steam_id=99,
        )
        assert signals.awper is not None
        assert signals.awper.steam_id == 99
        assert signals.support is not None
        assert signals.support.steam_id == 99
        assert signals.rifler is not None
        assert signals.rifler.steam_id == 99
        assert signals.lurker is not None
        assert signals.lurker.steam_id == 99
