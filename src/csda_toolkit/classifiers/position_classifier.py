"""Position classifier — map PlayerFrame x/y/z coordinates to named map zones.

Uses bounding boxes for each named position on each map, per side (T/CT).
The bounding boxes are approximate world-unit rectangles projected to 2D (X/Y)
from the game coordinate system.

Reference: coordinates are derived from CS2 world grid. Each map has its own
origin, but the coordinate system is consistent within each map.
"""

from dataclasses import dataclass
from typing import Optional

from csda_toolkit.classifiers.role_taxonomy import MAPS, MAP_POSITIONS, MAP_ZONES


# ── Coordinate bounding boxes per map per position ──────────────────────────────
#
# Format: { map: { position_key: { "x_min": ..., "x_max": ..., "y_min": ..., "y_max": ... } } }
# Coordinates are approximate world units from CS2. X/Y define a 2D horizontal
# bounding rectangle. Z (vertical) is not used for most positions since the
# X/Y projection is usually sufficient to distinguish areas.
#
# Maps: dust2, mirage, inferno, nuke, overpass, ancient

# NOTE: Coordinates are approximate — real calibration should use actual demo data
# from HLTV/demoparser. These are seed bounds to get classification running.
# Each classifier should log confidence and refine bounds as real data accumulates.

MAP_BOUNDS: dict[str, dict[str, dict]] = {
    "dust2": {
        # ── A Site ───────────────────────────────────────────────────────────
        "long_a": {
            "name": "Long A",
            "x_min": -1700, "x_max": -900,
            "y_min": -2800, "y_max": -2100,
        },
        "short_a": {
            "name": "Short A",
            "x_min": -3300, "x_max": -2500,
            "y_min": -2200, "y_max": -1400,
        },
        # ── Mid ──────────────────────────────────────────────────────────────
        "mid": {
            "name": "Mid",
            "x_min": -1800, "x_max": -800,
            "y_min": -1400, "y_max": -500,
        },
        # ── B Site ───────────────────────────────────────────────────────────
        "b_tunnels": {
            "name": "B Tunnels",
            "x_min": 500, "x_max": 1700,
            "y_min": 1200, "y_max": 2400,
        },
        "lower_tunnels": {
            "name": "Lower Tunnels",
            "x_min": 300, "x_max": 1600,
            "y_min": 1700, "y_max": 2800,
        },
    },

    "mirage": {
        # ── A Site ───────────────────────────────────────────────────────────
        "a_site": {
            "name": "A Site",
            "x_min": -1500, "x_max": 0,
            "y_min": -900, "y_max": 200,
        },
        "palace": {
            "name": "Palace",
            "x_min": -3200, "x_max": -1800,
            "y_min": -600, "y_max": 400,
        },
        "connector": {
            "name": "Connector",
            "x_min": -1700, "x_max": -700,
            "y_min": -600, "y_max": 0,
        },
        # ── Mid ──────────────────────────────────────────────────────────────
        "mid": {
            "name": "Mid",
            "x_min": -1700, "x_max": -400,
            "y_min": -200, "y_max": 700,
        },
        # ── B Site ───────────────────────────────────────────────────────────
        "apartments": {
            "name": "B Apartments",
            "x_min": -400, "x_max": 800,
            "y_min": 400, "y_max": 1500,
        },
        "b_site": {
            "name": "B Site",
            "x_min": 500, "x_max": 1800,
            "y_min": 800, "y_max": 1900,
        },
    },

    "inferno": {
        # ── A Site ───────────────────────────────────────────────────────────
        "a_site": {
            "name": "A Site",
            "x_min": -2200, "x_max": -1200,
            "y_min": -800, "y_max": 200,
        },
        "apartments": {
            "name": "Apartments",
            "x_min": -3500, "x_max": -2300,
            "y_min": -600, "y_max": 300,
        },
        # ── Mid ──────────────────────────────────────────────────────────────
        "mid": {
            "name": "Mid",
            "x_min": -2000, "x_max": -1000,
            "y_min": -200, "y_max": 500,
        },
        # ── B Site ───────────────────────────────────────────────────────────
        "banana": {
            "name": "Banana",
            "x_min": -600, "x_max": 600,
            "y_min": 200, "y_max": 1400,
        },
        "b_site": {
            "name": "B Site",
            "x_min": -200, "x_max": 1200,
            "y_min": 800, "y_max": 2000,
        },
    },

    "nuke": {
        # ── A Site ───────────────────────────────────────────────────────────
        "a_site_upper": {
            "name": "A Site (Upper)",
            "x_min": -700, "x_max": 700,
            "y_min": -2300, "y_max": -1400,
        },
        "ramp": {
            "name": "Ramp",
            "x_min": -1200, "x_max": -200,
            "y_min": -1500, "y_max": -600,
        },
        # ── B Site (Lower) ───────────────────────────────────────────────────
        "b_site_lower": {
            "name": "B Site (Lower)",
            "x_min": 400, "x_max": 1600,
            "y_min": -400, "y_max": 800,
        },
        "outside": {
            "name": "Outside / T Spawn",
            "x_min": -2800, "x_max": -800,
            "y_min": -2600, "y_max": -1600,
        },
        "squeaky": {
            "name": "Squeaky",
            "x_min": -900, "x_max": 100,
            "y_min": -1700, "y_max": -900,
        },
    },

    "overpass": {
        # ── A Site ───────────────────────────────────────────────────────────
        "a_site": {
            "name": "A Site",
            "x_min": -600, "x_max": 1000,
            "y_min": -2600, "y_max": -1600,
        },
        "bathrooms": {
            "name": "Bathrooms",
            "x_min": -1600, "x_max": -700,
            "y_min": -2300, "y_max": -1600,
        },
        "connector": {
            "name": "Connector",
            "x_min": -800, "x_max": 400,
            "y_min": -1700, "y_max": -900,
        },
        "monster": {
            "name": "Monster",
            "x_min": -400, "x_max": 800,
            "y_min": -1000, "y_max": -100,
        },
        # ── B Site ───────────────────────────────────────────────────────────
        "b_site": {
            "name": "B Site",
            "x_min": -400, "x_max": 1200,
            "y_min": 200, "y_max": 1400,
        },
        "water": {
            "name": "Water / Canal",
            "x_min": -1200, "x_max": 200,
            "y_min": 600, "y_max": 1800,
        },
    },

    "ancient": {
        # ── A Site ───────────────────────────────────────────────────────────
        "a_site": {
            "name": "A Site",
            "x_min": -2000, "x_max": -800,
            "y_min": -1600, "y_max": -400,
        },
        "long_a": {
            "name": "Long A",
            "x_min": -3800, "x_max": -2200,
            "y_min": -2200, "y_max": -1200,
        },
        "donut": {
            "name": "Donut",
            "x_min": -1600, "x_max": -400,
            "y_min": -600, "y_max": 400,
        },
        "cave": {
            "name": "Cave",
            "x_min": -2600, "x_max": -1600,
            "y_min": -800, "y_max": 200,
        },
        # ── B Site ───────────────────────────────────────────────────────────
        "b_ramp": {
            "name": "B Ramp",
            "x_min": 200, "x_max": 1400,
            "y_min": -600, "y_max": 600,
        },
        "b_site": {
            "name": "B Site",
            "x_min": 600, "x_max": 2200,
            "y_min": 200, "y_max": 1600,
        },
    },
}


