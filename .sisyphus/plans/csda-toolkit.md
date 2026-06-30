# CSDA Toolkit — Implementation Plan

## Status: IN PROGRESS

## Completed Work

### Infrastructure
- [x] Alembic setup with 9 migrations applied (0001–0009: initial, events/series, round_side_map, weapons, weapon_damage_stats, kill_steam_ids, remove_prw_fk, created_at, event_data_ingest)
- [x] Docker Compose with `postgres:16-alpine` on port 5432 + Adminer on 8080
- [x] 41 tables in `csda` schema, all migrations passing
- [x] pytest configured with 178 tests passing

### Core Models & Ingest
- [x] 36 SQLAlchemy 2.0 ORM models in `db/models.py`
- [x] Domain dataclasses in `domain/models.py` (Match, Player, Round, Kill, Team, MatchTeam, PlayerFrame, RoleClassification, EconomyClassification, Classification, SideAssignment, BuyType, RoundArchetype, etc.)
- [x] `CsdaParser` wrapper over demoparser2 with: rounds, kills, players, player_frames, player_equipment_at_freezetime, item_pickups, item_drops, weapon_fires, parse_match, bomb_events, grenades, inferno_events, grenade_trajectories, damage, player_blinds, player_round_stats
- [x] `IngestBundle` pipeline: demo → domain → DB, wired for demo_file, teams, players, match, rounds, kills, round_equipment, round_purchases, round_side_map, player_round_weapons (purchases + pickups), bomb_events, grenade_detonations, inferno_events, player_blinds, damage_events (with last_place_name), grenade_trajectories, player_round_stats, weapon_drops

### Classifiers
- [x] `RoleClassification` domain model with full taxonomy (broad_roles, map_positions, zone_roles, ROLE_POSITION_PREFERENCES, ZONE_ROLES)
- [x] `RoleClassificationResult.to_classifications()` for persisting to DB
- [x] `classifiers/economy.py` — buy type per side per round (full/half/eco), weapon counts, confidence scoring
- [x] `classifiers/position_classifier.py` — x/y/z → named map position via bounding boxes for 6 maps (dust2, mirage, inferno, nuke, overpass, ancient)

### Data Stored by Ingest
| Table | Status | Notes |
|---|---|---|
| `demo_files` | ✅ Full | filename, checksum, parser name/version, source |
| `teams` | ✅ Full | display name |
| `players` | ✅ Full | steam_id, name |
| `matches` | ✅ Full | map, tick_rate, server_name, source, played_at |
| `match_teams` | ✅ Full | team_slot, display_name |
| `match_players` | ✅ Full | player ↔ match links with match_player_index (0-9 roster position) |
| `rounds` | ✅ Full | start/end_tick, winner_side, end_reason, scores |
| `kills` | ✅ Full | all kill fields including assister, weapon, headshot, wallbang; killer/victim/assister steam IDs added via migration 0006 |
| `round_side_map` | ✅ Full | team_slot, round_number, overtime_index, side — regulation + OT |
| `round_equipment` | ✅ Full | equipment_value, armor, helmet, defuse_kit, weapons JSON — all populated. weapons = {name: {"defindex": X}} from active_weapon_name + round purchases. Note: at freezetime end, active_weapon may still be a knife even after buy. |
| `round_purchases` | ✅ Full | weapon_name, weapon_category, cost enriched from weapons table |
| `player_round_weapons` | ✅ Full | weapon_key, weapon_defindex (from weapons table), is_purchased/is_equipped/is_dropped, purchase_cost, acquired_tick |
| `weapon_pickups` | ✅ Full | `CsdaParser.item_pickups()` → `PlayerRoundWeapon` (is_purchased=False); tick→round assignment via bisect; utility/armor/defuse skipped |
| `weapon_drops` | ✅ Full | `WeaponDropEvent` wired to DB via `item_drops()` — dropped_by/picked_up_by per round |
| `damage_events` | ✅ Full | `CsdaParser.damage()` → `player_hurt` with `attacker_last_place_name` / `victim_last_place_name` (CS2 zone labels) |
| `player_blinds` | ✅ Full | `CsdaParser.player_blinds()` → flashbang blind events with attacker/victim/duration |
| `grenade_detonations` | ✅ Full | `CsdaParser.grenades()` → he/flash/smoke detonations with x/y/z landing positions |
| `inferno_events` | ✅ Full | `CsdaParser.inferno_events()` → molotov start_burn/expire with x/y/z positions |
| `grenade_trajectories` | ✅ Full | `CsdaParser.grenade_trajectories()` → grenade path points with thrower + grenade_entity_id |
| `player_round_stats` | ✅ Full | `CsdaParser.player_round_stats()` → kills/assists/deaths/damage/utility per player per tick |
| `bomb_events` | ✅ Full | `CsdaParser.bomb_events()` → plant/defuse/explode/drop/pickup events with site + has_kit |

