"""Canonical Python domain models for CS2 demo analysis.

Pure domain objects (not DB models). Covers all event types, tick snapshots,
and economy state that demoparser2 can extract.
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


# ── Event-level models ────────────────────────────────────────────────────


@dataclass
class Event:
    """A tournament or event containing series (e.g. BLAST Rivals 2026)."""
    name: str
    slug: str = ""
    tier: int = 0               # 1=tier1, 2=tier2, 3=tier3, 0=unknown
    region: str = ""
    source: str = "unknown"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    id: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class EventSeries:
    """A best-of series within an event (BO1, BO3, BO5).

    Links two teams across multiple maps in a single series.
    """
    event_id: int
    series_type: str = ""       # "bo1", "bo3", "bo5"
    round_name: str = ""        # "quarterfinal", "semifinal", "grand_final"
    team_a_id: int = 0
    team_b_id: int = 0
    team_a_name: str = ""
    team_b_name: str = ""
    team_a_score: int = 0
    team_b_score: int = 0
    map_veto_json: str = ""     # veto order as JSON string
    source: str = "unknown"
    id: int = 0


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
    event_id: int = 0


@dataclass
class TeamFrame:
    """Team-level state at a tick."""
    team_num: int
    team_name: str
    clan_name: str = ""
    score: int = 0
    score_first_half: int = 0
    score_second_half: int = 0
    score_overtime: int = 0
    num_map_victories: int = 0
    surrendered: bool = False
    player_steam_ids: list[int] = field(default_factory=list)


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
    series_id: int = 0
    map_number: int = 0     # 1-based index within series


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
    freeze_end_tick: Optional[int] = None


# ── Round event models ──────────────────────────────────────────────────────


@dataclass
class RoundEndReason:
    """Parsed round_end event."""
    tick: int
    winner_side: str
    reason_code: int
    reason_name: str
    message: str = ""
    player_count: int = 0
    total_rounds_played: int = 0


@dataclass
class RoundMvp:
    """Parsed round_mvp event."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""
    reason: int = 0
    value: int = 0
    musickit_id: int = 0


@dataclass
class WinPanelRound:
    """Parsed cs_win_panel_round event."""
    tick: int
    final_event: int = 0
    funfact_token: str = ""
    funfact_player: int = 0
    funfact_data1: int = 0
    funfact_data2: int = 0
    funfact_data3: int = 0
    show_timer_attack: bool = False
    show_timer_defend: bool = False
    timer_time: int = 0


@dataclass
class MatchPanel:
    """Parsed cs_win_panel_match event."""
    tick: int


# ── Player event models ─────────────────────────────────────────────────────


@dataclass
class Kill:
    """A kill event — 34 fields from player_death."""
    tick: int
    round_number: int = 0
    killer_steam_id: Optional[int] = None
    killer_name: str = ""
    killer_team: str = ""
    killer_last_place_name: str = ""
    victim_steam_id: Optional[int] = None
    victim_name: str = ""
    victim_team: str = ""
    victim_last_place_name: str = ""
    assister_steam_id: Optional[int] = None
    assister_name: str = ""
    assister_team: str = ""
    assister_last_place_name: str = ""
    weapon: str = ""
    weapon_item_id: str = ""
    weapon_faux_item_id: str = ""
    weapon_original_owner_xuid: str = ""
    headshot: bool = False
    penetrated: int = 0
    thrusmoke: bool = False
    attackerblind: bool = False
    attackerinair: bool = False
    noscope: bool = False
    assistedflash: bool = False
    dominated: bool = False
    revenge: bool = False
    wipe: bool = False
    distance: Optional[float] = None
    dmg_health: int = 0
    dmg_armor: int = 0
    hitgroup: int = -1
    hitgroup_name: str = "unknown"


@dataclass
class DamageEvent:
    """A damage event (player_hurt).

    The last_place_name fields come from CS2's internal map zone labels.
    Values like 'Long A', 'BombsiteA', 'Mid', 'T Spawn', 'CT Spawn' etc.
    are provided directly by the game engine — no bounding-box inference needed.
    """
    tick: int
    round_number: int = 0
    attacker_steam_id: Optional[int] = None
    attacker_name: str = ""
    victim_steam_id: Optional[int] = None
    victim_name: str = ""
    weapon: str = ""
    dmg_health: int = 0
    dmg_armor: int = 0
    hitgroup: int = -1
    health: int = 0
    armor: int = 0
    hitgroup_name: str = "unknown"
    attacker_last_place_name: str = ""
    victim_last_place_name: str = ""


@dataclass
class PlayerBlind:
    """A player_blind (flashbang) event."""
    tick: int
    attacker_steam_id: Optional[int] = None
    attacker_name: str = ""
    victim_steam_id: Optional[int] = None
    victim_name: str = ""
    blind_duration: float = 0.0


@dataclass
class PlayerSpawn:
    """A player_spawn event."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""


@dataclass
class PlayerBulletHit:
    """A player_bullet_hit event (where bullets land, even missed shots)."""
    tick: int
    shooter_steam_id: Optional[int] = None
    shooter_name: str = ""
    target_entity_id: Optional[int] = None
    penetrating_count: int = 0


@dataclass
class ChatMessage:
    """A player_chat / say / say_team event."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""
    message: str = ""
    team_only: bool = False


