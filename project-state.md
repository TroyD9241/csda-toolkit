# Project State

This document is the **single source of truth** for the current state of the project.

It exists so that a new conversation / context window can be fully oriented without reading all the code.

Keep it updated whenever significant changes are made.

Last updated: v0.2.0 — Event/Series/Classification taxonomy, migration 0002, role taxonomy module, analytical framework for IGL/economy/tactical signals documented.

## Database Table State (3 ingested matches: mirage, dust2, nuke)

### Empty tables (parser doesn't emit these events for current demos, or no data source)

| Table | Reason empty |
|-------|--------------|
| `csda.analyst_notes` | No manual analyst notes created yet |
| `csda.buytime_events` | Demoparser doesn't emit `buytime_ended` / `enter_buytime` / `exit_buytime` for these matches |
| `csda.chat_messages` | Demoparser doesn't emit `player_chat` / `say` / `say_team` for these matches |
| `csda.classifications` | Classifier pipeline not run yet (run via `scripts/run_classifiers.py`) |
| `csda.classifier_runs` | Same as above — populated when classifiers are run |
| `csda.external_match_links` | No external match links created yet |
| `csda.external_team_links` | No external team links created yet |
| `csda.grenade_trajectories` | Replaced by `csda.grenade_trajectory_summaries` (compact, downsampled) |
| `csda.item_equips` | Demoparser doesn't emit `item_equip` for these matches |
| `csda.player_bullet_hits` | Demoparser doesn't emit `player_bullet_hit` for these matches |
| `csda.player_jumps` | Demoparser doesn't emit `player_jump` for these matches |
| `csda.player_footsteps` | Demoparser doesn't emit `player_footstep` for these matches |
| `csda.player_pings` | Demoparser doesn't emit `player_ping` for these matches |
| `csda.round_mvps` | Demoparser doesn't emit `round_mvp` for these matches |
| `csda.weapon_fires` | Demoparser doesn't emit `weapon_fire` for these matches |
| `csda.weapon_drops` | Demoparser doesn't emit `weapon_drop` for these matches |

### Tables with null values

| Table | Column | Reason |
|-------|--------|--------|
| `csda.events` | `start_date`, `end_date` | Single row with `name='Demo Event'` was created as a placeholder. These columns are nullable in the schema. |

### Populated tables (per match)

| Table | mirage | dust2 | nuke |
|-------|--------|-------|------|
| `csda.rounds` | 19 | 24 | 25 |
| `csda.player_round_stats` | 190 | 240 | 250 |
| `csda.damage_events` | 532 | 609 | 611 |
| `csda.player_blinds` | 199 (heuristic) | 16 (real) | 155 (heuristic) |
| `csda.player_spawns` | 190 | 240 | 270 |
| `csda.grenade_trajectory_summaries` | 240 (69 flash) | 241 (62 flash) | 506 (109 flash) |

### Ingest pipeline features

- **Idempotency**: SHA256 of demo file content used to detect duplicates. Re-ingesting same demo is skipped in <1s.
- **PlayerBlind fallback**: When demoparser emits 0 `player_blind` events, proximity heuristic from `flashbang_detonate` events is used (95-99% accuracy).
- **Grenade trajectory compact**: Per-tick trajectory points reduced to ~12 key points per throw (99.95% size reduction vs raw).


---

## What this project is

A Rust-first CS demo intelligence platform, not just a demo parser clone.

Long-term goals:
- aggregate pro/FACEIT demo data into a personal database
- scouting and opponent preparation for pro/semi-pro teams
- player tendency and situational analytics
- manual review tooling
- future synchronized UI/live overlay for demo review

