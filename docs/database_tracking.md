# Database Tracking & Progress

Tracks empty tables, null values, bugs, and goals for the `csda` schema.

Last updated: 3 matches ingested (mirage, dust2, nuke) via `IngestBundle` with SHA256 idempotency.

---

## Answers to Open Questions

### Q: Is `player_round_stats` all cumulative for a match?
**Yes.** Each row is a cumulative snapshot at a specific `tick` (from PRS extraction at `freeze_end_tick` per round). So `damage`, `kills`, `deaths`, etc. are running totals — the max value across all rows for a player in a match = their match totals. Use `MAX(damage)` (or the last row by tick) for the match total.

### Q: Does `players` have enough info or is it overlapping?
**It's intentionally minimal — a global player directory:**
- `steam_id`: PK
- `last_known_name`: most recent alias
- `created_at`, `updated_at`: timestamps

The player → match relationship lives in `match_players` (with `team_side` and `match_team_id`). The `players` table is just the canonical identity table, one row per unique steam_id across all matches. No overlap with `match_players`.

### Q: What is `round_side_map`?
**Per-round team side assignment.** CS2 teams swap sides after halftime (and in overtimes). This table records which team (`team_slot` 0 or 1) was on CT vs T for each `round_number` per match. Critical for per-round analytics (e.g., win rate by side, economy by side).

Schema: `(match_id, team_slot, round_number) → side` (`"CT"` or `"T"`)

### Q: Is `weapons` a lookup table?
**Yes.** `weapons` is a **static reference table** (not per-match). One row per weapon (AK-47, AWP, etc.) with metadata: `damage`, `armor_penetration`, `rpm`, `magazine_size`, `head_damage_armored`, `cost`, `category`, `slot`, `weapon_key`, `display_name`. Populated from `weaponData/CS2 Weapon Spreadsheet...csv` (cs2damage.com source). Used as a join target for `player_round_weapons.weapon_defindex`.

### Q: What is `team_memberships`?
**Roster history per team.** Tracks when players joined/left a team org, with `membership_type` (e.g., "starter", "sub", "standin"), `confidence` (0-1), and `source` (e.g., "hltv", "manual"). Currently empty — would be populated by the HLTV adapter scraping team rosters. Not per-match.

### Q: How do I know if a `player_blinds` row is real or estimated?
Check the `is_heuristic` column:
- `is_heuristic = false` → real demoparser event
- `is_heuristic = true` → proximity-heuristic estimate (demoparser emitted 0 events for this match)

In our 3 ingested demos: dust2 has 16 real events (heuristic skipped); mirage and nuke had 0 real events so the heuristic filled in 199+155=354 estimates. The heuristic is ~70-85% accurate (no FOV check, no wall check, no prior flash stack).


---

## Empty Tables (Reason / Action Needed)

| Table | Status | Action |
|-------|--------|--------|
| `analyst_notes` | No analyst notes created | Add UI/form for manual notes |
| `buytime_events` | Demoparser doesn't emit for these demos | Re-try with different parser events |
| `chat_messages` | Demoparser doesn't emit | Parser limitation, likely no fix |
| `classifications` | Classifier pipeline not run | Run `scripts/run_classifiers.py` |
| `classifier_runs` | Same as above | Populated when classifiers run |
| `external_match_links` | No external links yet | Populated by HLTV adapter |
| `external_team_links` | No external links yet | Populated by HLTV adapter |
| `grenade_trajectories` | **Replaced** by `grenade_trajectory_summaries` | Keep table for raw data option, or drop |
| `item_equips` | Demoparser doesn't emit | Parser limitation |
| `lineup_players` | No lineups created | Populated by lineup tool |
| `lineups` | No lineups created | Populated by lineup tool |
| `match_classifications` | Classifier pipeline not run | Run classifiers |
| `match_contexts` | No match context added | Populated by context tool |
| `match_event_qualifiers` | No event qualifiers | Populated by event system |
| `player_aliases` | No alias tracking yet | Populated by HLTV adapter |
| `player_bullet_hits` | Demoparser doesn't emit | Parser limitation |
| `player_footsteps` | Demoparser doesn't emit | Parser limitation |
| `player_jumps` | Demoparser doesn't emit | Parser limitation |
| `player_pings` | Demoparser doesn't emit | Parser limitation |
| `player_situation_roles` | Classifier not run | Run classifiers |
| `round_classifications` | Classifier not run | Run classifiers |
| `round_mvps` | Demoparser doesn't emit | Parser limitation |
| `team_aliases` | No alias tracking yet | Populated by HLTV adapter |
| `team_memberships` | No roster data scraped | Run HLTV adapter |
| `weapon_drops` | Demoparser doesn't emit | Parser limitation |
| `weapon_fires` | Demoparser doesn't emit | Parser limitation |

---

## Null Value Issues (Need Investigation / Fix)