@dataclass
class PlayerPing:
    """A player_ping / player_ping_world event (map ping)."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""
    is_world_ping: bool = False


@dataclass
class BuyTimeEvent:
    """A buytime_ended / enter_buytime / exit_buytime event."""
    tick: int
    event_type: str  # "buytime_ended" | "enter_buytime" | "exit_buytime"


@dataclass
class PlayerJump:
    """A player_jump event."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""


@dataclass
class FlashAssist:
    """A flash assist (someone was blinded by your flash)."""
    tick: int
    attacker_steam_id: Optional[int] = None
    attacker_name: str = ""
    victim_steam_id: Optional[int] = None
    victim_name: str = ""
    flash_duration: float = 0.0


@dataclass
class FootstepEvent:
    """A player_footstep event."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""


@dataclass
class OtherDeath:
    """An other_death event (entity death, not a player)."""
    tick: int
    attacker_steam_id: Optional[int] = None
    attacker_name: str = ""
    attackerblind: bool = False
    headshot: bool = False
    noscope: bool = False
    penetrated: int = 0
    thrusmoke: bool = False
    weapon: str = ""
    othertype: str = ""


# ── Weapon event models ─────────────────────────────────────────────────────


@dataclass
class WeaponFire:
    """A weapon_fire event."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""
    weapon: str = ""
    silenced: bool = False


@dataclass
class WeaponReload:
    """A weapon_reload event."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""


@dataclass
class WeaponZoom:
    """A weapon_zoom event."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""


@dataclass
class ItemEquip:
    """An item_equip event (player equips a weapon)."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""
    defindex: int = 0
    item: str = ""
    canzoom: bool = False
    hassilencer: bool = False
    issilenced: bool = False
    ispainted: bool = False
    hastracers: bool = False
    weptype: str = ""


@dataclass
class ItemPickup:
    """An item_pickup event (player picks up weapon)."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""
    item: str = ""
    defindex: int = 0
    silent: bool = False


# ── Bomb event models ───────────────────────────────────────────────────────


@dataclass
class BombEvent:
    """A bomb-related event."""
    tick: int
    event_type: str  # planted, begin_plant, defused, begin_defuse, exploded, dropped, pickup
    player_steam_id: Optional[int] = None
    player_name: str = ""
    site: Optional[str] = None
    has_kit: Optional[bool] = None


# ── Grenade event models ────────────────────────────────────────────────────


@dataclass
class GrenadeDetonation:
    """A grenade detonation event (he, flash, smoke)."""
    tick: int
    grenade_type: str  # hegrenade, flashbang, smoke, smoke_expired
    player_steam_id: Optional[int] = None
    player_name: str = ""
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None


@dataclass
class InfernoEvent:
    """An inferno (molotov/incendiary) start/expire event."""
    tick: int
    event_type: str  # start_burn, expire
    player_steam_id: Optional[int] = None
    player_name: str = ""
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None


# ── Tick-marker events (no extra data beyond event type + tick) ──────────────


@dataclass
class TickEvent:
    """A tick-marker — something happened at this tick, no other data.

    Used for: begin_new_match, buytime_ended, cs_pre_restart, cs_round_final_beep,
    cs_round_start_beep, round_announce_match_start, round_officially_ended,
    round_poststart, round_prestart, round_time_warning.
    """
    event_type: str
    tick: int


@dataclass
class RoundStartEvent:
    """Parsed round_start event — has extra fields beyond tick."""
    tick: int
    frag_limit: int = 0
    objective: str = ""
    time_limit: int = 0


@dataclass
class HltvVersionInfo:
    """Parsed hltv_versioninfo event."""
    tick: int
    version: int = 0


# ── Rank / progression models ───────────────────────────────────────────────


@dataclass
class RankUpdate:
    """A rank_update event."""
    tick: int
    player_steam_id: Optional[int] = None
    player_name: str = ""
    rank_old: int = 0
    rank_new: int = 0
    rank_change: int = 0
    num_wins: int = 0
    rank_type_id: int = 0


# ── Economy models ─────────────────────────────────────────────────────────


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
    freezetime_end_value: Optional[int] = None
    round_start_value: Optional[int] = None


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


# ── Tick snapshot models ────────────────────────────────────────────────────


@dataclass
class PlayerFrame:
    """Complete per-player state snapshot at a single tick.

    Extracted from CCSPlayerController + CCSPlayerPawn fields.
    """
    tick: int
    steam_id: int
    name: str = ""
    # Controller-level
    team_num: int = 0
    is_alive: bool = False
    health: int = 0
    armor: int = 0
    has_defuser: bool = False
    has_helmet: bool = False
    score: int = 0
    mvps: int = 0
    ping: int = 0
    competitive_ranking: int = 0
    competitive_wins: int = 0
    clan: str = ""
    # Pawn-level (positional)
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    eye_angle_x: float = 0.0
    eye_angle_y: float = 0.0
    eye_angle_z: float = 0.0
    # State
    is_scoped: bool = False
    is_walking: bool = False
    is_defusing: bool = False
    in_buy_zone: bool = False
    in_bomb_zone: bool = False
    shots_fired: int = 0
    flash_duration: float = 0.0
    # Movement
    velocity_modifier: float = 1.0
    duck_amount: float = 0.0
    # Equipment values
    current_equip_value: int = 0
    freezetime_end_equip_value: int = 0
    round_start_equip_value: int = 0


