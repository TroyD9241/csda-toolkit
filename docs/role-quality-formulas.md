# Role Quality Score Formulas

> **WARNING: All formulas in this document are INITIAL TUNING and WILL CHANGE.**
> Weights, benchmarks, and detection logic were calibrated from CS2Hype role guides
> and are intentionally approximate. Treat these as starting points, not ground truth.

---

## Scoring Architecture

Each role has three components:

1. **Profile dataclass** — raw metric counters (produced by `_build_*_profile()`)
2. **Detection logic** — rules for incrementing counters from event data
3. **Score function** — weighted formula mapping raw metrics → 0–1 quality score

Score function pattern: `component_score = min(1.0, raw_rate / benchmark)`
This means the score is **capped at 1.0** and reaches 1.0 only when the benchmark is hit.

---

## Entry Fragger

### Detection
- **Entry attempt**: Round where player got the first kill OR died first as the apparent first attacker
- **Successful entry**: Entry attempt where player got at least one kill
- **Flash-pop kill**: A kill preceded by a teammate's flashbang within 3 seconds (384 ticks @ 128 tick)
- **Opening duel win**: Player got the first kill of the round
- **Survived post-entry**: Player got at least one kill AND did not die that round

### Score Formula

```
entry_kill_rate     = successful_entries / entry_attempts
entry_kill_score    = min(1.0, entry_kill_rate / 0.40)       # benchmark: 40%

flash_pop_ratio     = flash_pop_kills / successful_entries
flash_pop_score     = min(1.0, flash_pop_ratio / 0.50)        # benchmark: 50%

survival_rate       = rounds_survived_post_entry / successful_entries
survival_score      = min(1.0, survival_rate / 0.60)          # benchmark: 60%

opening_duel_rate   = opening_duel_wins / entry_attempts
opening_duel_score  = min(1.0, opening_duel_rate / 0.50)       # benchmark: 50%

quality = 0.40 * entry_kill_score
        + 0.20 * flash_pop_score
        + 0.20 * survival_score
        + 0.20 * opening_duel_score
```

### Benchmarks
| Signal | Benchmark | Meaning |
|--------|-----------|---------|
| Entry kill rate | 40% | Every ~2.5 entry attempts = 1 kill |
| Flash-pop ratio | 50% | Half of entry kills are flash-assisted |
| Survival post-entry | 60% | Survive 3 out of 5 entry rounds |
| Opening duel win | 50% | Win half of opening duels |

---

## AWP Per

### Detection
- **AWP round**: Round where player equipped AWP (weapon_events contains AWP)
- **First pick**: AWP kill was the first kill of the round globally
- **CT hold pick**: CT-side first pick where player survived the round
- **T-side first pick**: T-side first pick round (estimated: tick < 10,000 = CT side)
- **Utility synergy**: Teammate flash within 3 seconds before an AWP kill
- **AWP save**: Survived a lost round with the AWP alive
- **AWP death on eco**: Died while holding AWP on eco/force round

### Score Formula

```
pick_rate        = first_pick_rounds / awp_rounds
pick_score       = min(1.0, pick_rate / 0.35)               # benchmark: 35%

ct_surv_rate     = ct_survived_after_pick / ct_hold_picks
ct_score         = min(1.0, ct_surv_rate / 0.60)            # benchmark: 60%

t_rounds         = awp_rounds // 2                           # NOTE: rough estimate
t_pick_rate      = t_first_pick_rounds / max(1, t_rounds)
t_score          = min(1.0, t_pick_rate / 0.25)             # benchmark: 25%

total_econ       = awp_saves + awp_deaths_on_eco
save_rate        = awp_saves / total_econ
save_score       = min(1.0, save_rate / 0.70)               # benchmark: 70%

quality = (pick_score + ct_score + t_score + save_score) / 4
```

### Benchmarks
| Signal | Benchmark | Meaning |
|--------|-----------|---------|
| Opening pick rate | 35% | First pick every ~3 AWP rounds |
| CT survival rate | 60% | "Get one, fall back" discipline |
| T-side first pick | 25% | Aggressive opening picks on T |
| Save rate | 70% | Keep AWP alive on lost eco rounds |

### Known Issues
- **CT/T split** is estimated from tick alone (`< 10000` = CT side). Position data would be more accurate.
- **T rounds** are approximated as `awp_rounds // 2`.

---

## Support

### Detection
- **Support round**: Round where player threw at least one utility
- **Trade opportunity**: A teammate died first in the round (player was positioned to trade)
- **Successful trade**: Got a kill within 5 seconds (640 ticks @ 128 tick) of teammate's death
- **Flash-assisted kill**: Teammate flash within 3 seconds before player's kill
- **Economy sacrifice round**: Player saved money on eco/force for team's benefit
  *(Note: not currently tracked in `build_player_role_signals` — counter is always 0)*

### Score Formula

```
trade_rate       = successful_trades / trade_opportunities
trade_score      = min(1.0, trade_rate / 0.70)              # benchmark: 70%

total_kills      = successful_trades + entry_kills_when_needed + 1
flash_rate       = flash_assisted_kills / max(1, total_kills)
flash_score      = min(1.0, flash_rate / 0.30)              # benchmark: 30%

util_rate        = utility_rounds / support_rounds
util_score       = min(1.0, util_rate / 0.80)               # benchmark: 80%

eco_rate         = economy_sacrifice_rounds / support_rounds
eco_score        = min(1.0, eco_rate / 0.20)               # benchmark: 20%

quality = 0.35 * trade_score
        + 0.25 * flash_score
        + 0.20 * util_score
        + 0.20 * eco_score
```

