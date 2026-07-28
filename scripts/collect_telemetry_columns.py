#!/usr/bin/env python3
"""Collect column listings for the "important telemetry tables" appendix of docs/FIELDS.md.

The main glossary (docs/FIELDS.md) only covers the handful of telemetry tables this
project actually queries. This helper dumps the *column list* (not every value) for a
curated set of additional telemetry tables, so they can be added to FIELDS.md as a
reference appendix -- most column names are self-descriptive, so we don't annotate each.

WORKFLOW (you run steps 2-3 where the DB is reachable -- the same env in which
`telemetry_mining.db.fetch_all` already works for you):
  1. Edit TABLES below to the full list you want in the appendix.
  2. Run:  PYTHONPATH=src python3 scripts/collect_telemetry_columns.py
     (or just `python3 scripts/collect_telemetry_columns.py` if telemetry_mining is installed)
  3. Paste the contents of the written file (telemetry_appendix_columns.json) back into
     the Claude session and ask it to format the FIELDS.md appendix.

It needs ONLY the database -- no files, no NERSC compute. `shared_variable` is carried
through purely as a human label; `tablename` is what gets queried in the telemetry schema.
"""
import json
import re
import sys

from telemetry_mining import Config, db

# ---- EDIT THIS LIST: the tables to include in the appendix ------------------
# (the 7 you supplied are here as a starting point -- add the rest)
TABLES = [
    {'shared_variable': 'TELEMETRY_LIMITS',      'tablename': 'telemetry_limits'},
    {'shared_variable': 'GFA_TELEMETRY',         'tablename': 'gfa_telemetry'},
    {'shared_variable': 'GFA_STATUS',            'tablename': 'gfa_status'},
    {'shared_variable': 'CALIBRATION_TELEMETRY', 'tablename': 'calibration_telemetry'},
    {'shared_variable': 'PC_TELEMETRY',          'tablename': 'pc_telemetry'},
    {'shared_variable': 'PC_TELEMETRY-CAN-FID',  'tablename': 'pc_telemetry_can_fid'},
    {'shared_variable': 'PC_TELEMETRY-CAN-ALL',  'tablename': 'pc_telemetry_can_all'},
    # ... add the rest of your list here ...
]

SCHEMA = 'telemetry'          # change if a table lives in another schema
FETCH_EXAMPLES = True         # also grab ONE sample row per table for example values
                              #   (set False for a smaller paste-back / faster run)
OUT_PATH = 'telemetry_appendix_columns.json'

CFG = Config.default()
_IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')   # guard the f-string identifier below


def truncate(v, n=52):
    s = str(v).replace('\n', ' ').replace('\r', ' ')
    return s if len(s) <= n else s[: n - 3] + '...'


def collect(tablename):
    """Return (columns, error). columns = [[name, data_type, example], ...] in table order."""
    cols = db.fetch_all(
        CFG,
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
        (SCHEMA, tablename),
    )
    if not cols:
        return None, f"no columns found -- table '{SCHEMA}.{tablename}' does not exist?"

    example = {}
    if FETCH_EXAMPLES and _IDENT.match(tablename):
        try:
            row = db.fetch_one(CFG, f"SELECT * FROM {SCHEMA}.{tablename} LIMIT 1")
            if row:
                example = {k: truncate(v) for k, v in row.items()}
        except Exception:
            example = {}          # example values are a bonus; never fail the run over them

    columns = [[c["column_name"], c["data_type"], example.get(c["column_name"], "")] for c in cols]
    return columns, None


results = []
for entry in TABLES:
    name = entry["tablename"]
    print(f"... {SCHEMA}.{name}", file=sys.stderr)
    try:
        columns, err = collect(name)
    except Exception as e:
        columns, err = None, f"{type(e).__name__}: {e}"
    results.append({
        "shared_variable": entry.get("shared_variable", ""),
        "tablename": name,
        "ncols": len(columns) if columns else 0,
        "error": err,
        "columns": columns or [],
    })

with open(OUT_PATH, "w") as f:
    json.dump(results, f, indent=1)

ok = sum(1 for r in results if not r["error"])
total_cols = sum(r["ncols"] for r in results)
print(f"\nWrote {OUT_PATH}: {ok}/{len(results)} tables OK, {total_cols} columns total.",
      file=sys.stderr)
bad = [r["tablename"] for r in results if r["error"]]
if bad:
    print(f"  {len(bad)} had errors (recorded in the file): {', '.join(bad)}", file=sys.stderr)
print("Now paste the contents of that file back into the Claude session.", file=sys.stderr)
