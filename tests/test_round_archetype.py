"""Tests for the round archetype classifier."""

import pytest

from csda_toolkit.classifiers.round_archetype import (
    RoundArchetype,
    RoundArchetypeSignals,
    extract_round_signals,
    classify_round_archetype,
    GRENADE_RUSH_THRESHOLD,
    GRENADE_EXEC_THRESHOLD,
)


class TestRoundArchetypeSignals:
    def test_signals_post_init(self):
        s = RoundArchetypeSignals(round_number=1, was_planted=False)
        assert s.unique_attacker_zones == []
        assert s.was_planted is False
        assert s.t_total_nades == 0

    def test_was_rush_low_nades(self):
        s = RoundArchetypeSignals(round_number=1, was_planted=False, t_total_nades=1)
        assert s.was_rush is True

    def test_was_rush_at_threshold(self):
        s = RoundArchetypeSignals(round_number=1, was_planted=False, t_total_nades=GRENADE_RUSH_THRESHOLD)
        assert s.was_rush is True

    def test_was_exec(self):
        s = RoundArchetypeSignals(round_number=1, was_planted=False, t_total_nades=8)
        assert s.was_exec is True

    def test_t_avg_grenades(self):
        s = RoundArchetypeSignals(round_number=1, was_planted=False, t_total_nades=10)
        assert s.t_avg_grenades_per_player == 2.0


class TestExtractRoundSignals:
    def _make_bomb(self, event_type: str, site: str = "") -> dict:
        return {"event_type": event_type, "site": site}

    def _make_grenade(self, grenade_type: str, steam_id: int) -> dict:
        return {"grenade_type": grenade_type, "player_steam_id": steam_id}

    def _make_damage(self, attacker_steam_id: int, attacker_place: str) -> dict:
        return {"attacker_steam_id": attacker_steam_id, "attacker_last_place_name": attacker_place}

    def test_no_plant(self):
        signals = extract_round_signals(
            round_number=1,
            bomb_events=[],
            grenade_detonations=[],
            inferno_events=[],
            damage_events=[],
            t_steam_ids={1, 2, 3, 4, 5},
        )
        assert signals.was_planted is False
        assert signals.plant_site == ""
        assert signals.was_rush is True

    def test_planted_on_a(self):
        signals = extract_round_signals(
            round_number=1,
            bomb_events=[self._make_bomb("planted", "A")],
            grenade_detonations=[],
            inferno_events=[],
            damage_events=[],
            t_steam_ids={1, 2, 3, 4, 5},
        )
        assert signals.was_planted is True
        assert signals.plant_site == "A"

    def test_bomb_defused(self):
        signals = extract_round_signals(
            round_number=1,
            bomb_events=[
                self._make_bomb("planted", "B"),
                self._make_bomb("defused"),
            ],
            grenade_detonations=[],
            inferno_events=[],
            damage_events=[],
            t_steam_ids={1},
        )
        assert signals.was_planted is True
        assert signals.bomb_defused is True
        assert signals.bomb_exploded is False

    def test_grenade_counting_t_side(self):
        signals = extract_round_signals(
            round_number=1,
            bomb_events=[],
            grenade_detonations=[
                self._make_grenade("hegrenade", 1),   # T
                self._make_grenade("flashbang", 1),   # T
                self._make_grenade("smoke", 99),       # CT
            ],
            inferno_events=[],
            damage_events=[],
            t_steam_ids={1, 2, 3, 4, 5},
        )
        assert signals.t_he_count == 1
        assert signals.t_flash_count == 1
        assert signals.t_total_nades == 2
        assert signals.was_rush is True
        assert signals.ct_smoke_count == 1
        assert signals.was_rush is True

    def test_molotov_count(self):
        signals = extract_round_signals(
            round_number=1,
            bomb_events=[],
            grenade_detonations=[
                self._make_grenade("molotov", 1),
                self._make_grenade("molotov", 2),
                self._make_grenade("inferno", 3),
            ],
            inferno_events=[],
            damage_events=[],
            t_steam_ids={1, 2, 3},
        )
        assert signals.t_molotov_count == 3

    def test_attacker_zones_extracted(self):
        signals = extract_round_signals(
            round_number=1,
            bomb_events=[],
            grenade_detonations=[],
            inferno_events=[],
            damage_events=[
                self._make_damage(1, "Long A"),
                self._make_damage(2, "BombsiteA"),
                self._make_damage(3, "Mid"),
            ],
            t_steam_ids={1, 2, 3},
        )
        assert "Long A" in signals.unique_attacker_zones
        assert "BombsiteA" in signals.unique_attacker_zones
        assert "Mid" in signals.unique_attacker_zones
        assert len(signals.unique_attacker_zones) == 3

    def test_site_matches_plant(self):
        signals = extract_round_signals(
            round_number=1,
            bomb_events=[self._make_bomb("planted", "B")],
            grenade_detonations=[],
            inferno_events=[],
            damage_events=[
                self._make_damage(1, "BombsiteB"),
            ],
            t_steam_ids={1},
        )
        assert signals.site_matches_plant is True

    def test_site_does_not_match_plant(self):
        signals = extract_round_signals(
            round_number=1,
            bomb_events=[self._make_bomb("planted", "A")],
            grenade_detonations=[],
            inferno_events=[],
            damage_events=[
                self._make_damage(1, "BombsiteB"),
            ],
            t_steam_ids={1},
        )
        assert signals.site_matches_plant is False