### Benchmarks
| Signal | Benchmark | Meaning |
|--------|-----------|---------|
| Trade success rate | 70% | Good support converts 7/10 trade opportunities |
| Flash assist rate | 30% | Flash teammate on 30% of kills |
| Utility engagement | 80% | Throwing utility in 8/10 rounds |
| Economy sacrifice | 20% | Willing to save 1/5 rounds for team |

### Known Issues
- **Economy sacrifice** counter is not currently populated by `build_support_profile`.

---

## Rifler

### Detection
- **Rifle round**: Round where player used a rifle (AK-47, M4A4, M4A1-S, SG 553, Galil, FAMAS, SCAR-L)
- **Multi-kill round**: 2+ kills in the same round
- **Trade kill**: Kill within 5 seconds of a teammate dying (CT side: victim is not player)
- **Headshot kill**: Kill marked with `headshot=True`
- **CT anchor round**: CT-side rifle round with kills, player survived (tick < 10,000)
- **Clutch round**: Rifle round with kills and no deaths (simplified detection)

### Score Formula

```
multi_kill_rate  = multi_kill_rounds / rifler_rounds
multi_kill_score  = min(1.0, multi_kill_rate / 0.30)        # benchmark: 30%

trade_rate       = trade_kills / rifler_rounds
trade_score      = min(1.0, trade_rate / 0.25)              # benchmark: 25%

hs_score         = min(1.0, headshot_rate / 0.40)          # benchmark: 40%

anchor_rate      = ct_survived_anchor / ct_site_anchor_rounds
anchor_score     = min(1.0, anchor_rate / 0.70)             # benchmark: 70%

quality = (multi_kill_score + trade_score + hs_score + anchor_score) / 4
```

### Benchmarks
| Signal | Benchmark | Meaning |
|--------|-----------|---------|
| Multi-kill rate | 30% | 2+ kills in 3/10 rounds |
| Trade rate | 25% | Trade 1/4 rounds |
| Headshot rate | 40% | HS on 40% of kills (top tier) |
| CT anchor survival | 70% | Stay alive on site anchor rounds |

### Known Issues
- **CT anchor detection** uses tick heuristic (`< 10000`).
- **Clutch detection** is a placeholder — all `rk and not rd` rounds count as clutch wins.

---

## Lurker

### Detection
- **Lurk attempt**: Round where player was in a flank/mid_control/anchor zone (from position_classifications), OR killed late in the round (> tick 15,000) after the round was already engaged
- **Solo kill**: Kill in a lurk attempt round
- **Rotation cut kill**: Kill in lurk attempt (currently same as solo_kill — see issues)
- **Flank kill**: Kill in lurk attempt (currently same as solo_kill — see issues)
- **Survived lurk round**: Lurk attempt where player did not die
- **Clutch round**: Lurk attempt with kills and at least one teammate dead (player is last alive)

### Score Formula

```
solo_rate        = solo_kills / lurk_attempts
solo_score       = min(1.0, solo_rate / 0.40)               # benchmark: 40%

survival_rate    = survived_lurk_rounds / lurk_attempts
survival_score   = min(1.0, survival_rate / 0.55)           # benchmark: 55%

rotation_rate    = rotation_cut_kills / lurk_attempts
rotation_score   = min(1.0, rotation_rate / 0.30)           # benchmark: 30%

clutch_rate      = clutch_rounds_won / clutch_rounds
clutch_score     = min(1.0, clutch_rate / 0.45)            # benchmark: 45%

quality = 0.30 * solo_score
        + 0.25 * survival_score
        + 0.20 * rotation_score
        + 0.25 * clutch_score
```

### Benchmarks
| Signal | Benchmark | Meaning |
|--------|-----------|---------|
| Solo kill rate | 40% | Get a kill in 4/10 lurk attempts |
| Survival rate | 55% | Wait for right timing, don't int |
| Rotation cut rate | 30% | Cut rotations in 3/10 lurk attempts |
| Clutch win rate | 45% | Win nearly half of 1vX situations |

### Known Issues
- **Lurk detection** is heuristic (late tick > 15,000). Position zone data is more accurate when available.
- **Solo kills, rotation cuts, flank kills** are currently all the same counter (`solo_kills`). They should be distinguished once position data is available.
- **Clutch detection** is a rough approximation — any lurk round with kills and teammate deaths counts as clutch won.

---

## Global Notes

### Tick Conversions
| Real Time | Ticks @ 128 tick |
|-----------|-----------------|
| 1 second | ~128 ticks |
| 3 seconds | ~384 ticks |
| 5 seconds | ~640 ticks |
| 8 seconds | ~1024 ticks |

### Score Interpretation
| Range | Label |
|-------|-------|
| 0.75 – 1.00 | Elite |
| 0.50 – 0.75 | Solid |
| 0.30 – 0.50 | Average |
| 0.00 – 0.30 | Liability |

### Missing Data
These signals require data that `build_player_role_signals` does not currently compute:
- **Trade frag tracking** — who killed who in what order (needed for clean trade detection)
- **Clutch situations** — whether player was truly last alive (needs team death data)
- **Economy sacrifice** — when player saved vs bought (needs economy event data)
- **Flash-pop attribution** — which teammate's flash assisted which kill (needs kill-flash pairing)

### Position Data
All roles benefit significantly from `position_classifications` data, which provides:
- Zone-level positioning (a_anchor, b_anchor, mid_control, flanker)
- Side detection (CT vs T) without tick heuristics
- Solo/isolated position detection for lurkers
