"""Ingest a single CS2 demo file into the database.

Usage:
    py scripts/ingest_one.py <path-to-demo.dem>
    py scripts/ingest_one.py                       # uses default (mirage demo)

Uses IngestBundle for the full pipeline: demo_file, teams, players, match,
rounds, kills, round_side_map, equipment at freezetime end, purchases,
pickups, bomb events, grenades, infernos, blinds, damage events, PRS,
and weapon drops.
"""
import os
import sys
import time

from csda_toolkit.db.database import Database
from csda_toolkit.ingest.bundle import IngestBundle

DEFAULT_DEMO = r"C:\Users\Troy\csda-toolkit\demos\blast-rivals-2026-season-1-vitality-vs-fut-bo3-9RYfK_Nffwu4TXDghNJDks\vitality-vs-fut-m1-mirage.dem"
DEMO = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DEMO
DB_URL = os.environ.get("DATABASE_URL", "postgresql://csda:csda@localhost:5432/csda")

print(f"DB: {DB_URL}")
print(f"Demo: {DEMO}")

if not os.path.isfile(DEMO):
    print(f"ERROR: demo file not found: {DEMO}")
    sys.exit(1)

db = Database(DB_URL)
bundle = IngestBundle(db, DEMO)

t0 = time.time()
print("\n[Running full IngestBundle pipeline...]")
result = bundle.run()
print(f"\n[DONE] {result} in {time.time()-t0:.1f}s")
