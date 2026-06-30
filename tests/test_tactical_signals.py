"""Tests for tactical signal detection."""

import pytest

from csda_toolkit.classifiers.tactical_signals import (
    TacticalSignal,
    RoundClusterResult,
    cluster_round_positions,
    detect_ct_stack,
    detect_ct_rotate,
    detect_t_fast_execute,
    detect_t_split,
    detect_t_fake,
    classify_round_tactical_signals,
    _map_site_centroids,
    _closer_to,
)


class TestClusterRoundPositions:
    """Tests for k-means position clustering."""

    def _frame(self, x: float, y: float, side: str, tick: int = 10000) -> dict:
        return {"x": x, "y": y, "z": 0.0, "side": side, "steam_id": 1, "tick": tick}

    def test_single_ct_cluster_a_site(self):
        # 4 CT players clustered at Long A (dust2 site A = negative coords)
        frames = [
            self._frame(-1200, -2300, "ct", tick=10000),
            self._frame(-1300, -2400, "ct", tick=10000),
            self._frame(-1100, -2350, "ct", tick=10000),
            self._frame(-1250, -2200, "ct", tick=10000),
        ]
        result = cluster_round_positions(frames, tick=10000, map_name="dust2")
        assert result is not None
        # All frames are closer to site A centroid (-1400, -2400)
        assert result.ct_players_in_a >= 3

    def test_single_t_cluster_b_site(self):
        # 3 T players at B tunnels (dust2 site B = positive coords)
        frames = [
            self._frame(800, 1700, "t", tick=10000),
            self._frame(900, 1600, "t", tick=10000),
            self._frame(700, 1800, "t", tick=10000),
        ]
        result = cluster_round_positions(frames, tick=10000, map_name="dust2")
        assert result is not None
        assert result.dominant_t_site == "b"
        assert result.t_players_in_b >= 2

    def test_split_teams(self):
        # 3 CT at A, 2 CT at B → dominant is A (more players)
        frames = [
            self._frame(-1200, -2300, "ct", tick=10000),
            self._frame(-1300, -2400, "ct", tick=10000),
            self._frame(-1100, -2350, "ct", tick=10000),
            self._frame(800, 1700, "ct", tick=10000),
            self._frame(900, 1600, "ct", tick=10000),
        ]
        result = cluster_round_positions(frames, tick=10000, map_name="dust2")
        assert result is not None
        # dominant = "a" when ct_a > ct_b (3 > 2), "split" only when equal
        assert result.dominant_ct_site in ("a", "split")
        assert result.ct_players_in_a >= 3

    def test_no_matching_tick(self):
        frames = [self._frame(-1200, -2300, "ct", tick=9999)]
        result = cluster_round_positions(frames, tick=10000, map_name="dust2")
        assert result is None

    def test_all_spawn_returns_none(self):
        frames = []
        result = cluster_round_positions(frames, tick=10000, map_name="dust2")
        assert result is None


class TestDetectCTStack:
    """Tests for CT stack signal detection."""

    def _cluster(self, dominant_ct: str, ct_a: int, ct_b: int) -> RoundClusterResult:
        return RoundClusterResult(
            tick=10000,
            site_a_centroid=(-1400, -2400),
            site_b_centroid=(900, 1700),
            ct_players_in_a=ct_a,
            ct_players_in_b=ct_b,
            t_players_in_a=0,
            t_players_in_b=0,
            dominant_ct_site=dominant_ct,
            dominant_t_site="split",
            confidence=0.8,
        )

    def test_stack_correct_ct_won(self):
        # 4 CT at A, T committed to A, CT won
        cluster = self._cluster("a", 4, 0)
        signal = detect_ct_stack(None, cluster, t_committed_site="a", ct_won=True, mid_round_tick=10000)
        assert signal is not None
        assert signal.signal_type == "ct_stack_correct"
        assert signal.side == "ct"
        assert signal.metadata["stacked_site"] == "a"
        assert signal.metadata["ct_count"] == 4

    def test_stack_correct_t_won(self):
        # 4 CT at A, T committed to A, CT lost — still correct stack, different outcome
        cluster = self._cluster("a", 4, 0)
        signal = detect_ct_stack(None, cluster, t_committed_site="a", ct_won=False, mid_round_tick=10000)
        assert signal is not None
        assert signal.signal_type == "ct_stack_correct"
        assert signal.confidence < 0.8  # Lower confidence when CT lost

    def test_stack_wrong(self):
        # 4 CT at A, T committed to B
        cluster = self._cluster("a", 4, 0)
        signal = detect_ct_stack(None, cluster, t_committed_site="b", ct_won=False, mid_round_tick=10000)
        assert signal is not None
        assert signal.signal_type == "ct_stack_wrong"

    def test_stack_insufficient_players(self):
        # Only 3 CT at site — below threshold
        cluster = self._cluster("a", 3, 1)
        signal = detect_ct_stack(None, cluster, t_committed_site="a", ct_won=True, mid_round_tick=10000)
        assert signal is None


