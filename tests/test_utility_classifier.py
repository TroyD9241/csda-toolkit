"""Tests for the utility classifier."""

import pytest

from csda_toolkit.classifiers.utility_classifier import (
    UtilityQuality,
    UtilityThrow,
    UtilityRoundSummary,
    evaluate_he_grenade,
    evaluate_flashbang,
    evaluate_molotov,
    evaluate_smoke,
    summarize_player_utility,
    FLASHBLIND_GOOD_SECONDS,
    FLASHBLIND_DECENT_SECONDS,
)


class TestEvaluateHeGrenade:
    def _det(self, tick: int = 1000, x: float = 0.0, y: float = 0.0) -> dict:
        return {"tick": tick, "round_number": 1, "grenade_type": "hegrenade",
                "x": x, "y": y, "z": 0.0, "player_name": "player1"}

    def _dmg(self, tick: int, attacker: int, victim: int, weapon: str = "hegrenade",
             dmg_health: int = 0) -> dict:
        return {"tick": tick, "attacker_steam_id": attacker, "victim_steam_id": victim,
                "weapon": weapon, "dmg_health": dmg_health, "victim_name": "vic",
                "attacker_name": "att"}

    def test_hit_enemy(self):
        det = self._det(tick=1000)
        dmg_events = [self._dmg(tick=1000, attacker=1, victim=2, dmg_health=85)]
        result = evaluate_he_grenade(det, dmg_events, steam_id=1)
        assert result.quality == UtilityQuality.GOOD
        assert result.damage_dealt == 85
        assert result.hit_victim_steam_id == 2

    def test_hit_multiple_enemies(self):
        det = self._det(tick=1000)
        dmg_events = [
            self._dmg(tick=1000, attacker=1, victim=2, dmg_health=50),
            self._dmg(tick=1000, attacker=1, victim=3, dmg_health=35),
        ]
        result = evaluate_he_grenade(det, dmg_events, steam_id=1)
        assert result.quality == UtilityQuality.GOOD
        assert result.damage_dealt == 85

    def test_self_damage(self):
        det = self._det(tick=1000)
        dmg_events = [self._dmg(tick=1000, attacker=1, victim=1, dmg_health=15)]
        result = evaluate_he_grenade(det, dmg_events, steam_id=1)
        assert result.quality == UtilityQuality.SELF_DAMAGE
        assert result.damage_dealt == 15

    def test_no_damage(self):
        det = self._det(tick=1000)
        result = evaluate_he_grenade(det, [], steam_id=1)
        assert result.quality == UtilityQuality.MISSED
        assert result.confidence == 0.6


class TestEvaluateFlashbang:
    def _det(self, tick: int = 1000) -> dict:
        return {"tick": tick, "round_number": 1, "grenade_type": "flashbang",
                "x": 0.0, "y": 0.0, "z": 0.0, "player_name": "player1"}

    def _blind(self, tick: int, attacker: int, victim: int, duration: float) -> dict:
        return {"tick": tick, "attacker_steam_id": attacker, "victim_steam_id": victim,
                "blind_duration": duration, "attacker_name": "att", "victim_name": "vic"}

    def test_good_blind(self):
        det = self._det(tick=1000)
        blinds = [self._blind(tick=1000, attacker=1, victim=2, duration=2.5)]
        result = evaluate_flashbang(det, blinds, steam_id=1)
        assert result.quality == UtilityQuality.GOOD
        assert result.blind_duration == 2.5

    def test_decent_blind(self):
        det = self._det(tick=1000)
        blinds = [self._blind(tick=1000, attacker=1, victim=2, duration=1.0)]
        result = evaluate_flashbang(det, blinds, steam_id=1)
        assert result.quality == UtilityQuality.DECENT

    def test_short_blind(self):
        det = self._det(tick=1000)
        blinds = [self._blind(tick=1000, attacker=1, victim=2, duration=0.3)]
        result = evaluate_flashbang(det, blinds, steam_id=1)
        assert result.quality == UtilityQuality.MISSED

    def test_whiffed_no_blind(self):
        det = self._det(tick=1000)
        result = evaluate_flashbang(det, [], steam_id=1)
        assert result.quality == UtilityQuality.WHIFFED

    def test_self_flash(self):
        det = self._det(tick=1000)
        blinds = [
            self._blind(tick=1000, attacker=1, victim=1, duration=1.0),  # self
        ]
        result = evaluate_flashbang(det, blinds, steam_id=1)
        # Only self-flashed, no enemies → SELF_DAMAGE
        assert result.quality == UtilityQuality.SELF_DAMAGE

    def test_self_flash_and_enemy_blind(self):
        det = self._det(tick=1000)
        blinds = [
            self._blind(tick=1000, attacker=1, victim=1, duration=1.0),   # self
            self._blind(tick=1000, attacker=1, victim=2, duration=2.0),  # enemy
        ]
        result = evaluate_flashbang(det, blinds, steam_id=1)
        assert result.quality == UtilityQuality.GOOD