class TestClassifyRoundArchetype:
    def _sig(
        self,
        was_planted: bool = False,
        plant_site: str = "",
        bomb_defused: bool = False,
        bomb_exploded: bool = False,
        t_total_nades: int = 0,
        ct_total_nades: int = 0,
        unique_attacker_zones: list = None,
        t_buy_type: str = "full",
        ct_buy_type: str = "full",
    ) -> RoundArchetypeSignals:
        if unique_attacker_zones is None:
            unique_attacker_zones = []
        return RoundArchetypeSignals(
            round_number=1,
            was_planted=was_planted,
            plant_site=plant_site,
            bomb_defused=bomb_defused,
            bomb_exploded=bomb_exploded,
            t_total_nades=t_total_nades,
            ct_total_nades=ct_total_nades,
            unique_attacker_zones=unique_attacker_zones,
            t_buy_type=t_buy_type,
            ct_buy_type=ct_buy_type,
        )

    def test_retakesave_ct_defused(self):
        """CT defused after plant = retakesave."""
        sig = self._sig(was_planted=True, bomb_defused=True, plant_site="B")
        arch, conf = classify_round_archetype(sig)
        assert arch == RoundArchetype.RETAKESAVE
        assert conf == 0.85

    def test_save_eco_no_plant(self):
        """Eco T side with no plant = save."""
        sig = self._sig(was_planted=False, t_buy_type="eco", t_total_nades=1)
        arch, conf = classify_round_archetype(sig)
        assert arch == RoundArchetype.SAVE
        assert conf == 0.75

    def test_contact_eco_plant(self):
        """Eco T side that plants = contact (fast rush)."""
        sig = self._sig(was_planted=True, t_buy_type="eco", t_total_nades=2, plant_site="A")
        arch, conf = classify_round_archetype(sig)
        assert arch == RoundArchetype.CONTACT
        assert conf == 0.70

    def test_fake_no_plant_high_utility(self):
        """High utility, multiple zones, but no plant = fake."""
        sig = self._sig(
            was_planted=False,
            t_total_nades=10,
            unique_attacker_zones=["Long A", "BombsiteB"],
        )
        arch, conf = classify_round_archetype(sig)
        assert arch == RoundArchetype.FAKE
        assert conf == 0.70

    def test_fake_not_enough_zones(self):
        """High utility but only one zone = exec, not fake."""
        sig = self._sig(
            was_planted=False,
            t_total_nades=10,
            unique_attacker_zones=["Long A"],
        )
        arch, conf = classify_round_archetype(sig)
        assert arch == RoundArchetype.DEFAULT

    def test_split_both_zones(self):
        """High utility, zones on both A and B, then plant = split."""
        sig = self._sig(
            was_planted=True,
            t_total_nades=10,
            plant_site="B",
            unique_attacker_zones=["Long A", "BombsiteB"],
        )
        arch, conf = classify_round_archetype(sig)
        assert arch == RoundArchetype.SPLIT
        assert conf == 0.75

    def test_split_only_one_zone(self):
        """Plant on site but only one zone hit = exec, not split."""
        sig = self._sig(
            was_planted=True,
            t_total_nades=10,
            plant_site="A",
            unique_attacker_zones=["BombsiteA"],
        )
        arch, conf = classify_round_archetype(sig)
        assert arch == RoundArchetype.EXEC

    def test_exec_high_utility_plant(self):
        """High utility + plant = exec."""
        sig = self._sig(
            was_planted=True,
            t_total_nades=8,
            plant_site="A",
            unique_attacker_zones=["Long A", "BombsiteA"],
        )
        arch, conf = classify_round_archetype(sig)
        assert arch == RoundArchetype.EXEC
        assert conf == 0.80

    def test_contact_moderate_nades_plant(self):
        """Moderate utility + plant = contact."""
        sig = self._sig(was_planted=True, t_total_nades=4, plant_site="B")
        arch, conf = classify_round_archetype(sig)
        assert arch == RoundArchetype.CONTACT
        assert conf == 0.65

    def test_default_fallthrough(self):
        """Low utility, no plant, not eco = default."""
        sig = self._sig(was_planted=False, t_total_nades=3)
        arch, conf = classify_round_archetype(sig)
        assert arch == RoundArchetype.DEFAULT
        assert conf == 0.50
