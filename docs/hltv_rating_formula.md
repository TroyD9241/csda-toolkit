# HLTV3 Rating Formula

> Reverse-engineered from ML analysis with RMSE 0.032, R² 0.991.
> Source: [@n3c1k](https://x.com/n3c1k/status/2071665300689273144)

---

## Per-Round Rating

```
Rating = ((0.33 × KPR) + (0.60 × K/D) + (0.53 × RPI)) × Impact_mult + (0.55 × ADR) + (0.21 × (1 − K/D) × HS%)
```

### Impact Multiplier

```
Impact_mult = e^(0.43 × Impact)

Impact = (2.13 × K/D_ratio) + (0.42 × KPR × 100) + (−1.25 × OK%) + (−0.17)
```

---

## Variable Definitions

| Variable | Full Name | Range | Description |
|---|---|---|---|
| `KPR` | Kills Per Round | 0 – 5 | `kills / rounds_played` |
| `K/D` | Kill/Death Ratio | 0 – ∞ | `kills / deaths` (no upper clamp) |
| `RPI` | Round Participation Index | 0 – 1 | Situational contribution beyond raw kills |
| `ADR` | Average Damage per Round | 0 – 100+ | `total_damage / rounds_played` |
| `HS%` | Headshot Percentage | 0 – 1 | `headshot_kills / total_kills` |
| `Impact` | Impact Score | −∞ – ∞ | Opening-frag-weighted kill quality |
| `Impact_mult` | Impact Multiplier | 0.2 – ~3 | Exponential boost for high-impact players |

---

## Impact Components

### K/D_ratio

```
K/D_ratio = clamp(0, ∞, (OK / TK))

OK  = Opening Kills (kills in first 30 seconds of a round)
TK  = Total Kills in that round
OK% = clamp(0, 1, OK / TK)
```

### Opening Kill % (OK%)

```
OK% = clamp(0, 1, OK / TK)
```

A kill is an **opening kill** if it occurs within the first 30 seconds of the round.

---

## RPI — Round Participation Index

```
RPI = clamp(0, 1,
    (0.41 × oK%) +
    (0.36 × (clutch_won / clutch_played)) +
    (0.23 × util_success)
)
```

| Sub-component | Weight | Description |
|---|---|---|
| `oK%` | 0.41 | Opening kill participation rate |
| `clutch_won / clutch_played` | 0.36 | Clutch win rate (as last alive) |
| `util_success` | 0.23 | Utility effectiveness rate |

### Clutch

```
Clutch = max(0, clutch_won - clutch_lost)

clutch_won  = rounds won as last alive
clutch_lost = rounds lost as last alive
```

---

## ADS — ADR Contribution (dampened)

```
ADS = ADR × (1 / K/D_ratio) × 0.33
```

This is the dampened ADR term — it scales down ADR contribution for high K/D players (who already get a big boost from the K/D term).

---

## Match Rating

```
Match Rating = mean(per-round Ratings)
```

The match rating is the **simple average** of all per-round ratings where the player participated.

---

## Coefficient Summary

| Component | Formula | Weight | Notes |
|---|---|---|---|
| Kill rate | `0.33 × KPR` | 0.33 | Raw frequency of kills |
| Kill efficiency | `0.60 × K/D` | 0.60 | **Heaviest weight** — survival matters |
| Situational value | `0.53 × RPI × Impact_mult` | variable | RPI boosted by impact multiplier |
| Damage output | `0.55 × ADR` | 0.55 | Flat damage contribution |
| Headshot (die-alot) | `0.21 × (1 − K/D) × HS%` | variable | Consolation for low-K/D high-HS players |

---

## ADS (ADR Dampening Factor)

The term `0.21 × (1 − K/D) × HS%` only meaningfully fires when `K/D < 1` — i.e., for players who are dying more than they're killing. It's a headshot consolation score: even if you're losing duels, hitting heads is valuable.

---

## Implementation Notes

### Swing is a Hidden Probabilistic Rating Feature

> "swing itself is a hidden probabilistic rating feature"

**Swing kills** (kills on enemies who are already in a fight / swinging their crosshair) are easy to get and inflate KPR but don't reflect skill. The Impact term indirectly captures this — a player with high KPR but low opening-kill% will have lower Impact, reducing their rating boost from the KPR term.

### Data Requirements

To compute this formula we need from the demo:
- `kills` — with tick timestamps to compute opening kills (< 30s)
- `deaths` — for K/D ratio
- `damage` — for ADR
- `headshot_kills` — for HS%
- `clutch situations` — last alive rounds won/lost (from kill/victim data)
- `utility_damage` — for util_success
- `rounds_played` — for per-round KPR

### Clutch Detection

A clutch is when a player is the **last alive** member of their team in a round. Detected by: the player's team lost all other players before the round ended, and that player either survived or got a kill in the round.

---

## Reference Implementation (Python)

```python
import math

def compute_hltv_rating(
    kills: int,
    deaths: int,
    rounds_played: int,
    adr: float,
    headshot_kills: int,
    opening_kills: int,      # kills in first 30s of round
    total_round_kills: int,  # kills in that specific round (for OK%)
    clutch_won: int,
    clutch_lost: int,
    util_success: float,     # 0–1 utility hit rate
) -> float:
    # KPR
    kpr = kills / rounds_played if rounds_played > 0 else 0.0

    # K/D
    kd = kills / deaths if deaths > 0 else 0.0

    # Headshot %
    hs_pct = headshot_kills / kills if kills > 0 else 0.0

    # OK% (opening kill %)
    ok_pct = opening_kills / total_round_kills if total_round_kills > 0 else 0.0
    ok_pct = max(0.0, min(1.0, ok_pct))

    # K/D ratio (for impact)
    kd_ratio = kd  # K/D_ratio = OK/TK but capped at ∞

    # Impact
    impact = (2.13 * kd_ratio) + (0.42 * kpr * 100) - (1.25 * ok_pct) - 0.17

    # Impact multiplier
    impact_mult = math.exp(0.43 * impact)

    # RPI
    clutch_ratio = clutch_won / (clutch_won + clutch_lost) if (clutch_won + clutch_lost) > 0 else 0.0
    clutch_ratio = max(0.0, min(1.0, clutch_ratio))
    rpi = max(0.0, min(1.0,
        (0.41 * ok_pct) +
        (0.36 * clutch_ratio) +
        (0.23 * util_success)
    ))

    # ADS (dampened ADR)
    ads = adr * (1.0 / kd_ratio) * 0.33 if kd_ratio > 0 else 0.0

    # Full rating
    rating = (
        (0.33 * kpr) +
        (0.60 * kd) +
        (0.53 * rpi) * impact_mult +
        (0.55 * adr) +
        (0.21 * (1.0 - kd) * hs_pct)
    )

    return rating
```