@dataclass
class PositionClassification:
    """Classified map position for one player in one frame."""
    steam_id: int
    map_name: str
    side: str                       # "t" or "ct"
    tick: int
    position_code: str              # e.g. "long_a", "mid"
    zone: str                       # e.g. "long_a", "b_tunnels"
    x: float
    y: float
    z: float
    confidence: float = 0.0


def classify_position(
    x: float,
    y: float,
    z: float,
    map_name: str,
    side: str,
    steam_id: int = 0,
    tick: int = 0,
) -> PositionClassification:
    """Classify a player's position on a map given their x/y/z coordinates.

    Uses the closest-position bounding box match, weighted by distance to
    the box center. Returns UNKNOWN if the coordinates don't fall within
    any defined position.

    Parameters
    ----------
    x, y, z : float
        Player world coordinates from PlayerFrame
    map_name : str
        e.g. "dust2", "mirage" — must be in MAPS
    side : str
        "t" or "ct"
    steam_id : int
    tick : int

    Returns
    -------
    PositionClassification
    """
    if map_name not in MAP_BOUNDS:
        return _unknown(steam_id, map_name, side, tick, x, y, z, reason=f"unknown_map:{map_name}")

    map_bounds = MAP_BOUNDS[map_name]

    # Filter positions by side if the position definition has side-specific data
    # Otherwise use the position as-is (some positions are shared)
    candidates: list[tuple[str, dict, float]] = []

    for pos_key, bounds in map_bounds.items():
        if _in_bounds(x, y, bounds):
            # Compute distance to center for tiebreaking
            cx = (bounds["x_min"] + bounds["x_max"]) / 2
            cy = (bounds["y_min"] + bounds["y_max"]) / 2
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            candidates.append((pos_key, bounds, dist))

    if not candidates:
        return _unknown(steam_id, map_name, side, tick, x, y, z, reason="no_match")

    # Pick the closest (smallest distance to box center)
    candidates.sort(key=lambda c: c[2])
    best_key, best_bounds, best_dist = candidates[0]

    # Confidence based on how centered the player is
    box_w = best_bounds["x_max"] - best_bounds["x_min"]
    box_h = best_bounds["y_max"] - best_bounds["y_min"]
    max_dist = ((box_w / 2) ** 2 + (box_h / 2) ** 2) ** 0.5
    confidence = round(max(0.1, 1.0 - (best_dist / max_dist)), 3)

    # Zone from MAP_POSITIONS (fall back to position key)
    zone = best_key
    if map_name in MAP_POSITIONS and best_key in MAP_POSITIONS[map_name]:
        zone = MAP_POSITIONS[map_name][best_key].get("zone", best_key)

    return PositionClassification(
        steam_id=steam_id,
        map_name=map_name,
        side=side,
        tick=tick,
        position_code=best_key,
        zone=zone,
        x=x,
        y=y,
        z=z,
        confidence=confidence,
    )