class TestDetectCTRotate:
    """Tests for CT rotation signal detection."""

    def _cluster(self, site: str) -> RoundClusterResult:
        return RoundClusterResult(
            tick=10000,
            site_a_centroid=(-1400, -2400),
            site_b_centroid=(900, 1700),
            ct_players_in_a=3 if site == "a" else 0,
            ct_players_in_b=3 if site == "b" else 0,
            t_players_in_a=0,
            t_players_in_b=0,
            dominant_ct_site=site,
            dominant_t_site="split",
            confidence=0.8,
        )

    def test_wrong_rotate(self):
        # CT moved A → B, T hit A
        early = self._cluster("a")
        mid   = self._cluster("b")
        signal = detect_ct_rotate(early, mid, t_commit_site="a", ct_won=False)
        assert signal is not None
        assert signal.signal_type == "ct_wrong_rotate"
        assert signal.metadata["early_site"] == "a"
        assert signal.metadata["mid_site"] == "b"

    def test_correct_adapt_ct_won(self):
        # CT moved A → B, T hit B, CT won
        early = self._cluster("a")
        mid   = self._cluster("b")
        signal = detect_ct_rotate(early, mid, t_commit_site="b", ct_won=True)
        assert signal is not None
        assert signal.signal_type == "ct_correct_adapt"

    def test_no_rotation(self):
        # CT stayed at A
        early = self._cluster("a")
        mid   = self._cluster("a")
        signal = detect_ct_rotate(early, mid, t_commit_site="a", ct_won=True)
        assert signal is None

    def test_split_ct(self):
        # CT was split — not a meaningful rotation
        early_cluster = RoundClusterResult(
            tick=5000, site_a_centroid=(-1400, -2400), site_b_centroid=(900, 1700),
            ct_players_in_a=2, ct_players_in_b=2, t_players_in_a=0, t_players_in_b=0,
            dominant_ct_site="split", dominant_t_site="split", confidence=0.5,
        )
        mid_cluster = self._cluster("b")
        signal = detect_ct_rotate(early_cluster, mid_cluster, t_commit_site="a", ct_won=False)
        assert signal is None


class TestDetectTFastExecute:
    """Tests for T fast execute signal."""

    def _cluster(self, dominant_t: str, t_a: int, t_b: int) -> RoundClusterResult:
        return RoundClusterResult(
            tick=20000,
            site_a_centroid=(-1400, -2400),
            site_b_centroid=(900, 1700),
            ct_players_in_a=2,
            ct_players_in_b=2,
            t_players_in_a=t_a,
            t_players_in_b=t_b,
            dominant_t_site=dominant_t,
            dominant_ct_site="split",
            confidence=0.8,
        )

    def _grenade(self, tick: int, gtype: str) -> dict:
        return {"tick": tick, "grenade_type": gtype, "thrower_side": "t", "x": -1200, "y": -2300}

    def test_fast_execute_heavy_utility(self):
        cluster = self._cluster("a", 3, 0)
        grenades = [self._grenade(5000, "he"), self._grenade(6000, "flash"),
                    self._grenade(7000, "smoke"), self._grenade(8000, "flash"),
                    self._grenade(9000, "molotov")]
        signal = detect_t_fast_execute(grenades, cluster, round_start_tick=0, mid_round_tick=20000)
        assert signal is not None
        assert signal.signal_type == "t_fast_execute"
        assert signal.metadata["t_players"] == 3
        assert signal.metadata["grenade_count"] == 5

    def test_fast_execute_insufficient_t_players(self):
        cluster = self._cluster("a", 2, 0)
        grenades = [self._grenade(5000, "he"), self._grenade(6000, "flash"),
                    self._grenade(7000, "smoke"), self._grenade(8000, "flash"),
                    self._grenade(9000, "molotov")]
        signal = detect_t_fast_execute(grenades, cluster, round_start_tick=0, mid_round_tick=20000)
        assert signal is None

    def test_fast_execute_insufficient_utility(self):
        cluster = self._cluster("a", 3, 0)
        grenades = [self._grenade(5000, "he"), self._grenade(6000, "flash")]
        signal = detect_t_fast_execute(grenades, cluster, round_start_tick=0, mid_round_tick=20000)
        assert signal is None