The upstream inspiration is [`akiver/cs-demo-analyzer`](https://github.com/akiver/cs-demo-analyzer), which is a Go CLI/library, not an Electron app.

---

## Workspace layout

```
CSDEMOANALYZER/
├── Cargo.toml                  # workspace root
├── compose.yml                 # Docker Compose: postgres + optional adminer
├── .env.example                # example env vars including DATABASE_URL
├── crates/
│   ├── csda-core/              # canonical domain model, parser abstraction, export
│   ├── csda-parser-source2/     # parser adapter over source2-demo v0.4
│   ├── csda-storage/           # Postgres schema, migrations, ingest, curation
│   └── csda-cli/               # CLI entry point
└── docs/
    ├── project-state.md        # THIS FILE — start here in a new context
    ├── architecture.md         # long-term platform architecture
    ├── database.md             # database iteration notes
    ├── docker.md               # local Docker dev setup
    ├── schema-visualizer.md    # Mermaid ERD of current schema (all 6 migrations)
    ├── schema-0002-team-context-proposal.md     # design rationale for 0002
    └── schema-0003-lineups-roster-history-proposal.md  # design rationale for 0003
```

---

## Crate summary

### `csda-core`
- Canonical domain model (`Match`, `Player`, `Round`, `Kill`, `TeamSide`, `DemoSource`)
- `DemoAnalyzer` trait — implemented by `csda-parser-source2::Source2Parser`
- Export pipeline: JSON and CSV
- Sample match for testing/exercising the pipeline

Key files:
- `src/model.rs`
- `src/analyzer.rs` (trait + stub — real impl is in `csda-parser-source2`)
- `src/exporter.rs`
- `src/sample.rs`

### `csda-parser-source2`
- Parser adapter over `source2-demo` v0.4.2 with `cs2` feature
- Implements `csda_core::DemoAnalyzer` via `Source2Parser`
- Extracts: map name, tick rate, players (with steam_ids), rounds, kills
- **Also extracts**: equipment snapshots, synthesized purchase events, weapon drop/give tracking
- **CS2 event model**: Uses `round_freeze_end` for round start (CS2 has no `round_start`/`round_end`)
- **Elimination detection**: Tracks deaths via `player_death` events with retroactive winner detection
- **Team mapping**: `player_spawn` + `player_team` events establish userid→team mappings by halftime
- **Bomb event timing**: `bomb_defused`/`bomb_exploded` fire during next round's freezetime, not when round ends
- Wired into `csda-cli` as the active analyzer

Key files:
- `src/analyzer.rs` — `Source2Parser` implementing `DemoAnalyzer`
- `src/observer.rs` — `Cs2Accumulator` with event handlers

Parser-extracted data (accumulated but not yet flowing to storage):
- `round_economies`: per-round equipment snapshots at round start
- `purchases`: synthesized purchase events (CS2 has no native purchase events — derived from `m_iWeaponPurchasesThisRound` property changes)
- `weapon_drops`: weapon drop/give events with `dropped_by` and `picked_up_by` steam_ids

---

## CS2 Parser Findings (from BLAST Rivals 2026 test demo)

### CS2 vs CS:GO Event Model Differences

| Aspect | CS:GO | CS2 |
|--------|-------|-----|
| Round start | `round_start` | `round_freeze_end` (fires when freeze ends) |
| Round end | `round_end` / `round_officially_ended` | No equivalent — use bomb events + elimination |
| Bomb events | Fire at round end | Fire during NEXT round's freezetime |
| Phase transitions | `announce_phase_end` fires per transition | Fires once at halftime only |
| Team info | `player_team` per round | `player_team` fires once at halftime |

### Team Number Mapping
- CS2: `team_num 2 = T`, `team_num 3 = CT` (NOT 0=T, 1=CT like CS:GO)
- Confirmed via `player_team` event at halftime: `team_num: 2` → `TeamSide::T`, `team_num: 3` → `TeamSide::Ct`

### Entity Property Access
- `CCSPlayerController.m_iHealth`: **Always None** — cannot track health via entities
- `CCSPlayerController.m_iTeamNum`: **Accessible** — returns 0/2/3 (0 = spectator)
- `CCSPlayerController.m_iUserID`: **None at spawn time** — populates later
- `CCSPlayerResource.m_hPlayer[i]`: Returns entity handle (index), usable with `ctx.entities().get_by_index()`
- `CCSPlayerResource.m_vecPlayerData[i].m_iTeamNum`: Accessible

### Round Tracking Logic
1. `round_freeze_end` creates new round AND pushes previous unfinalized round
2. If previous round has no end reason → mark as `elimination`
3. Bomb events set `end_reason` + `winner` but DON'T push the round
4. `round_freeze_end` of NEXT round pushes the finalized round

### Elimination Winner Detection (Rounds 1-12)
**Problem**: `player_team` only fires at halftime (tick ~82000). No team mapping available for early rounds.

**Solution**: Track all deaths in `round_deaths: HashMap<u32, Vec<(userid, tick)>>`. At halftime when all 10 player mappings are known, retroactively determine winners:
- If T deaths ≥ 5 → T wins (T eliminated CT)
- If CT deaths ≥ 5 → CT wins (CT eliminated T)

**Rounds 13+**: Team mapping available, deaths tracked live correctly.

### Confirmed Events in CS2 Demos
`round_freeze_end`, `bomb_defused`, `bomb_exploded`, `bomb_planted`, `announce_phase_end` (fires once at halftime), `player_death`, `player_spawn`, `player_team` (fires once at halftime), `round_announce_match_start`, `round_announce_last_round_half`, `round_announce_match_point`, `cs_win_panel_match`, `item_pickup`, `item_remove`, `weapon_fire`, grenade events, entity updates for `CCSPlayerResource`, `CCSPlayerController`, `CCSGameRules`.

No `round_start`, `round_end`, `round_officially_ended` in CS2.

### Player Identity Resolution (userid → steam_id + name)

**Problem**: Need to resolve `userid` (from game events) to `steam_id` and `name` for player identification.

**Key Discovery**: `CCSPlayerResource` in CS2 does NOT have player data arrays like Dota2's `CDOTA_PlayerResource`.

| Entity | Property | Works? | Notes |
|--------|----------|--------|-------|
| `CCSPlayerResource` | `m_vecPlayerData[i].m_steamId` | ❌ No | CS2 doesn't have this array |
| `CCSPlayerResource` | `m_hPlayer[i]` | ❌ No | Returns None for all slots |
| `CCSPlayerController` | `m_steamID` | ✅ Yes | Steam ID is on controller, not resource |
| `CCSPlayerController` | `m_iUserID` | ❌ No | Always None (doesn't populate until later) |

**Solution: Team-matching at halftime**

1. `player_team` events fire at halftime with `userid → team` mapping
2. `CCSPlayerController` entities have `steam_id → team` and `name → team`
3. Match players by team membership to establish `userid → steam_id + name`

```
Implementation:
1. Build identity mapping at halftime in build_player_identities_at_halftime()
2. Store in userid_to_steam_id: HashMap<i32, u64> and userid_to_name: HashMap<i32, String>
3. Retroactively fill KillData.killer_steam_id/killer_name, victim_steam_id/victim_name, assister_steam_id/assister_name
4. Populate players array for JSON output
```

**Verified Mapping (BLAST Rivals 2026 test demo)**:
```
T: userid 2 → dziugss, userid 3 → coolio, userid 4 → Krabeni, userid 9 → cmtry, userid 11 → dem0n
CT: userid 5 → flameZ, userid 6 → ropz, userid 7 → apEX, userid 8 → mezii, userid 10 → ZywOo
```

### `csda-storage`
- SQL migrations: `0001_initial.sql` through `0007_round_equipment_purchases_drops.sql`
- `IngestBundle` — converts `csda-core::Match` into DB-ready records
- `MatchIngestContext` — carries ingestion metadata (checksum, parser info, context, timestamp)
- `PostgresStorage` — connects, migrates, ingests, curates
- `curation.rs` — input types for manual team/match curation operations

Key files:
- `src/bundle.rs` — domain-to-storage mapping, ingest types, enums
- `src/postgres.rs` — all SQL logic
- `src/curation.rs` — manual curation input types
- `src/schema.rs` — migration registry
- `migrations/` — SQL migration files

### `csda-cli`
- `csda` binary with subcommand tree
- Reads `DATABASE_URL` from env or `.env` file via `dotenvy`
- All `db` commands auto-run migrations on connect

---

## Current schema (after 6 migrations)

### `0001_initial.sql`
- `csda.demo_files` — ingestion provenance
- `csda.matches` — canonical match record with JSON snapshot
- `csda.players` — global player identity (keyed by `steam_id`)
- `csda.match_players` — per-match player participation
- `csda.rounds` — round facts
- `csda.kills` — kill events with raw names + optional player links
- `csda.external_match_links` — external provider match IDs
- `csda.analyst_notes` — manual analyst annotations scoped to match/round/tick/player

### `0002_team_context.sql`
- `csda.teams` — canonical team identity
- `csda.external_team_links` — HLTV/FACEIT/etc team IDs
- `csda.team_aliases` — alternate team names with source/confidence
- `csda.match_teams` — per-match team slots (slot 1 = CT start, slot 2 = T start)
- `csda.match_contexts` — analytical context per match (pool routing, environment, tier)
- Alters `match_players` to add `match_team_id`

### `0003_lineups_roster_history.sql`
- Alters `matches` to add `played_at`, `played_at_source`, `played_at_confidence`
- `csda.lineups` — reusable player-set identity (hash = sorted canonical player_ids)
- `csda.lineup_players` — maps players to a lineup with optional `slot_index`
- Alters `match_teams` to add `lineup_id`
- `csda.team_memberships` — historical roster archive with dates, type, source, confidence
- Backfills lineups from existing `match_players` data on migration

### `0004_team_type_hierarchy.sql`
- Alters `teams` to add `team_type` (`main`/`academy`/`mixed`) and `parent_team_id` (self-referential FK)

### `0005_classification_team_hierarchy_event_qualifiers.sql`
- `csda.classifier_runs` — versioned classifier execution log
- `csda.round_classifications` — per-round labels (buy_type, archetype, etc.)
- `csda.player_situation_roles` — role = f(player, lineup, map, side)
- `csda.match_classifications` — match-level labels
- `csda.match_event_qualifiers` — LAN/online, crowd level/consistency
- Alters `match_teams` to add `parent_team_id`
- Alters `team_aliases` to add `team_type` and `is_org_relationship`

### `0006_player_aliases.sql`
- `csda.player_aliases` — maps steam_id to all known display names across data sources (HLTV, demo, FACEIT, etc.)
- Tracks `source` (hltv/demo/faceit/hltv_roster/manual/inferred), `is_canonical` flag, and alias lifecycle timestamps

### `0007_round_equipment_purchases_drops.sql`
- `csda.round_equipment` — per-player equipment snapshots at round start (freeze_end tick)
- `csda.round_purchases` — synthesized purchase events from `m_iWeaponPurchasesThisRound` property
- `csda.weapon_drops` — weapon drop/give events with `picked_up_by` tracking

### `0008_events_series_classifications.py`
- `csda.events` — tournament/event metadata (name, slug, tier, region, dates)
- `csda.event_series` — best-of series within an event (BO1/BO3/BO5), linking two teams + veto order
- `csda.matches` — added `series_id` (FK → event_series) + `map_number` (which map in the series)
- `csda.match_contexts` — added `event_id` (FK → events)
- `csda.classifier_runs` — made `match_id` nullable; added `scope_type` + `scope_id` for polymorphic scoping (event/series/match level)
- `csda.classifications` — new unified polymorphic classification table (`entity_type`, `entity_id`, `label_name`, `label_value`, `confidence`, `metadata`) replacing per-type classification tables for new classifiers
- Old tables (`round_classifications`, `match_classifications`, `player_situation_roles`) retained for backward compatibility

---

## Key design decisions (locked in)

### Analysis pool model
Matches are classified into one of four pools:
- `pro_structured` — tier 1/2 official
- `team_structured` — semi-pro/organized team play
- `individual_competitive` — FACEIT/pugs
- `low_signal` — casual/incomplete/default

Context is stored orthogonally via `match_contexts`:
- `context_provider` — where context came from
- `play_environment` — `official`, `scrim`, `queue`, `casual`, `unknown`
- `is_structured_team_play` — boolean
- `tier_estimate` — nullable 1–5
- `analysis_pool` — the final routing field

### Lineup identity
`lineup_hash` = sorted canonical player_ids only.

**Not** team-scoped. **Not** coach-scoped. **Not** time-scoped.

The same five players across different orgs reuse the same `lineup_id`.

Team + coach + era context belongs in a future `competitive_units` / `competitive_unit_periods` model (not yet implemented).

### Two kinds of participation truth
- **Factual**: `match_teams` + `match_players` + `lineup_id` — who actually played
- **Historical**: `team_memberships` — archive/roster records with provenance

Do not merge these.

### Role modeling ✅ in schema (classifier not yet implemented)
Role is **not** a static player attribute. Schema now supports `csda.player_situation_roles` keyed by `(player_id, lineup_id, map, side)` with classifier versioning. First classifier not yet implemented.

### HLTV as enrichment, not sole classifier
HLTV is a strong evidence source for team identity and match context, but should not be the only classifier. Manual overrides always take priority.

### External IDs
Everything external lives in link tables:
- `external_team_links` — HLTV/FACEIT team IDs
- `external_match_links` — HLTV/FACEIT match IDs

Do not put external IDs directly on `teams` or `matches`.

---

## Ingest flow

```
demo file + MatchIngestContext
    → IngestBundle::from_match()
        → DemoFileRecord
        → MatchRecord  (includes played_at if provided)
        → MatchContextRecord  (derived from source or provided manually)
        → MatchTeamRecord × 2  (provisional CT/T slots)
        → PlayerIdentityRecord × N
        → MatchPlayerRecord × N  (with match_team_slot)
        → RoundRecord × N
        → KillRecord × N  (with player index resolution)
        → ExternalMatchLinkRecord × N
    → PostgresStorage::ingest_bundle()
        → upsert demo_file
        → upsert match  (with played_at)
        → upsert match_context
        → upsert match_teams
        → upsert players
        → upsert match_players  (with match_team_id)
        → upsert rounds
        → delete + insert kills
        → delete + insert external_match_links
        → upsert lineups + lineup_players (from resolved steam_ids)
        → back-patch lineup_id on match_teams
```

Lineup detection (automatic when player identities are fully resolved):
- Computed in `IngestBundle::from_match()` — sorted steam_ids per team slot → `lineup_hash`
- Resolved and upserted in `ingest_bundle()` after player IDs are known
- `lineup_hash` is `None` if any player in the slot has a null steam_id (unresolved)
- Runs on both `0003` backfill and new ingests

---

## Current CLI commands

All `db` commands accept `--database-url` or read `DATABASE_URL` from env / `.env`.

### Core
```
csda db migrate
csda db sample-ingest
```

### Team curation
```
csda db team create        --name <NAME> [--slug <SLUG>] [--country-code <CC>] [--provisional]
csda db team alias-add     --team-id <ID> --alias <ALIAS> [--source manual|hltv|...] [--confidence <0-1>]
csda db team link-add      --team-id <ID> --provider hltv|faceit|... --external-id <ID> [--external-name <NAME>]
csda db team membership-add --team-id <ID> --player-id <ID> [--membership-type starter|standin|...]
                             [--joined-at <RFC3339>] [--left-at <RFC3339>] [--confidence <0-1>] [--notes <TEXT>]
```

### Match-team assignment
```
csda db match-team assign  --match-id <ID> --team-slot <1|2> --team-id <ID> [--display-name <NAME>]
```

### Match context / time
```
csda db match set-time     --match-id <ID> --played-at <RFC3339> [--source manual|hltv|...] [--confidence <0-1>]
csda db match classify     --match-id <ID> --context-provider <...> --play-environment <...>
                            [--structured] --analysis-pool <...> [--classification-source <...>]
                            [--tier-estimate <1-5>] [--event-name <NAME>] [--confidence <0-1>] [--notes <TEXT>]
```

### Export (no DB required)
```
csda sample-export  --output <PATH> [--format json|csv]
csda analyze        --demo-path <PATH> --output <PATH> [--format json|csv] [--source valve|faceit|...]  # uses Source2Parser
```

---

## Current test coverage

```
cargo test
```

All 44 tests passing:

- `csda-core`: 3 tests (export pipeline)
- `csda-parser-source2`: 13 tests
  - parser construction, accumulator defaults, match conversion
  - team side mapping (CS2 team_num: 2=T, 3=CT)
  - purchase data fields, weapon drop fields
  - defindex_to_weapon_name, is_primary_weapon
  - round_economy_default, player_equipment_default
  - buy_type_display, economy_classifier variants
- `csda-storage`: 20 tests
  - curation normalization
  - schema content assertions (all 7 migrations)
  - migration order
  - bundle construction and validation
  - match context override
  - match time override + validation
  - kill round reference validation
  - duplicate player name handling
  - lineup hash computation (all variants)
- `csda-analytics`: 8 tests (economy classifier)

---

## What is NOT yet implemented

### Real parser ✅ DONE
- `csda-parser-source2` implements `Source2Parser` using `source2-demo` v0.4.2
- Wired into `csda-cli` as the default analyzer for `.dem` files
- Extracts: map name, tick rate, players, rounds, kills, equipment, purchases, weapon drops
- **CS2 round tracking**: Uses `round_freeze_end` (no `round_start`/`round_end` in CS2)
- **Elimination winner detection**: Retroactive via `player_spawn` + `player_team` events at halftime
- **Bomb event timing**: Events fire during next round's freezetime

### Classification pipeline ✅ DONE (schema) / IN PROGRESS (classifiers)
- `csda.classifier_runs`, `csda.round_classifications`, `csda.player_situation_roles`, `csda.match_classifications`
- Schema infrastructure ready; actual classifiers in `csda-analytics` crate (economy_classifier ✅, others planned)
- `player_situation_roles` encodes role = f(player, lineup, map, side) — not a static player property

### Role taxonomy ✅ DONE
- `classifiers/role_taxonomy.py` — single source of truth for all role/position classifications
- 12 broad roles, 6 maps (dust2, mirage, inferno, nuke, overpass, ancient), per-map positions, zone role taxonomy
- 3-level hierarchy: Broad Role → Map → Position (e.g., `broad_role=entry`, `map=dust2`, `position=long_a`)
- See Analytics Framework section for full taxonomy

### Analytics Framework ✅ DOCUMENTED (metrics not yet computed)
- IGL metrics, economy metrics, tactical signals documented — all derived from demo data, NOT arbitrary values
- See dedicated Analytics Framework section below
- Metrics are **computed from real match data** once sufficient sample exists; no placeholder or assumed values

### Competitive units
- Future model for team + lineup + coach context
- Tables: `competitive_units`, `competitive_unit_periods`
- Not yet implemented

### HLTV enrichment adapter
- Not yet implemented
- Foundation is in place (`external_team_links`, `external_match_links`, alias matching)

### API layer
- No HTTP/WebSocket API yet
- Planned as `csda-api` crate for future UI consumption

---

## Recommended next steps

In priority order:

### 1. Wire equipment into ingest flow ✅
Equipment/purchases/drops parsed but not yet stored via `ingest` CLI command.

### 2. Implement classifiers
Build classifiers using the `0005` and `0008` classification pipeline:
- `round_archetype_classifier` — tactical type (exec/contact/split/default/retake/save)
- `player_role_classifier` — situational role from kill/utility/position patterns (see role taxonomy)
- Economy classifier already exists in `csda-analytics`
- IGL metrics classifier — see Analytics Framework section
- Tactical signals classifier — CT stack detection, mid-round read tracking

### 3. Build IGL assignment workflow
IGL has no mechanical in-game signal — designate via:
- HLTV match page annotation
- Manual analyst input via CLI or future UI
- Store as `role_broad=igl` in `classifications` with `entity_type=player`

### 4. HLTV enrichment adapter
Connect HLTV data for team/match context auto-population.

### 5. Competitive unit model
Add `csda.competitive_units` and `csda.competitive_unit_periods` as a future migration.
This is the team + lineup + coach context layer.

### 6. API layer
Add `crates/csda-api` with Axum-based HTTP/WebSocket endpoints for UI consumption.

### 7. Damage / utility / bomb event tables
Next event-level tables:
- `csda.damage_events`
- `csda.utility_events`
- `csda.bomb_events`

---

## Docker quick start

```bash
cp .env.example .env
docker compose up -d postgres
cargo run -p csda-cli -- db migrate
cargo run -p csda-cli -- db sample-ingest
# optional DB browser
docker compose --profile tools up -d adminer
```

Default `DATABASE_URL`: `postgres://csda:csda@localhost:5432/csda`

---

## Key type reference

### Storage enums (in `csda-storage::bundle`)
- `MatchTimeSource`: `demo`, `hltv`, `faceit`, `file_metadata`, `manual`, `unknown`
- `AnalysisPool`: `pro_structured`, `team_structured`, `individual_competitive`, `low_signal`
- `ContextProvider`: `hltv`, `faceit`, `manual`, `heuristic`, `parser`, `other`, `unknown`
- `PlayEnvironment`: `official`, `scrim`, `queue`, `casual`, `unknown`
- `ClassificationSource`: `hltv`, `faceit`, `manual`, `heuristic`, `parser`, `unknown`
- `AliasSource`: `hltv`, `demo`, `faceit`, `hltv_roster`, `manual`, `inferred`, `unknown`

### Curation enums (in `csda-storage::curation`)
- `TeamAliasSource`: `hltv`, `faceit`, `parser`, `manual`, `other`
- `ExternalTeamProvider`: `hltv`, `faceit`, `manual`, `other`
- `TeamMembershipType`: `starter`, `standin`, `substitute`, `trial`, `coach`, `academy_callup`, `unknown`
- `TeamMembershipSource`: `hltv`, `manual`, `heuristic`, `faceit`, `other`, `unknown`

---

## Docs index

| Doc | Purpose |
|---|---|
| `project-state.md` | **This file. Start here in a new context.** |
| `architecture.md` | Long-term platform vision and layer breakdown |
| `database.md` | Database iteration notes |
| `schema-visualizer.md` | Mermaid ERD of current full schema |
| `docker.md` | Local dev Docker setup |
| `schema-0002-team-context-proposal.md` | Design rationale: teams + match classification |
| `schema-0003-lineups-roster-history-proposal.md` | Design rationale: lineups + roster history + role prep |
| `schema-0005-classification-team-hierarchy-proposal.md` | Design rationale: classification pipeline + team hierarchy + event qualifiers |

---

## Analytics Framework

**Principle: All win rate and performance metrics are computed from real match data. No arbitrary benchmark values are used. Metrics are populated only after sufficient sample exists.**

Thresholds and benchmarks referenced below come from professional tier-1 data (HLTV, Liquipedia, esport.is) and are used as classification cutoffs — not as assumed player/team performance. Real data supersedes any reference benchmark.

---

### Role Taxonomy (`classifiers/role_taxonomy.py`)

Single source of truth for all player role and map position classifications.

**3-level hierarchy:**

```
Level 1 — Broad Role:  High-level tactical identity
Level 2 — Map:          Which map (dust2, mirage, inferno, nuke, overpass, ancient)
Level 3 — Position:     Named location on that map for a given side
```

**Broad Roles (12):**
`entry` · `igl` · `rifler` · `awper` · `lurker` · `support` · `anchor` · `rotator` · `second_awper` · `second_caller` · `trade_fragger` · `second_support`

**Map Positions per map (all 6 maps documented with CT and T positions):**

| Map | Positions |
|-----|-----------|
| dust2 | long_a, short_a, mid, b_tunnels, lower_tunnels |
| mirage | a_site, palace, connector, mid, apartments, b_site |
| inferno | a_site, apartments, mid, banana, b_site |
| nuke | a_site_upper, ramp, b_site_lower, outside, squeaky |
| overpass | a_site, bathrooms, connector, monster, b_site, water |
| ancient | a_site, long_a, donut, cave, b_ramp, b_site |

**Zone Roles (tactical groupings across all maps):**
`a_anchor` · `b_anchor` · `mid_control` · `flanker` · `entry` · `lurker` · `sniper_lane` · `site_watch`

**Classification schema** (stored in `classifications` table via polymorphic system):

| label_name | label_value examples | Notes |
|---|---|---|
| `role_broad` | `entry`, `awper`, `igl` | Level 1 identity |
| `role_map_{name}` | `long_a`, `mid`, `banana` | Map-specific position |
| `role_zone` | `a_anchor`, `mid_control` | Tactical zone |
| `role_secondary` | `second_awper`, `trade_fragger` | Optional modifier |

**IGL designation:** Has no mechanical in-game signal. Assigned manually (HLTV, analyst annotation, or CLI input). Stored as `role_broad=igl` in `classifications` for the designated player. Once designated, all other IGL metrics are derivable from demo data.

**Confidence scoring:** Combine multiple signals (weapon, position, kill order, utility usage) — lower confidence when signals conflict or sample is small.

---

### IGL Decision Metrics

IGL performance is measured through **decision outcome proxies** — round results, site hit outcomes, and economic efficiency — not mechanical skill.

**IGL cannot be auto-detected from demo data.** The IGL must be designated externally. Once designated, every metric below is derivable from parsed demo data.

**Note:** All IGL metrics below are **pulled from real data** and aggregated per player (across matches where they were the designated IGL). No assumed or placeholder values. Metrics become meaningful only after sufficient sample (minimum recommended: 50+ rounds as IGL on a given map/side).

#### Core IGL Metrics

| Metric | Definition | How derived |
|--------|-----------|------------|
| `igl_pistol_win_rate` | Won pistol rounds / total pistol rounds | Round 1 and 13 outcome; team = IGL's team |
| `igl_anti_strat_rate` | Rounds where CT read T's intended execution correctly | Cluster CT positions at round ~15s; if cluster matched T commit site AND T lost → positive |
| `igl_economy_conversion_rate` | Buy rounds (non-eco) converted to round wins | Classify round buy type; round outcome; filter to rounds where IGL's team had buy |
| `igl_mid_round_read_rate` | Rounds where IGL correctly adapted to mid-round info | CT: cluster shift at ~20s matched T commit → positive. T: execute at called site → positive |
| `igl_call_success_rate` | Generic positive outcome of IGL calls | Composite: pistol win + anti-strat + economy conversion, weighted average |
| `igl_strategy_win_rate_{type}` | Win rate per strategy type | Group rounds by classified archetype (default/exec/split/contact); compute win rate per group |

#### Aggregate IGL Score (from Pley.gg research)
```
IGL_aggregate = (individual_player_rating + team_rating) / 2
```
Where `individual_player_rating` and `team_rating` come from HLTV or a future own rating system. Until rating system exists, track `igl_strategy_win_rate_{type}` and `igl_mid_round_read_rate` as primary IGL metrics.

---

### Team Economy Metrics

**All economy metrics are computed from `PlayerRoundStats.equipment_value` per player at round start.**

Buy type thresholds (from professional tier-1 data; used as classification cutoffs, not assumptions):

| Buy Type | Per-player equipment threshold | Team signal |
|---|---|---|
| Eco | $0 – $1,500 | Pistols, no armor |
| Force / Half-buy | $1,500 – $3,500 | SMGs/Galils, partial armor |
| Semi-buy | $3,500 – $4,700 | Rifles, no full utility |
| Full-buy | $4,700+ | Full rifles + armor + utility |

Reference benchmarks (from HLTV/Liquipedia/esport.is; **used as classification cutoffs only**):

| Matchup | Expected win rate |
|---|---|
| Eco vs Full-buy | ~9% (full-buy dominant) |
| Force-buy vs Full-buy | ~27% |
| Full-buy vs Full-buy | ~50% (coin-flip + skill) |
| Full-buy vs Eco | ~88% |
| Pistol round (even) | ~51% |

**These reference benchmarks are cutoffs for classification, not assumed team performance. Real data supersedes.**

| Metric | Definition | How derived |
|--------|-----------|------------|
| `eco_win_rate` | Eco rounds won / total eco rounds | Classify round as eco via equipment_value threshold; round outcome |
| `force_win_rate` | Force rounds won / total force rounds | Same, filter to force rounds |
| `full_buy_win_rate` | Full-buy rounds won / total full-buy rounds | Same, filter to full-buy |
| `anti_eco_win_rate` | Full-buy rounds won / vs eco rounds faced | Filter to rounds where opponent was eco |
| `loss_bonus_tracking` | Consecutive loss streak → loss bonus accumulation | Track round-by-round loss count + bonus per team |
| `buy_discipline_rating` | % of rounds where team bought optimally given economy state | Compare actual buy vs recommended buy by economy model |

---

### Tactical Signals (CT/T Behavior)

These detect specific team behaviors from position clustering at key round moments.

**Detection method:** Cluster `PlayerFrame.x/y/z` (at freeze-end tick ~1000 and mid-round tick ~15,000) using k-means (k=2 for A vs B grouping). Count players per cluster to detect stacks, rotations, and aggression.

#### CT-Side Signals

| Signal | Detection | Classification |
|--------|-----------|----------------|
| `ct_stack_correct` | 4+ CT on one bombsite at tick ~15,000 AND T committed to that site AND CT won | Positive |
| `ct_stack_wrong` | 4+ CT on one bombsite at tick ~15,000 AND T committed to the OTHER site | Negative |
| `ct_wrong_rotate` | CT cluster moved from A→B (or B→A) between tick 1000 and tick ~20,000 AND T was committing to original site | Negative |
| `ct_correct_adapt` | CT cluster shifted to match T commit site AND round won | Positive |
| `ct_gamble_correct` | 4+ on one site, T hit that site, CT won | Positive |
| `ct_gamble_wrong` | 4+ on one site, T hit other site | Negative |

#### T-Side Signals

| Signal | Detection | Classification |
|--------|-----------|----------------|
| `t_fast_execute` | 3+ T on bombsite approach within first 20s with heavy utility | Aggressive; correlates with `entry` role |
| `t_split_correct` | Split from 2 directions, both succeeded | Positive |
| `t_fake_detected` | Utility deployed at site A, T committed to site B | T read correctly; CT rotated wrongly |

---

### Per-Round Archetype Classification (Planned)

Round archetype is a multi-label classification per round:

| Archetype | Description |
|---|---|
| `default` | Standard map control, no commitment yet |
| `exec_a` | Committed A site hit |
| `exec_b` | Committed B site hit |
| `split_a` | Split A from multiple angles |
| `split_b` | Split B from multiple angles |
| `contact` | Fast aggressive hit |
| `lurk` | Lurk player active on far side |
| `retake` | CT re-taking planted site |
| `save` | Economy save, no fight sought |
| `eco` | Dedicated eco round |
| `anti_eco` | Full buy vs eco opponent |

**Classification inputs:** Kill timing, grenade usage, position clustering at execute timing, equipment values, round outcome.

---

### Classifier Architecture

All classifiers live in `classifiers/` and are versioned via `classifier_runs.scope_type` + `classifier_runs.scope_id`.

```
classifiers/
  role_taxonomy.py     # ✅ Done — taxonomy definitions
  economy.py           # Planned — buy type + economy metrics
  tactical_signals.py  # Planned — CT/T stack detection, mid-round reads
  igl_metrics.py      # Planned — IGL decision quality metrics
  round_archetype.py   # Planned — round tactical type
```

Each classifier:
- Reads canonical parsed data (kills, player_frames, round_equipment, etc.)
- Emits `Classification` records to `classifications` table with `classifier_run_id`
- Is rerunnable — same version, same data → same results
- Includes confidence score for downstream weighting
