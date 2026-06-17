# CSDA Toolkit

**Python toolkit for CS2 demo analysis** — built on top of our fork of [`LaihoE/demoparser`](https://github.com/LaihoE/demoparser).

## What this is

`csda-toolkit` is a Python-native toolkit that wraps the `demoparser` to provide:
- Direct access to every data point the parser extracts (kills, damage, economy, grenades, bomb events, player positions, etc.)
- Classifiers and analytics (economy, round archetypes, player roles, team tendencies)
- No database bottleneck — parse demos and get data straight into Python

## Fork

The parser fork lives at: `C:\Users\Troy\demoparser\`  
GitHub: `https://github.com/TroyD9241/demoparser`

**Future intent**: We will actively extend this fork to expose additional data points, improve event coverage, and add new parsing capabilities beyond what the upstream `LaihoE/demoparser` provides. The fork is the foundation — everything in this toolkit depends on it.

## Reference Docs

The `*.md` files in this folder are from the original `CSDEMOANALYZER` project. They describe the overall vision:

| Doc | What it covers |
|-----|---------------|
| `project-state.md` | Full current project state — **start here** |
| `architecture.md` | Long-term platform vision |
| `database.md` | DB schema iteration notes |
| `schema-visualizer.md` | ERD of current schema |
| `docker.md` | Local dev setup |

These docs define where we're headed — this toolkit is the new implementation of that vision, built directly on the parser fork without the Postgres bottleneck.

## Quick Start (soon)

```python
# pip install csda-toolkit
from csda_toolkit import DemoParser

demo = DemoParser("path/to/demo.dem")
kills = demo.kills()
damage = demo.damage_events()
economy = demo.round_economies()
```