class TestDetectTSplit:
    """Tests for T split signal."""

    def _cluster(self, dominant_t: str) -> RoundClusterResult:
        return RoundClusterResult(
            tick=20000, site_a_centroid=(-1400, -2400), site_b_centroid=(900, 1700),
            ct_players_in_a=2, ct_players_in_b=2,
            t_players_in_a=2, t_players_in_b=2,
            dominant_t_site=dominant_t, dominant_ct_site="split", confidence=0.8,
        )

    def _grenade(self, tick: int, x: float, y: float) -> dict:
        return {"tick": tick, "grenade_type": "he", "thrower_side": "t", "x": x, "y": y}

    def test_split_both_sites(self):
        cluster = self._cluster("split")
        grenades = [
            self._grenade(5000, -1200, -2300),   # A side
            self._grenade(6000, -1100, -2200),
            self._grenade(7000, 900, 1700),     # B side
            self._grenade(8000, 1000, 1800),
        ]
        signal = detect_t_split(cluster, grenades, round_start_tick=0)
        assert signal is not None
        assert signal.signal_type == "t_split_correct"

    def test_not_split(self):
        cluster = self._cluster("a")  # Not split
        grenades = [self._grenade(5000, -1200, -2300), self._grenade(6000, -1100, -2200)]
        signal = detect_t_split(cluster, grenades, round_start_tick=0)
        assert signal is None


class TestDetectTFake:
    """Tests for T fake signal."""

    def _cluster(self, dominant_t: str) -> RoundClusterResult:
        return RoundClusterResult(
            tick=20000, site_a_centroid=(-1400, -2400), site_b_centroid=(900, 1700),
            ct_players_in_a=2, ct_players_in_b=2,
            t_players_in_a=1, t_players_in_b=3,
            dominant_t_site=dominant_t, dominant_ct_site="split", confidence=0.8,
        )

    def _grenade(self, tick: int, x: float, gtype: str = "smoke") -> dict:
        return {"tick": tick, "grenade_type": gtype, "thrower_side": "t", "x": x, "y": -2300}

    def test_fake_a_committed_b(self):
        # Smoke at A (negative x), T committed to B (positive x)
        cluster = self._cluster("b")
        grenades = [self._grenade(5000, -1200, "smoke"), self._grenade(6000, -1150, "flash")]
        signal = detect_t_fake(grenades, cluster, round_start_tick=0)
        assert signal is not None
        assert signal.signal_type == "t_fake_detected"
        assert signal.metadata["fake_site"] == "a"
        assert signal.metadata["commit_site"] == "b"


class TestMapSiteCentroids:
    """Tests for map centroid helper."""

    def test_dust2_centroids(self):
        a, b = _map_site_centroids("dust2")
        assert a[0] < b[0]  # A is negative-X, B is positive-X

    def test_unknown_map_defaults(self):
        a, b = _map_site_centroids("unknown_map")
        assert a == (-1000, -1000)
        assert b == (1000, 1000)


class TestCloserTo:
    """Tests for site proximity helper."""

    def test_closer_to_a(self):
        frame = {"x": -1400.0, "y": -2400.0}
        a, b = (-1400, -2400), (900, 1700)
        assert _closer_to(frame, a, b) == "a"

    def test_closer_to_b(self):
        frame = {"x": 900.0, "y": 1700.0}
        a, b = (-1400, -2400), (900, 1700)
        assert _closer_to(frame, a, b) == "b"


class TestClassifyRoundTacticalSignals:
    """Integration test for full round classification."""

    def _frame(self, x: float, y: float, side: str, tick: int = 10000) -> dict:
        return {"x": x, "y": y, "z": 0.0, "side": side, "steam_id": 1, "tick": tick}

    def test_empty_inputs(self):
        signals = classify_round_tactical_signals(
            player_frames=[],
            grenade_events=[],
            round_start_tick=0,
            mid_round_tick=20000,
            round_end_tick=70000,
            map_name="dust2",
            round_number=1,
            t_committed_site="a",
            ct_won=False,
        )
        assert signals == []

    def test_no_signals_below_threshold(self):
        # Only 2 CT at site (below 4-player threshold)
        frames = [
            self._frame(-1200, -2300, "ct", tick=20000),
            self._frame(-1300, -2400, "ct", tick=20000),
        ]
        grenades = [  # Light utility
            {"tick": 5000, "grenade_type": "flash", "thrower_side": "t", "x": -1200, "y": -2300},
        ]
        signals = classify_round_tactical_signals(
            player_frames=frames,
            grenade_events=grenades,
            round_start_tick=0,
            mid_round_tick=20000,
            round_end_tick=70000,
            map_name="dust2",
            round_number=1,
            t_committed_site="a",
            ct_won=True,
        )
        assert len(signals) == 0