### BUG: `match_players` has 2 rows with NULL `team_side` and `match_team_id`
- **id=113**: match=12, name=mezii, steam_id=76561197973140692
- **id=114**: match=12, name=apEX, steam_id=76561197989744167
- **Root cause**: Match 12 is dust2. The team inference in `bundle.py` uses "first event in round 0" to assign sides. If a player had no kill and no death in round 0, their side can't be inferred. mezii and apEX likely didn't participate in round 0.
- **Fix**: Add fallback in `_compute_side_assignments` — use other rounds, or use damage events, or default to a side based on majority.

### `events` table: `start_date` and `end_date` are NULL
- Single row with `name='Demo Event'` as placeholder
- These columns are nullable in the schema
- **Fix**: Either populate from the actual event metadata, or make the columns non-nullable with sensible defaults

### `match_teams`: `team_id`, `lineup_id`, `parent_team_id`, `score`, `is_winner`, `metadata` are all NULL
- These are intentionally optional fields
- `score` and `is_winner` should be populated from match results
- **Fix**: Populate `score` and `is_winner` post-ingest from match data

### `matches`: `canonical_match_json`, `played_at_source`, `played_at_confidence` are NULL
- Optional metadata fields for HLTV matching
- **Fix**: Populate from HLTV adapter (enrichment/hltv_adapter.py)

### `player_blinds`: `victim_name` is empty string
- Demoparser's `player_blind` event doesn't include victim name (only steam_id)
- **Fix**: Look up victim name from `players.last_known_name` using `victim_steam_id`

### `player_round_weapons`: `dropped_at_tick` is NULL
- For purchased weapons (not dropped), this is expected
- For picked-up weapons, this should be set
- **Fix**: In ingest, set `dropped_at_tick` from the event data

### `teams`: `country_code`, `team_type`, `parent_team_id` are NULL
- Optional metadata fields
- **Fix**: Populate from HLTV adapter scraping team profiles

---

## Goals & Next Steps

### Short-term (this session)
- [x] Ingest 3 demos (mirage, dust2, nuke) via IngestBundle
- [x] Add SHA256 idempotency (prevents duplicate ingestion)
- [x] Add PlayerBlind proximity heuristic fallback
- [x] Add compact grenade trajectory summary (12 points/throw vs raw)
- [x] Add batch event tables (weapon_fire, player_spawn, etc.)
- [x] PRS column types widened (SMALLINT → INTEGER)
- [ ] **Fix match_players NULL team_side for players inactive in round 0**
- [ ] Populate `match_teams.score` and `match_teams.is_winner` from match results
- [ ] Populate `player_blinds.victim_name` from players table

### Medium-term
- [ ] Run classifier pipeline (`scripts/run_classifiers.py`) to populate classification tables
- [ ] Populate `events` with real HLTV event data (not placeholder)
- [ ] Add HLTV adapter to populate external_team_links, external_match_links, team_aliases, player_aliases
- [ ] Ingest more demos to grow the dataset
- [ ] Implement the swing% computation (currently set to 0 in rating test)
- [ ] Verify PRS snapshot timing fix (round_end_ticks) by re-ingesting

### Long-term
- [ ] Build analyst UI for manual notes
- [ ] Build lineup tool to populate lineups tables
- [ ] Add per-tick game state for deeper analytics (player positions, economy, etc.)
- [ ] Add roster tracking (team_memberships) via HLTV scraping
- [ ] Improve swing% formula accuracy (currently 8.9% mean diff from HLTV)
- [ ] Improve ADR accuracy (PRS undercounts by 10-20% vs HLTV)

---

## Bug Log

| Date | Severity | Description | Status |
|------|----------|-------------|--------|
| recent | HIGH | `match_players` 2 rows with NULL team_side (mezii, apEX in match 12/dust2) | RESOLVED |
| recent | MED | `player_blinds.victim_name` empty string (not populated) | RESOLVED |
| recent | MED | `player_round_weapons.dropped_at_tick` NULL for all rows | OPEN |
| recent | LOW | `events.start_date`/`end_date` NULL (placeholder row) | OPEN |
| recent | LOW | `match_teams.score`/`is_winner` NULL (not populated) | RESOLVED |
| recent | LOW | `matches.canonical_match_json`/`played_at_source` NULL (not populated) | OPEN |
| recent | LOW | `teams.country_code`/`team_type`/`parent_team_id` NULL (not populated) | OPEN |
| recent | FIXED | PRS SMALLINT overflow on cumulative values | RESOLVED (columns widened to INTEGER) |
| recent | FIXED | PlayerBlind 0 events from demoparser (proximity heuristic) | RESOLVED |
| recent | FIXED | GrenadeTrajectory per-tick storage too large (compact summary) | RESOLVED (99.95% size reduction) |
| recent | FIXED | Duplicate demo ingestion (no idempotency) | RESOLVED (SHA256 check) |

## External References (for future use)

- [cs-demo-manager CLI docs](https://cs-demo-manager.com/docs/cli) � A reference for CS2 demo CLI tooling. Useful for cross-checking our demoparser2-based ingest against an independent implementation, and for discovering event types/columns we may be missing.