def _in_bounds(x: float, y: float, bounds: dict) -> bool:
    """Check if (x, y) falls within the bounding box."""
    return (
        bounds["x_min"] <= x <= bounds["x_max"]
        and bounds["y_min"] <= y <= bounds["y_max"]
    )


def _unknown(
    steam_id: int,
    map_name: str,
    side: str,
    tick: int,
    x: float,
    y: float,
    z: float,
    reason: str = "",
) -> PositionClassification:
    return PositionClassification(
        steam_id=steam_id,
        map_name=map_name,
        side=side,
        tick=tick,
        position_code="unknown",
        zone="unknown",
        x=x,
        y=y,
        z=z,
        confidence=0.0,
    )


def classify_player_frames(
    frames: list[dict],
    map_name: str,
) -> list[PositionClassification]:
    """Classify positions for a list of PlayerFrame dicts.

    Parameters
    ----------
    frames : list of dict
        Serialized PlayerFrame dicts with keys: steam_id, x, y, z, side, tick
    map_name : str

    Returns
    -------
    list of PositionClassification
    """
    results: list[PositionClassification] = []
    for frame in frames:
        x = float(frame.get("x", 0))
        y = float(frame.get("y", 0))
        z = float(frame.get("z", 0))
        side = str(frame.get("side", "ct")).lower()
        steam_id = int(frame.get("steam_id", 0))
        tick = int(frame.get("tick", 0))

        results.append(classify_position(
            x=x, y=y, z=z,
            map_name=map_name,
            side=side,
            steam_id=steam_id,
            tick=tick,
        ))
    return results


def get_position_description(map_name: str, position_code: str) -> str:
    """Return the human-readable description for a position."""
    if map_name in MAP_POSITIONS and position_code in MAP_POSITIONS[map_name]:
        return MAP_POSITIONS[map_name][position_code].get("description", "")
    return ""