@dataclass
class PlayerRoundStats:
    """Per-player cumulative stats at a tick (from ActionTrackingServices)."""
    tick: int
    steam_id: int
    round_number: int = 0
    kills: int = 0
    assists: int = 0
    deaths: int = 0
    damage: int = 0
    headshot_kills: int = 0
    cash_earned: int = 0
    equipment_value: int = 0
    utility_damage: int = 0
    enemies_flashed: int = 0


@dataclass
class PlayerMoney:
    """Per-player money state (from InGameMoneyServices)."""
    tick: int
    steam_id: int
    account: int = 0
    start_account: int = 0
    cash_spent_this_round: int = 0
    total_cash_spent: int = 0


@dataclass
class GameRulesFrame:
    """CS2 game rules state at a tick."""
    tick: int
    total_rounds_played: int = 0
    round_in_progress: bool = False
    freezetime: bool = False
    bomb_planted: bool = False
    bomb_dropped: bool = False
    match_started: bool = False
    warmup: bool = False
    round_win_status: int = 0
    round_win_reason: int = 0
    ct_cant_buy: bool = False
    t_cant_buy: bool = False
    ct_timeout_active: bool = False
    t_timeout_active: bool = False
    ct_score: int = 0
    t_score: int = 0
    is_valve_ds: bool = False
    is_hltv_active: bool = False


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


# ── Skin / Item-drop models (from parse_skins / parse_item_drops) ───────────


@dataclass
class SkinData:
    """A weapon skin from parse_skins()."""
    def_index: int
    item_id: int
    paint_index: int
    paint_seed: int
    paint_wear: int
    steam_id: int
    custom_name: str = ""


@dataclass
class ItemDrop:
    """An item drop event from parse_item_drops()."""
    account_id: int
    def_index: int
    drop_reason: int
    inventory: int
    item_id: int
    paint_index: int
    paint_seed: int
    paint_wear: int
    custom_name: str = ""


@dataclass
class GrenadeTrajectory:
    """A grenade trajectory point from parse_grenades().

    Columns from our fork: grenade_type, grenade_entity_id, x, y, z, tick, steamid, name
    """
    tick: int
    x: float
    y: float
    z: float
    grenade_type: str = ""
    grenade_entity_id: int = 0
    thrower_steam_id: int = 0
    thrower_name: str = ""


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
    """Player role classifier output.

    IMPORTANT: confidence and performance metrics are derived from real sample data.
    No assumed or arbitrary win rate values are stored — all values are computed
    from parsed demo events (kills, positions, utility, economy) once sufficient
    sample exists. Reference benchmarks from professional tier-1 data are used
    only as classification thresholds, not as assumed player/team performance.

    Matches the role_taxonomy.py taxonomy:
    - broad_role: high-level identity (entry, awper, igl, rifler, lurker, support, anchor, rotator)
    - map_position: named position on the map (e.g. long_a, mid, banana)
    - zone_role: tactical zone grouping (a_anchor, b_anchor, mid_control, flanker, etc.)
    - secondary_role: optional secondary classification
    """
    player_steam_id: int
    map_name: str
    side: str
    broad_role: str = ""           # e.g. "entry", "awper", "igl"
    map_position: str = ""         # e.g. "long_a", "mid", "banana"
    zone_role: str = ""            # e.g. "a_anchor", "mid_control", "flanker"
    secondary_role: Optional[str] = None  # e.g. "second_awper", "trade_fragger"
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def role_code(self) -> str:
        """Legacy composite code: {broad_role}_{map_position}."""
        return f"{self.broad_role}_{self.map_position}"


@dataclass
class Classification:
    """A unified polymorphic classification label for any entity.

    entity_type: which kind of entity ("event", "series", "match", "round", "kill", "player", "team")
    entity_id:   FK to the classified entity's row
    label_name:  classification axis (e.g. "buy_type", "archetype", "role", "tier")
    label_value: classification value (e.g. "full_buy", "fast_exec", "ct_b_anchor", "tier_1")
    """
    classifier_run_id: int = 0
    entity_type: str = ""
    entity_id: int = 0
    label_name: str = ""
    label_value: str = ""
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)


# ── Side assignment models ───────────────────────────────────────────────────


@dataclass
class SideAssignment:
    """Side assignment for one team slot in one round (including overtime).

    Derived from player_frame data at the round's start tick:
    - Look up any player in team_slot 1 or 2 at round start
    - team_num 2 = T, team_num 3 = CT
    - overtime_index 0 = regulation, 1..N = overtime round pairs
    """
    team_slot: int           # 1 or 2
    round_number: int        # 1-based round index
    overtime_index: int = 0  # 0 for regulation, 1..N for OT
    side: str = ""           # "t" or "ct"
