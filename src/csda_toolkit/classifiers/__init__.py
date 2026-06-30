"""Versioned classifiers for tactical analytics."""

from .economy import (
    BuyType,
    classify_round_economy,
    classify_side_economy,
)
from .position_classifier import (
    MAP_BOUNDS,
    classify_player_frames,
    classify_position,
    get_position_description,
)
from .role_taxonomy import (
    BROAD_ROLES,
    MAPS,
    MAP_POSITIONS,
    MAP_ZONES,
    ROLE_DESCRIPTIONS,
    ROLE_POSITION_PREFERENCES,
    ZONE_ROLES,
    RoleClassificationResult,
)
from .tactical_signals import (
    TacticalSignal,
    classify_round_tactical_signals,
    cluster_round_positions,
)
from .role_classifier import (
    AwperProfile,
    EntryFraggerProfile,
    LurkerProfile,
    PlayerRoleSignals,
    RiflerProfile,
    SupportProfile,
    classify_player_role,
    build_player_role_signals,
    score_entry_quality,
    score_awper_quality,
    score_support_quality,
    score_rifler_quality,
    score_lurker_quality,
)

__all__ = [
    # Economy
    "BuyType",
    "classify_round_economy",
    "classify_side_economy",
    # Position
    "MAP_BOUNDS",
    "classify_position",
    "classify_player_frames",
    "get_position_description",
    # Role taxonomy
    "BROAD_ROLES",
    "MAPS",
    "MAP_POSITIONS",
    "MAP_ZONES",
    "ROLE_DESCRIPTIONS",
    "ROLE_POSITION_PREFERENCES",
    "ZONE_ROLES",
    "RoleClassificationResult",
    # Tactical signals
    "TacticalSignal",
    "classify_round_tactical_signals",
    "cluster_round_positions",
    # Role classifier
    "AwperProfile",
    "EntryFraggerProfile",
    "LurkerProfile",
    "PlayerRoleSignals",
    "RiflerProfile",
    "SupportProfile",
    "classify_player_role",
    "build_player_role_signals",
    "score_entry_quality",
    "score_awper_quality",
    "score_support_quality",
    "score_rifler_quality",
    "score_lurker_quality",
]