class TestEvaluateMolotov:
    def _det(self, x: float = 0.0, y: float = 0.0) -> dict:
        return {"tick": 1000, "round_number": 1, "grenade_type": "molotov",
                "x": x, "y": y, "z": 0.0, "player_name": "player1"}

    def _inferno(self, x: float, y: float) -> dict:
        return {"event_type": "start_burn", "x": x, "y": y, "z": 0.0}

    def test_burning(self):
        det = self._det(x=100.0, y=200.0)
        infernos = [self._inferno(x=120.0, y=210.0)]  # within 150 units
        result = evaluate_molotov(det, infernos, [], steam_id=1)
        assert result.quality == UtilityQuality.GOOD

    def test_no_burn_but_damage(self):
        det = self._det(x=100.0, y=200.0)
        dmg = [{"attacker_steam_id": 1, "victim_steam_id": 2, "weapon": "inferno",
                "dmg_health": 30, "tick": 1000}]
        result = evaluate_molotov(det, [], dmg, steam_id=1)
        assert result.quality == UtilityQuality.GOOD
        assert result.damage_dealt == 30

    def test_missed(self):
        det = self._det(x=100.0, y=200.0)
        result = evaluate_molotov(det, [], [], steam_id=1)
        assert result.quality == UtilityQuality.MISSED


class TestEvaluateSmoke:
    def _det(self, gtype: str = "smoke_expired", zone: str = "") -> dict:
        d = {"tick": 1000, "round_number": 1, "grenade_type": gtype,
             "x": 0.0, "y": 0.0, "z": 0.0, "player_name": "player1"}
        if zone:
            d["landed_zone"] = zone
        return d

    def test_expired_zone_boost(self):
        # When zone data is provided (from damage event correlation), it boosts quality
        det = self._det(gtype="smoke_expired", zone="Long A")
        result = evaluate_smoke(det, [], steam_id=1, landed_zone="Long A")
        # expired + zone boost = GOOD (zone boost overrides DECENT)
        assert result.quality == UtilityQuality.GOOD

    def test_active_smoke(self):
        det = self._det(gtype="smoke")
        result = evaluate_smoke(det, [], steam_id=1)
        # Active smoke with no zone info = PENDING (might still be useful)
        assert result.quality == UtilityQuality.PENDING


class TestSummarizePlayerUtility:
    def _throw(self, gtype: str, quality: UtilityQuality) -> UtilityThrow:
        return UtilityThrow(
            steam_id=1, player_name="player1", round_number=1,
            grenade_type=gtype, quality=quality, confidence=0.8,
        )

    def test_all_counts(self):
        throws = [
            self._throw("hegrenade", UtilityQuality.GOOD),
            self._throw("hegrenade", UtilityQuality.MISSED),
            self._throw("flashbang", UtilityQuality.GOOD),
            self._throw("flashbang", UtilityQuality.DECENT),
            self._throw("flashbang", UtilityQuality.WHIFFED),
            self._throw("smoke", UtilityQuality.GOOD),
            self._throw("smoke", UtilityQuality.PENDING),
            self._throw("molotov", UtilityQuality.GOOD),
            self._throw("molotov", UtilityQuality.MISSED),
        ]
        s = summarize_player_utility(throws)
        assert s.total_throws == 9
        assert s.good_he == 1
        assert s.missed_he == 1
        assert s.good_flash == 1
        assert s.decent_flash == 1
        assert s.missed_flash == 1
        assert s.good_smoke == 1
        assert s.pending_smoke == 1
        assert s.good_molotov == 1
        assert s.missed_molotov == 1

    def test_empty(self):
        s = summarize_player_utility([])
        assert s.total_throws == 0
        assert s.utility_score == 0.0

    def test_utility_score(self):
        # 3 good HE + 1 missed molotov
        throws = [
            self._throw("hegrenade", UtilityQuality.GOOD),
            self._throw("hegrenade", UtilityQuality.GOOD),
            self._throw("hegrenade", UtilityQuality.GOOD),
            self._throw("molotov", UtilityQuality.MISSED),
        ]
        s = summarize_player_utility(throws)
        # score = (3*1.0 + 1*(-0.4)) / (4*1.2) = 2.6/4.8 ≈ 0.542
        assert s.utility_score > 0.5
        assert s.utility_score < 0.6
