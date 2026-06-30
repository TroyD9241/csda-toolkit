"""Grenade trajectory downsampling utilities.

Reduces per-tick trajectory points to a compact representation
(~12 key points) while preserving throw + detonation + mid-flight
shape for flash proximity, blind estimation, and utility analysis.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any


@dataclass
class TrajectoryPoint:
    tick: int
    x: float
    y: float
    z: float


def downsample_trajectory(
    points: list[TrajectoryPoint],
    max_points: int = 12,
    keep_first: int = 6,
    keep_last: int = 6,
) -> list[dict]:
    """Downsamples a trajectory while preserving start, end, and shape.

    Strategy: keep first N points (throw), evenly sample the middle, keep
    last N points (detonation). Removes duplicate positions.
    """
    if not points:
        return []
    n = len(points)
    if n <= max_points:
        return [
            {"tick": p.tick, "x": round(p.x, 2), "y": round(p.y, 2), "z": round(p.z, 2)}
            for p in points
        ]

    result: list[dict] = []
    # 1. Start (throw) — full resolution
    for i in range(min(keep_first, n)):
        p = points[i]
        result.append({"tick": p.tick, "x": round(p.x, 2), "y": round(p.y, 2), "z": round(p.z, 2)})

    # 2. Middle — evenly spaced
    middle_start = keep_first
    middle_end = n - keep_last
    middle_n = max_points - keep_first - keep_last
    if middle_end > middle_start and middle_n > 0:
        step = max(1, (middle_end - middle_start) // middle_n)
        for i in range(middle_start, middle_end, step):
            p = points[i]
            result.append({"tick": p.tick, "x": round(p.x, 2), "y": round(p.y, 2), "z": round(p.z, 2)})

    # 3. End (detonation) — full resolution
    for i in range(max(middle_end, n - keep_last), n):
        p = points[i]
        result.append({"tick": p.tick, "x": round(p.x, 2), "y": round(p.y, 2), "z": round(p.z, 2)})

    # Dedupe by (tick, x, y)
    seen: set = set()
    unique: list[dict] = []
    for p in result:
        key = (p["tick"], p["x"], p["y"])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def compact_trajectory(
    raw_points: list[dict],
    grenade_type: str = "",
    resolution: int | None = None,
) -> dict:
    """Take raw per-tick trajectory and return a compact summary dict.

    Args:
        raw_points: list of {"tick", "x", "y", "z"} from demoparser
        grenade_type: used to choose resolution (flashbangs get higher res)
        resolution: override max_points

    Returns dict ready for DB insert.
    """
    if not raw_points:
        return {}

    # Flashbangs need higher resolution for accurate blind estimation
    if resolution is None:
        if "flash" in grenade_type.lower():
            resolution = 20  # more points for flashbangs
        else:
            resolution = 12  # aggressive for smokes/mollies

    points = [TrajectoryPoint(p["tick"], p["x"], p["y"], p["z"]) for p in raw_points]
    downsampled = downsample_trajectory(points, max_points=resolution)

    # Compute metadata
    throw_tick = raw_points[0]["tick"]
    detonate_tick = raw_points[-1]["tick"]
    duration_ticks = detonate_tick - throw_tick

    # Throw position
    throw_pos = raw_points[0]

    # Detonate (last) position
    det_pos = raw_points[-1]

    # Max distance from thrower
    tx, ty = throw_pos["x"], throw_pos["y"]
    max_dist = 0.0
    for p in raw_points:
        d = math.sqrt((p["x"] - tx) ** 2 + (p["y"] - ty) ** 2)
        if d > max_dist:
            max_dist = d

    return {
        "throw_tick": throw_tick,
        "detonate_tick": detonate_tick,
        "duration_ticks": duration_ticks,
        "throw_pos_x": round(throw_pos["x"], 2),
        "throw_pos_y": round(throw_pos["y"], 2),
        "throw_pos_z": round(throw_pos["z"], 2),
        "detonate_pos_x": round(det_pos["x"], 2),
        "detonate_pos_y": round(det_pos["y"], 2),
        "detonate_pos_z": round(det_pos["z"], 2),
        "max_distance": round(max_dist, 2),
        "trajectory_points": json.dumps(downsampled),
    }


def estimate_blinded_players(
    flash: dict,
    players_at_tick: list[dict],
    flash_radius: float = 800.0,
) -> list[dict]:
    """Estimate who got blinded using detonation position + proximity."""
    det_x, det_y = flash["detonate_pos_x"], flash["detonate_pos_y"]
    blinded = []
    for player in players_at_tick:
        if player.get("steamid") == flash.get("thrower_steamid"):
            continue
        dist = math.sqrt(
            (player["x"] - det_x) ** 2 + (player["y"] - det_y) ** 2
        )
        if dist < flash_radius:
            blinded.append({
                "steamid": player.get("steamid"),
                "distance": round(dist, 1),
                "estimated_duration": max(0.5, 7.0 - dist / 200),
            })
    return blinded
