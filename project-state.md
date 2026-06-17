# Project State

This document is the **single source of truth** for the current state of the project.

It exists so that a new conversation / context window can be fully oriented without reading all the code.

Keep it updated whenever significant changes are made.

Last updated: after `0007_round_equipment_purchases_drops` migration — CS2 demo parsing fully operational with round tracking, elimination winner detection, and equipment tracking.

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
Build classifiers using the `0005` classification pipeline:
- `round_archetype_classifier` — tactical type (exec/contact/split/default/retake/save)
- `player_role_classifier` — situational role from kill/utility/position patterns
- Economy classifier already exists in `csda-analytics`

### 3. HLTV enrichment adapter
Connect HLTV data for team/match context auto-population.

### 4. Competitive unit model
Add `csda.competitive_units` and `csda.competitive_unit_periods` as a future migration.
This is the team + lineup + coach context layer.

### 5. Damage / utility / bomb event tables
Next event-level tables:
- `csda.damage_events`
- `csda.utility_events`
- `csda.bomb_events`

### 6. API layer
Add `crates/csda-api` with Axum-based HTTP/WebSocket endpoints for UI consumption.

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
| `docs/project-state.md` | **This file. Start here in a new context.** |
| `docs/architecture.md` | Long-term platform vision and layer breakdown |
| `docs/database.md` | Database iteration notes |
| `docs/schema-visualizer.md` | Mermaid ERD of current full schema |
| `docs/docker.md` | Local dev Docker setup |
| `docs/schema-0002-team-context-proposal.md` | Design rationale: teams + match classification |
| `docs/schema-0003-lineups-roster-history-proposal.md` | Design rationale: lineups + roster history + role prep |
