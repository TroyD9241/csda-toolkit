"""Canonical Python domain models for CS2 demo analysis.

These are the pure domain objects (not DB models). They mirror the
csda-core domain from the Rust CSDEMOANALYZER project.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TeamSide(str, Enum):
    T = "t"
    CT = "ct"
    NONE = "none"


class DemoSource(str, Enum):
    VALVE = "valve"
    FACEIT = "faceit"
    HLTV = "hltv"
    ESEA = "esea"
    UNKNOWN = "unknown"


# ── Match-level models ──────────────────────────────────────────────────────


@dataclass
class DemoFile:
    """Ingestion provenance for a demo file."""
    demo_filename: str
    demo_checksum: str
    parser_name: str = "demoparser2"
    parser_version: str = "0.41.3"
    source: str = "unknown"
    raw_metadata: Optional[dict] = None


@dataclass
class Player:
    """A player identified by Steam ID."""
    steam_id: int
    name: str


@dataclass
class MatchTeam:
    """A team as it appeared in one match slot."""
    team_slot: int  # 1 or 2
    display_name: str
    team_id: Optional[int] = None
    lineup_id: Optional[int] = None
    starting_side: str = "unknown"
    score: Optional[int] = None
    is_winner: Optional[bool] = None
    player_ids: list[int] = field(default_factory=list)


@dataclass
class MatchContext:
    """Analytical context for a match."""
    context_provider: str = "unknown"
    play_environment: str = "unknown"
    is_structured_team_play: bool = False
    tier_estimate: Optional[int] = None
    analysis_pool: str = "low_signal"
    classification_source: str = "unknown"
    event_name: Optional[str] = None


@dataclass
class Match:
    """Canonical match object — the top-level domain entity."""
    map_name: str
    tick_rate: int
    server_name: str = ""
    source: str = "unknown"
    demo_file: Optional[DemoFile] = None
    played_at: Optional[datetime] = None
    teams: list[MatchTeam] = field(default_factory=list)
    players: list[Player] = field(default_factory=list)
    rounds: list["Round"] = field(default_factory=list)
    kills: list["Kill"] = field(default_factory=list)
    context: Optional[MatchContext] = None
    external_links: dict[str, str] = field(default_factory=dict)


# ── Round-level models ──────────────────────────────────────────────────────


@dataclass
class Round:
    """A single round within a match."""
    round_number: int
    start_tick: int
    end_tick: Optional[int] = None
    winner_side: Optional[str] = None
    end_reason: Optional[str] = None
    score_t: int = 0
    score_ct: int = 0


# ── Event models ────────────────────────────────────────────────────────────


@dataclass
class Kill:
    """A kill event."""
    round_number: int
    tick: int
    killer_steam_id: Optional[int] = None
    killer_name: str = ""
    victim_steam_id: Optional[int] = None
    victim_name: str = ""
    assister_steam_id: Optional[int] = None
    assister_name: Optional[str] = None
    weapon_name: str = ""
    is_headshot: bool = False
    is_wallbang: bool = False


@dataclass
class DamageEvent:
    """A damage event (hit)."""
    round_number: int
    tick: int
    attacker_steam_id: Optional[int] = None
    attacker_name: str = ""
    victim_steam_id: Optional[int] = None
    victim_name: str = ""
    weapon_name: str = ""
    damage: int = 0
    hit_group: Optional[str] = None
    is_headshot: bool = False


@dataclass
class BombEvent:
    """A bomb-related event (plant/defuse/explode)."""
    round_number: int
    tick: int
    event_type: str  # plant, defuse, explode
    player_steam_id: Optional[int] = None
    player_name: str = ""
    site: Optional[str] = None


@dataclass
class GrenadeEvent:
    """A grenade detonation event."""
    round_number: int
    tick: int
    thrower_steam_id: Optional[int] = None
    thrower_name: str = ""
    grenade_type: str = ""
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    position_z: Optional[float] = None


# ── Economy models ──────────────────────────────────────────────────────────


@dataclass
class PlayerEquipment:
    """A player's equipment snapshot at a point in time."""
    round_number: int
    steam_id: int
    player_name: str
    equipment_value: int
    weapons: Optional[list[str]] = None
    armor: bool = False
    helmet: bool = False
    defuse_kit: Optional[bool] = None


@dataclass
class PurchaseEvent:
    """A synthesized weapon purchase event."""
    round_number: int
    tick: int
    steam_id: int
    player_name: str
    weapon_name: str
    weapon_category: Optional[str] = None
    cost: int = 0


@dataclass
class WeaponDropEvent:
    """A weapon drop or give event."""
    round_number: int
    tick: int
    weapon_name: str
    dropped_by_steam_id: Optional[int] = None
    dropped_by_name: Optional[str] = None
    picked_up_by_steam_id: Optional[int] = None
    picked_up_by_name: Optional[str] = None


# ── Economy classification ──────────────────────────────────────────────────


class BuyType(str, Enum):
    FULL = "full"
    FORCE = "force"
    HALF = "half"
    ECO = "eco"
    UNKNOWN = "unknown"


class RoundArchetype(str, Enum):
    DEFAULT = "default"
    EXEC = "exec"
    CONTACT = "contact"
    SPLIT = "split"
    FAKE = "fake"
    LATE_HIT = "late_hit"
    RETAKESAVE = "retake"
    SAVE = "save"
    UNKNOWN = "unknown"


@dataclass
class EconomyClassification:
    """Economy classifier output for a round and side."""
    round_number: int
    team_side: str
    buy_type: BuyType = BuyType.UNKNOWN
    total_equipment_value: int = 0
    num_rifles: int = 0
    num_smgs: int = 0
    num_pistols: int = 0
    num_awps: int = 0
    confidence: float = 0.0


@dataclass
class RoleClassification:
    """Player role classifier output."""
    player_steam_id: int
    map_name: str
    side: str
    role_code: str
    confidence: float = 0.0
