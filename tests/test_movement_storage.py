"""Tests for movement storage."""

import pytest

from csda_toolkit.classifiers.movement_storage import (
    categorize_zone,
    sample_keyframes,
    extract_zone_transitions,
    compute_movement_summary,
    KEYFRAME_TICK_INTERVAL,
    PlayerRoundKeyframe,
)


class TestCategorizeZone:
    def test_bombsite(self):
        assert categorize_zone("BombsiteA") == "site"
        assert categorize_zone("bombsiteb") == "site"
        assert categorize_zone("A Site") == "site"
        assert categorize_zone("Long A") == "site"

    def test_mid(self):
        assert categorize_zone("Mid") == "mid"
        assert categorize_zone("middoors") == "mid"

    def test_spawn(self):
        assert categorize_zone("T Spawn") == "spawn"
        assert categorize_zone("CT Spawn") == "spawn"
        assert categorize_zone("outside") == "spawn"

    def test_connector(self):
        assert categorize_zone("Connector") == "connector"
        assert categorize_zone("access") == "connector"

    def test_unknown(self):
        assert categorize_zone("some_weird_zone") == "unknown"
        assert categorize_zone("") == "unknown"


class TestSampleKeyframes:
    def _frame(self, tick: int, steam_id: int = 1, x: float = 0.0, y: float = 0.0) -> dict:
        return {
            "tick": tick, "round_number": 1, "steam_id": steam_id,
            "name": "player1", "x": x, "y": y, "z": 0.0,
            "eye_angle_x": 0.0, "eye_angle_y": 0.0, "eye_angle_z": 0.0,
            "velocity_modifier": 1.0, "is_alive": True, "health": 100,
            "side": "t",
        }

    def test_empty(self):
        result = sample_keyframes([], match_id=1)
        assert result == []

    def test_single_frame(self):
        frames = [self._frame(tick=100)]
        result = sample_keyframes(frames, match_id=1)
        assert len(result) == 1
        assert result[0].tick == 100

    def test_samples_at_interval(self):
        # 5 frames at ticks 0, 500, 1000, 1500, 2000 (KEYFRAME_INTERVAL=1000)
        frames = [self._frame(tick=t) for t in [0, 500, 1000, 1500, 2000]]
        result = sample_keyframes(frames, match_id=1)
        # Should sample at tick 0 and 1000 (and 2000 as last tick)
        ticks = [kf.tick for kf in result]
        assert 0 in ticks
        assert 1000 in ticks
        assert 2000 in ticks

    def test_last_tick_always_included(self):
        frames = [self._frame(tick=t) for t in [0, 500, 999]]  # 999 < 1000 interval
        result = sample_keyframes(frames, match_id=1)
        ticks = [kf.tick for kf in result]
        assert 999 in ticks  # last tick included

    def test_multiple_players(self):
        frames = [self._frame(tick=0, steam_id=1), self._frame(tick=0, steam_id=2)]
        result = sample_keyframes(frames, match_id=1)
        assert len(result) == 2


class TestExtractZoneTransitions:
    def _dmg(self, tick: int, sid: int, rn: int, zone: str, team: str = "TERRORIST") -> dict:
        return {
            "tick": tick, "round_number": rn, "attacker_steam_id": sid,
            "attacker_name": f"player{sid}", "attacker_last_place_name": zone,
            "attacker_team_name": team,
        }

    def test_empty(self):
        result = extract_zone_transitions([], match_id=1)
        assert result == []

    def test_single_zone(self):
        events = [self._dmg(tick=1000, sid=1, rn=1, zone="Long A")]
        result = extract_zone_transitions(events, match_id=1)
        assert len(result) == 1
        assert result[0].zone == "Long A"
        assert result[0].zone_category == "site"

    def test_zone_change(self):
        events = [
            self._dmg(tick=1000, sid=1, rn=1, zone="T Spawn"),
            self._dmg(tick=2000, sid=1, rn=1, zone="Long A"),
            self._dmg(tick=3000, sid=1, rn=1, zone="BombsiteA"),
        ]
        result = extract_zone_transitions(events, match_id=1)
        assert len(result) == 3  # 3 distinct zones
        zones = [r.zone for r in result]
        assert "T Spawn" in zones
        assert "Long A" in zones
        assert "BombsiteA" in zones

    def test_same_zone_no_duplicate(self):
        events = [
            self._dmg(tick=1000, sid=1, rn=1, zone="Long A"),
            self._dmg(tick=2000, sid=1, rn=1, zone="Long A"),  # same zone
            self._dmg(tick=3000, sid=1, rn=1, zone="Mid"),
        ]
        result = extract_zone_transitions(events, match_id=1)
        assert len(result) == 2  # only distinct zone changes

    def test_different_players(self):
        events = [
            self._dmg(tick=1000, sid=1, rn=1, zone="Mid"),
            self._dmg(tick=1000, sid=2, rn=1, zone="Long A"),
        ]
        result = extract_zone_transitions(events, match_id=1)
        assert len(result) == 2

    def test_different_rounds(self):
        events = [
            self._dmg(tick=1000, sid=1, rn=1, zone="Mid"),
            self._dmg(tick=10000, sid=1, rn=2, zone="Long A"),
        ]
        result = extract_zone_transitions(events, match_id=1)
        assert len(result) == 2

    def test_no_steam_id_skipped(self):
        events = [{"tick": 1000, "round_number": 1, "attacker_steam_id": None}]
        result = extract_zone_transitions(events, match_id=1)
        assert result == []


class TestComputeMovementSummary:
    def _kf(self, tick: int, sid: int, x: float = 0.0, is_alive: bool = True) -> PlayerRoundKeyframe:
        return PlayerRoundKeyframe(
            match_id=1,
            round_number=1,
            steam_id=sid,
            player_name=f"player{sid}",
            tick=tick,
            x=x,
            y=0.0,
            z=0.0,
            eye_angle_x=0.0,
            eye_angle_y=0.0,
            eye_angle_z=0.0,
            velocity_modifier=1.0,
            is_alive=is_alive,
            health=100,
            side="t",
        )

    def test_empty(self):
        result = compute_movement_summary([], [], [], [], match_id=1)
        assert result == []

    def test_distance_calculation(self):
        # Keyframes at tick 0 (x=0), 1000 (x=1000), 2000 (x=2000)
        # Distance: sqrt((1000-0)^2) = 1000 per interval
        keyframes = [self._kf(tick=0, sid=1, x=0.0),
                     self._kf(tick=1000, sid=1, x=1000.0),
                     self._kf(tick=2000, sid=1, x=2000.0)]
        result = compute_movement_summary(
            keyframes=keyframes,
            zone_transitions=[],
            damage_events=[],
            kill_events=[],
            match_id=1,
        )
        assert len(result) == 1
        s = result[0]
        assert s.total_distance > 0
        assert s.avg_speed > 0

    def test_movement_score(self):
        keyframes = [self._kf(tick=0, sid=1, x=0.0),
                     self._kf(tick=1000, sid=1, x=1000.0),
                     self._kf(tick=2000, sid=1, x=2000.0)]
        result = compute_movement_summary(
            keyframes=keyframes,
            zone_transitions=[],
            damage_events=[],
            kill_events=[],
            match_id=1,
        )
        assert 0.0 < result[0].movement_score <= 1.0

    def test_dead_player(self):
        keyframes = [self._kf(tick=0, sid=1, x=0.0, is_alive=False)]
        result = compute_movement_summary(
            keyframes=keyframes,
            zone_transitions=[],
            damage_events=[],
            kill_events=[],
            match_id=1,
        )
        assert result[0].avg_speed == 0.0