---

## TODOs

### Equipment / Purchase Wiring
- [x] Wire `item_pickup` events → `PlayerRoundWeapon` (is_purchased=False) via `CsdaParser.item_pickups()`; tick→round assignment via bisect; grenade/armor/defuse skips
- [x] `WEAPON_DEFINDEX_TO_NAME` corrected to match demoparser defindices (43=flashbang, 44=he_grenade, etc.); "knife" added to WEAPON_CATEGORY as "melee"
- [x] Enrich `round_purchases` with `weapon_category` (from `parsing/constants.weapon_category()`) and `cost`
- [x] Assign `weapon_defindex` to `PlayerRoundWeapon` from weapons table lookup
- [x] Populate `round_equipment.armor`, `round_equipment.helmet`, `round_equipment.defuse_kit`, `round_equipment.equipment_value` via `parse_ticks` + cumulative purchase tracking
- [x] Populate `round_equipment.weapons` JSON from `active_weapon_name`/`item_def_idx` via `parse_ticks` + round purchase lookup. Note: at freezetime end, active_weapon may still be a knife even after buying a rifle (auto-switch happens on spawn). All purchases for the round are included in the weapons dict.
- [x] Wire all missing parser data to DB (bomb_events, grenades, inferno_events, player_blinds, damage_events with last_place_name, grenade_trajectories, player_round_stats, weapon_drops)
- [x] Fix `DamageEvent` domain model to include `attacker_last_place_name` and `victim_last_place_name` from CS2 zone labels

### Remaining Classifiers
- [ ] Build `classifiers/tactical_signals.py` — CT/T position clustering, stack detection from player frames (depends on position_classifier)
- [ ] Build `classifiers/igl_metrics.py` — IGL decision quality metrics (IGL designated externally, no mechanical in-game signal)
- [ ] Build `classifiers/round_archetype.py` — round tactical type classification (depends on economy + position)
- [ ] Build `classifiers/role_classifier.py` — broad role from kill order, weapon, utility, position signals (depends on position + economy + tactical_signals)

### HLTV Enrichment
- [ ] Build `csda_toolkit/enrichment/hltv_adapter.py` — fetch event/series/map data from HLTV API, auto-populate events/event_series tables

---

## Reference Benchmarks (Classification Thresholds Only)
- HLTV/Liquipedia/esport.is — used as tier/classification thresholds, NOT assumed performance
- Win rates, ADR, K/D ratios computed from actual parsed demo data
- IGL: designated externally (HLTV analyst, CLI flag) — no mechanical in-game signal

## Key Constraints
- All metrics computed from real match data — never arbitrary values
- ORM and DB schema must stay in sync
- No live DB required for unit tests (integration tests use transaction rollback)

## Deliverables
- `src/csda_toolkit/db/models.py` — 36 ORM models (incl. 9 new: bomb_events, damage_events, player_blinds, grenade_detonations, inferno_events, grenade_trajectories, player_round_stats)
- `src/csda_toolkit/domain/models.py` — all domain dataclasses
- `src/csda_toolkit/parsing/parser.py` — CsdaParser wrapper
- `src/csda_toolkit/ingest/bundle.py` — IngestBundle pipeline
- `src/csda_toolkit/classifiers/economy.py` — ✅ buy type classifier
- `src/csda_toolkit/classifiers/position_classifier.py` — ✅ position classifier
- `src/csda_toolkit/classifiers/role_taxonomy.py` — ✅ taxonomy
- `src/csda_toolkit/classifiers/tactical_signals.py` — ⬜ TODO (player frame → CT/T clustering + zone transitions)
- `src/csda_toolkit/classifiers/igl_metrics.py` — ⬜ TODO (IGL designated externally)
- `src/csda_toolkit/classifiers/round_archetype.py` — ⬜ TODO (bomb site + grenades + economy)
- `src/csda_toolkit/classifiers/role_classifier.py` — ⬜ TODO (kills + weapons + utility + position)
- `src/csda_toolkit/enrichment/hltv_adapter.py` — ⬜ TODO
- `tests/` — 178 tests passing
