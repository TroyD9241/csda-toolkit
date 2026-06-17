"""CS2 Player Role & Map Position Taxonomy.

This module is the single source of truth for all role classifications used
by the csda-toolkit classifier pipeline.

IMPORTANT: All performance metrics (win rates, success rates, etc.) are
COMPUTED from real match data — never assigned as arbitrary or assumed values.
Reference benchmarks from professional tier-1 data (HLTV, Liquipedia, etc.)
are used ONLY as classification thresholds/cutoffs for labeling buy types and
round outcomes. Real sample data always supersedes reference benchmarks.

TAXONOMY HIERARCHY (3 levels)
==============================
Level 1 — Broad Role:   High-level tactical identity (Entry, AWPer, IGL, etc.)
Level 2 — Map:           Which map the position is on (dust2, mirage, inferno, etc.)
Level 3 — Position:     Named location on that map for a given side (Long_A, Mid, etc.)

For example:
    broad_role = "entry"           # Level 1
    map_name   = "dust2"           # Level 2
    position   = "long_a"          # Level 3
    side       = "t"               # t or ct (which team)

CLASSIFICATION SCHEMA (stored in classifications table)
=======================================================
entity_type:  "player"
entity_id:    match_player_id or player_id
label_name:   one of the label axes below
label_value:  one of the valid values for that axis

LABEL AXES
==========
role_broad        — Level 1 broad role (e.g. "entry", "awper", "igl")
role_map_{name}   — Map-specific position on map {name} (e.g. "role_map_mirage", "role_map_dust2")
role_zone         — Zone classification (e.g. "a_anchor", "b_anchor", "mid_control", "flanker")
role_secondary    — Secondary role modifier (e.g. "second_awper", "trade_fragger")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Broad Roles (Level 1) ────────────────────────────────────────────────────

BROAD_ROLES: tuple[str, ...] = (
    "entry",       # First into site, opens space for team
    "igl",         # Calls strategies, reads enemy, leads team
    "rifler",      # Core fragger, AK/M4, flexible and adaptive
    "awper",       # Sniper, controls long sightlines and key angles
    "lurker",      # Solo flanking, catches rotations, surprise pressure
    "support",     # Utility support, flashes, smokes for teammates
    "anchor",      # CT-side, holds site alone, delays pushes
    "rotator",     # CT-side, fast rotations between sites
    "second_awper", # Secondary AWPer, picks up AWP when primary can't
    "second_caller", # Extra caller, supports IGL with info and calls
    "trade_fragger", # Follows entry, secures trades to make it 1-for-1
    "second_support", # Extra support, throws utility, helps control map
)

ROLE_DESCRIPTIONS: dict[str, str] = {
    "entry":        "First into bomb site, finds early fights, opens space for team.",
    "igl":          "Calls strategies, reads enemy, makes in-round decisions.",
    "rifler":       "Core fragger using AK/M4; adapts to tasks, holds angles, pushes, trades.",
    "awper":        "Uses AWP to control long sightlines and get high-impact kills.",
    "lurker":       "Moves away from group, flanks or gathers info, punishes rotations.",
    "support":      "Uses grenades to help teammates, plays safely, executes plans.",
    "anchor":       "CT-side: holds a bomb site alone, strong defensive position.",
    "rotator":      "CT-side: moves fast between sites depending on enemy pressure.",
    "second_awper": "Picks up AWP when primary AWPer can't; holds long-range areas.",
    "second_caller":"Provides extra info and ideas during rounds; supports IGL.",
    "trade_fragger":"Follows entry fragger; gets kill if entry dies — even trade.",
    "second_support":"Throws extra utility; helps control map tempo.",
}


# ── Map Names (valid map identifiers) ───────────────────────────────────────

MAPS: tuple[str, ...] = (
    "dust2",
    "mirage",
    "inferno",
    "nuke",
    "overpass",
    "ancient",
)


# ── Map Zones (groups of related positions) ──────────────────────────────────

MAP_ZONES: dict[str, list[str]] = {
    "dust2":   ["long_a", "short_a", "mid", "b_tunnels", "lower_tunnels"],
    "mirage":  ["a_site", "palace", "mid", "connector", "apartments", "b_site"],
    "inferno": ["a_site", "apartments", "mid", "banana", "b_site"],
    "nuke":    ["a_site_upper", "ramp", "b_site_lower", "outside", "squeaky"],
    "overpass":["a_site", "connector", "monster", "bathrooms", "b_site", "water"],
    "ancient": ["a_site", "long_a", "donut", "cave", "b_site", "b_ramp"],
}


# ── Map Positions (Level 3) ───────────────────────────────────────────────────
# Format: { map_name: { position_code: { "name": ..., "zone": ..., "description": ..., "ct_side": {...}, "t_side": {...} } } }

MAP_POSITIONS: dict[str, dict[str, dict]] = {
    "dust2": {
        # ── A Site ──────────────────────────────────────────────────────────
        "long_a": {
            "name": "Long A",
            "zone": "long_a",
            "description": "Main corridor from T spawn to A bombsite",
            "ct_positions": ["pit", "a_ramp", "site"],
            "t_positions": ["long_doors", "long", "a_site"],
        },
        "short_a": {
            "name": "Short A (Catwalk)",
            "zone": "short_a",
            "description": "Fast A access via elevated catwalk",
            "ct_positions": ["stairs", "ct_spawn", "short"],
            "t_positions": ["catwalk", "a_site", "upper_short"],
        },
        # ── Mid ──────────────────────────────────────────────────────────────
        "mid": {
            "name": "Mid",
            "zone": "mid",
            "description": "Central control area connecting both bombsites",
            "ct_positions": ["ct_mid", "b_doors", "xbox"],
            "t_positions": ["top_mid", "mid_doors", "lower_tunnels", "suicide"],
        },
        # ── B Site ──────────────────────────────────────────────────────────
        "b_tunnels": {
            "name": "B Tunnels",
            "zone": "b_tunnels",
            "description": "Main B approach through tunnels",
            "ct_positions": ["window", "b_doors", "tunnels"],
            "t_positions": ["upper_tunnels", "lower_tunnels", "b_tunnels"],
        },
        "lower_tunnels": {
            "name": "Lower Tunnels",
            "zone": "lower_tunnels",
            "description": "Alternative underground B route",
            "ct_positions": ["lower_tunnels"],
            "t_positions": ["lower_tunnels", "mid"],
        },
    },

    "mirage": {
        # ── A Site ──────────────────────────────────────────────────────────
        "a_site": {
            "name": "A Site",
            "zone": "a_site",
            "description": "A bombsite area, open with multiple angles",
            "ct_positions": ["ramp", "jungle", "ticket_booth", "ct_spawn", "ninja"],
            "t_positions": ["a_ramp", "a_site", "default", "ninja"],
        },
        "palace": {
            "name": "Palace",
            "zone": "palace",
            "description": "Upper A entrance through palace building",
            "ct_positions": ["under_palace", "site"],
            "t_positions": ["a_palace", "under_palace", "jungle"],
        },
        "connector": {
            "name": "Connector (Stairs)",
            "zone": "connector",
            "description": "Mid-to-A staircase connection",
            "ct_positions": ["connector", "tetris", "sandwich"],
            "t_positions": ["top_connector", "a_ramp"],
        },
        # ── Mid ──────────────────────────────────────────────────────────────
        "mid": {
            "name": "Mid",
            "zone": "mid",
            "description": "Central area controlling access to both sites",
            "ct_positions": ["mid_window", "ladder_room", "catwalk"],
            "t_positions": ["top_mid", "catwalk", "short", "underpass"],
        },
        # ── B Site ──────────────────────────────────────────────────────────
        "apartments": {
            "name": "B Apartments (Apps)",
            "zone": "apartments",
            "description": "Main B approach through apartment building",
            "ct_positions": ["kitchen", "bench", "b_short"],
            "t_positions": ["t_apps", "underpass", "kitchen", "b_short"],
        },
        "b_site": {
            "name": "B Site",
            "zone": "b_site",
            "description": "B bombsite with van and stacked boxes",
            "ct_positions": ["van", "b_boxes", "back_site", "market"],
            "t_positions": ["b_site", "van", "back_site", "market"],
        },
    },

    "inferno": {
        # ── A Site ──────────────────────────────────────────────────────────
        "a_site": {
            "name": "A Site",
            "zone": "a_site",
            "description": "A bombsite with truck and sunken pit",
            "ct_positions": ["pit", "arch", "library", "porch", "graveyard", "truck"],
            "t_positions": ["a_site", "truck", "pit", "graveyard"],
        },
        "apartments": {
            "name": "Apartments (Apps)",
            "zone": "apartments",
            "description": "Building approach to A site",
            "ct_positions": ["boiler", "balcony", "dark"],
            "t_positions": ["apartments", "boiler", "balcony", "a_site"],
        },
        # ── Mid ──────────────────────────────────────────────────────────────
        "mid": {
            "name": "Mid",
            "zone": "mid",
            "description": "Central area linking both bombsites",
            "ct_positions": ["top_mid", "bottom_mid", "arch", "ruins"],
            "t_positions": ["top_mid", "t_stairs", "arch", "ruins"],
        },
        # ── B Site ──────────────────────────────────────────────────────────
        "banana": {
            "name": "Banana",
            "zone": "banana",
            "description": "Main B approach, narrow chokepoint",
            "ct_positions": ["logs", "sandbags", "car", "ct_spawn"],
            "t_positions": ["top_banana", "banana", "sandbags"],
        },
        "b_site": {
            "name": "B Site",
            "zone": "b_site",
            "description": "Small enclosed B bombsite",
            "ct_positions": ["fountain", "new_box", "old_box", "dark", "coffins"],
            "t_positions": ["b_site", "fountain", "back_site"],
        },
    },

    "nuke": {
        # ── A Site (Upper) ─────────────────────────────────────────────────
        "a_site_upper": {
            "name": "A Site (Upper)",
            "zone": "a_site_upper",
            "description": "Upper floor bombsite in the nuclear facility",
            "ct_positions": ["heaven", "hell", "boxes", "truck", "ct_red"],
            "t_positions": ["a_site", "heaven", "truck", "main"],
        },
        "ramp": {
            "name": "Ramp",
            "zone": "ramp",
            "description": "Central connection between upper and lower floors",
            "ct_positions": ["upper_ramp", "lower_ramp", "blue", "radio"],
            "t_positions": ["ramp", "upper_ramp", "big_garage"],
        },
        # ── B Site (Lower) ─────────────────────────────────────────────────
        "b_site_lower": {
            "name": "B Site (Lower)",
            "zone": "b_site_lower",
            "description": "Underground B bombsite",
            "ct_positions": ["headshot", "dark", "closet", "back_site", "toxic"],
            "t_positions": ["b_site", "secret", "back_site", "toxic"],
        },
        "outside": {
            "name": "Outside",
            "zone": "outside",
            "description": "Outdoor T control area critical for map access",
            "ct_positions": ["silo", "hut", "squeaky"],
            "t_positions": ["outside", "silo", "hut", "squeaky"],
        },
        "squeaky": {
            "name": "Squeaky",
            "zone": "squeaky",
            "description": "Red door to A — loud and telegraphs A pressure",
            "ct_positions": ["squeaky"],
            "t_positions": ["squeaky", "lobby"],
        },
    },

    "overpass": {
        # ── A Site ──────────────────────────────────────────────────────────
        "a_site": {
            "name": "A Site",
            "zone": "a_site",
            "description": "Multi-level A bombsite with elevated bank",
            "ct_positions": ["bank", "heaven", "truck", "barrels", "long_a"],
            "t_positions": ["a_site", "long_a", "heaven", "truck"],
        },
        "bathrooms": {
            "name": "Bathrooms",
            "zone": "bathrooms",
            "description": "Small room near A — critical control point",
            "ct_positions": ["bathrooms", "trash_can"],
            "t_positions": ["bathrooms", "a_site"],
        },
        # ── Connector ───────────────────────────────────────────────────────
        "connector": {
            "name": "Connector",
            "zone": "connector",
            "description": "Central hub connecting both sites",
            "ct_positions": ["monster", "short", "heaven"],
            "t_positions": ["connector", "monster", "party", "playground"],
        },
        "monster": {
            "name": "Monster",
            "zone": "monster",
            "description": "Under-bridge area — key strategic position",
            "ct_positions": ["monster"],
            "t_positions": ["monster", "party", "playground"],
        },
        # ── B Site ──────────────────────────────────────────────────────────
        "b_site": {
            "name": "B Site",
            "zone": "b_site",
            "description": "Multi-level B bombsite with heaven balcony",
            "ct_positions": ["b_heaven", "pillar", "toxic", "dumpster", "back_site"],
            "t_positions": ["b_site", "b_heaven", "pillar", "back_site", "water"],
        },
        "water": {
            "name": "Water (Canal)",
            "zone": "water",
            "description": "Lower passage to B — unusual angle",
            "ct_positions": ["water"],
            "t_positions": ["water", "tunnel", "boost", "b_site"],
        },
    },

    "ancient": {
        # ── A Site ──────────────────────────────────────────────────────────
        "a_site": {
            "name": "A Site",
            "zone": "a_site",
            "description": "Open A bombsite with temple structure",
            "ct_positions": ["temple", "ramp", "heaven", "jungle", "elbow"],
            "t_positions": ["a_site", "ramp", "heaven", "jungle"],
        },
        "long_a": {
            "name": "Long A",
            "zone": "long_a",
            "description": "Long corridor to A site with open sightlines",
            "ct_positions": ["long_a", "cave", "cubby"],
            "t_positions": ["long_a", "cave", "cubby", "a_site"],
        },
        # ── Mid / Donut ─────────────────────────────────────────────────────
        "donut": {
            "name": "Donut",
            "zone": "donut",
            "description": "Central circular structure — key to the entire map",
            "ct_positions": ["donut", "top_mid", "pillar", "red"],
            "t_positions": ["donut", "top_mid", "lane", "window"],
        },
        "cave": {
            "name": "Cave",
            "zone": "cave",
            "description": "Underground passage providing fast A access",
            "ct_positions": ["cave"],
            "t_positions": ["cave", "a_site"],
        },
        # ── B Site ──────────────────────────────────────────────────────────
        "b_ramp": {
            "name": "B Ramp",
            "zone": "b_ramp",
            "description": "Main ramped B approach",
            "ct_positions": ["b_ramp", "headshot", "cat"],
            "t_positions": ["b_ramp", "headshot", "cat"],
        },
        "b_site": {
            "name": "B Site",
            "zone": "b_site",
            "description": "Enclosed B bombsite with multiple angles",
            "ct_positions": ["b_site", "back_site", "boxes", "default", "window"],
            "t_positions": ["b_site", "back_site", "alley", "cat", "window"],
        },
    },
}


# ── Role-to-Position Heuristics ──────────────────────────────────────────────
# These map broad roles → typical positions/zones on each map.
# Used as seed rules for the classifier before it learns from data.

ROLE_POSITION_PREFERENCES: dict[str, dict[str, list[str]]] = {
    # Broad role → { map: [preferred positions] }
    "entry": {
        "dust2":   ["short_a", "b_tunnels", "mid"],
        "mirage":  ["apartments", "palace", "short"],
        "inferno": ["apartments", "banana"],
        "nuke":    ["outside", "squeaky"],
        "overpass":["bathrooms", "water", "short"],
        "ancient": ["long_a", "b_ramp", "donut"],
    },
    "igl": {
        "dust2":   ["mid", "short_a"],
        "mirage":  ["mid", "connector"],
        "inferno": ["mid", "a_site"],
        "nuke":    ["outside", "ramp"],
        "overpass":["connector", "mid"],
        "ancient": ["donut", "mid"],
    },
    "awper": {
        "dust2":   ["long_a", "mid", "b_tunnels"],
        "mirage":  ["mid", "long_a", "a_site"],
        "inferno": ["banana", "a_site"],
        "nuke":    ["outside", "a_site_upper"],
        "overpass":["a_site", "mid", "connector"],
        "ancient": ["long_a", "donut", "b_ramp"],
    },
    "lurker": {
        "dust2":   ["mid", "lower_tunnels", "long_a"],
        "mirage":  ["mid", "underpass", "b_site"],
        "inferno": ["mid", "apartments"],
        "nuke":    ["outside", "b_site_lower"],
        "overpass":["water", "monster", "b_site"],
        "ancient": ["cave", "donut", "b_site"],
    },
    "support": {
        "dust2":   ["mid", "short_a", "long_a"],
        "mirage":  ["mid", "connector", "apartments"],
        "inferno": ["mid", "banana", "apartments"],
        "nuke":    ["ramp", "a_site_upper"],
        "overpass":["connector", "monster", "a_site"],
        "ancient": ["donut", "long_a", "b_ramp"],
    },
    "anchor": {
        "dust2":   ["long_a", "b_tunnels"],
        "mirage":  ["a_site", "b_site"],
        "inferno": ["a_site", "b_site"],
        "nuke":    ["a_site_upper", "b_site_lower"],
        "overpass":["a_site", "b_site"],
        "ancient": ["a_site", "b_site"],
    },
    "rotator": {
        "dust2":   ["mid", "short_a"],
        "mirage":  ["mid", "connector"],
        "inferno": ["mid"],
        "nuke":    ["ramp"],
        "overpass":["connector", "monster"],
        "ancient": ["donut"],
    },
}


# ── Zone Classifications ──────────────────────────────────────────────────────
# Zone = tactical grouping across all maps (A anchor, B anchor, Mid control, Flanker, etc.)

ZONE_ROLES: dict[str, str] = {
    # Zone code → tactical description
    "a_anchor":    "Holds A bomb site as last line of defense",
    "b_anchor":    "Holds B bomb site as last line of defense",
    "mid_control": "Controls mid area to influence both bombsites",
    "flanker":     "Separates from team to apply unexpected pressure",
    "entry":       "First contact on attack, opens space",
    "lurker":      "Solo operator catching rotations or gathering info",
    "sniper_lane": "Controls a long sightline or critical chokepoint",
    "site_watch":  "Holds a specific bombsite from a distance or angle",
}


# ── Dataclass for structured role output ─────────────────────────────────────

@dataclass
class RoleClassificationResult:
    """Structured result from role classification.

    Note: confidence is a classifier quality signal (how certain the model is),
    NOT a performance metric. Performance metrics (win rates, success rates) are
    computed separately from real match data and stored in the classifications
    table with their own label axes — they are never assumed or hardcoded."""
    steam_id: int
    map_name: str
    side: str                        # "t" or "ct"
    broad_role: str                   # e.g. "entry", "awper", "igl"
    map_position: str                # e.g. "long_a", "mid", "banana"
    zone_role: str                   # e.g. "a_anchor", "mid_control"
    secondary_role: Optional[str] = None  # e.g. "second_awper", "trade_fragger"
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_classifications(self) -> list[dict]:
        """Convert to list of Classification-ready dicts for the DB."""
        return [
            {
                "entity_type": "player",
                "entity_id": self.steam_id,
                "label_name": "role_broad",
                "label_value": self.broad_role,
                "confidence": self.confidence,
            },
            {
                "entity_type": "player",
                "entity_id": self.steam_id,
                "label_name": f"role_map_{self.map_name}",
                "label_value": self.map_position,
                "confidence": self.confidence,
            },
            {
                "entity_type": "player",
                "entity_id": self.steam_id,
                "label_name": "role_zone",
                "label_value": self.zone_role,
                "confidence": self.confidence,
            },
        ] + (
            [
                {
                    "entity_type": "player",
                    "entity_id": self.steam_id,
                    "label_name": "role_secondary",
                    "label_value": self.secondary_role,
                    "confidence": self.confidence,
                },
            ]
            if self.secondary_role
            else []
        )
