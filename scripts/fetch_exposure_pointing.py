#!/usr/bin/env python3
"""Fetch per-exposure pointing/timing for the DAR / PlateMaker HA-dependence test.

Reads the exposure list (`data/dar_exposure_list.csv`) and queries the DESI
exposure database (`exposure.exposure`) for the quantities requested in
`DAR_PLATEMAKER_REPORT.md` §7 — RA/Dec, MJD+EXPTIME (or HA), effective exposure
time, and the hexapod rotator info. Run this **at KPNO**, where the `DOS_DB_*`
environment variables point at the mountain database.

DB access reuses the project's own `Exposure` plumbing: `telemetry_mining.config.
Config.default()` (which reads `DOS_DB_HOST / DOS_DB_NAME / DOS_DB_PORT /
DOS_DB_READER / DOS_DB_READER_PASSWORD`) and `telemetry_mining.db.fetch_all`,
querying `exposure.exposure` keyed by `id` — exactly as `Exposure.db_row` does.
A plain-`psycopg2` fallback (same env-var names) kicks in if the package is not
importable.

Workflow
--------
1.  `python scripts/fetch_exposure_pointing.py --discover`
        Prints every column of `exposure.exposure` (with types) and the keys
        inside the `tcs` / `hexapod` jsonb blobs for one sample exposure, so you
        can confirm the real column names.
2.  Edit `PLAIN_COLUMNS` / `JSONB_FIELDS` below to match those names.
3.  `python scripts/fetch_exposure_pointing.py`
        Writes `data/dar_exposure_pointing.csv` (one row per EXPID).

`--limit N` restricts to the first N exposures (handy for a quick test run).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)   # repo root (this script lives in scripts/)
DEFAULT_IN = os.path.join(ROOT, "data", "dar_exposure_list.csv")
DEFAULT_OUT = os.path.join(ROOT, "data", "dar_exposure_pointing.csv")

# ---------------------------------------------------------------------------
# EDIT to match the real `exposure.exposure` schema (run --discover to list it).
# Names below are best-guess DESI conventions and are almost certainly not all
# correct — confirm/rename against your table definition.
#
# Plain top-level columns to copy through verbatim. Unknown names are skipped
# with a warning (so a wrong guess won't crash the run).
PLAIN_COLUMNS = [
    "night",        # observing night (cross-check vs the list)
    "tileid",       # tile / field id
    "date_obs",     # timestamp at exposure start
    "mjd_obs",      # MJD at start        <-- confirm: mjd_obs? mjd? mjd_start?
    "exptime",      # open-shutter seconds
    "airmass",      # cross-check vs our per-exposure value
    "skyra",        # telescope/field RA  <-- confirm: skyra? reqra? targtra? tilera?
    "skydec",       # telescope/field Dec <-- confirm: skydec? reqdec? targtdec? tiledec?
    "ha",           # hour angle if stored <-- confirm; may not exist -> compute from RA+LST later
    "mountha",      # alternative HA name  <-- confirm or delete
    "parallactic",  # parallactic angle (column of exposure.exposure)
    "efftime",      # effective/total-effective exposure time <-- confirm: efftime? totteff? efftime_spec?
]

# jsonb-blob fields: (output_column_name, blob_column, key_inside_blob).
# Per your note, the rotator quantities live in the `tcs` jsonb blob.
JSONB_FIELDS = [
    ("rot_rate",   "tcs", "rot_rate"),      # hexapod rotator update rate
    ("rot_offset", "tcs", "rot_offset"),    # initial rotator position
    # e.g. add ("tcs_targ_ra", "tcs", "targ_ra"), etc. once you see the blob keys
]

BATCH = 1000  # exposures per `id = ANY(%s)` query
# ---------------------------------------------------------------------------


def get_fetcher():
    """Return (fetch_all, label). fetch_all(query, params) -> list[dict]."""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    try:
        from telemetry_mining import db
        from telemetry_mining.config import Config

        cfg = Config.default()

        def fetch_all(query, params=None):
            return db.fetch_all(cfg, query, params)

        return fetch_all, f"telemetry_mining  (site={cfg.site}, host={cfg.db_host or '?'}, db={cfg.db_name or '?'})"
    except Exception as exc:  # fall back to a direct connection with the same env vars
        print(f"[info] telemetry_mining unavailable ({exc!r}); using direct psycopg2", file=sys.stderr)
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(
            dbname=os.environ["DOS_DB_NAME"],
            host=os.environ["DOS_DB_HOST"],
            port=int(os.environ.get("DOS_DB_PORT", "5432") or 5432),
            user=os.environ.get("DOS_DB_READER", ""),
            password=os.environ.get("DOS_DB_READER_PASSWORD", ""),
        )
        conn.autocommit = True

        def fetch_all(query, params=None):
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return [dict(r) for r in cur.fetchall()]

        return fetch_all, f"psycopg2 direct  (host={os.environ.get('DOS_DB_HOST', '?')})"


def load_expids(path):
    with open(path) as fh:
        return [int(row["EXPID"]) for row in csv.DictReader(fh)]


def discover(fetch_all, expid):
    rows = fetch_all("SELECT * FROM exposure.exposure WHERE id = %s LIMIT 1", (expid,))
    if not rows:
        print(f"[discover] no exposure.exposure row for EXPID {expid}")
        return
    row = rows[0]
    print(f"\n=== exposure.exposure columns (sample EXPID {expid}) ===")
    for key in sorted(row):
        val = row[key]
        print(f"  {key:26s} {type(val).__name__:9s} {str(val)[:56]}")
    for blob in ("tcs", "hexapod"):
        b = row.get(blob)
        if isinstance(b, dict):
            print(f"\n=== keys inside '{blob}' jsonb ===")
            for key in sorted(b):
                print(f"  {blob}.{key:22s} {str(b[key])[:56]}")
        elif b is not None:
            print(f"\n[note] column '{blob}' is {type(b).__name__}, not a dict: {str(b)[:80]}")
    print("\nEdit PLAIN_COLUMNS / JSONB_FIELDS to match, then run without --discover.")


def main():
    ap = argparse.ArgumentParser(description="Fetch per-exposure pointing/timing from exposure.exposure.")
    ap.add_argument("--in", dest="inp", default=DEFAULT_IN, help="exposure list CSV (needs an EXPID column)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output CSV path")
    ap.add_argument("--batch", type=int, default=BATCH, help="exposures per DB query")
    ap.add_argument("--limit", type=int, default=None, help="only the first N exposures (test run)")
    ap.add_argument("--discover", action="store_true", help="print available columns / jsonb keys and exit")
    args = ap.parse_args()

    fetch_all, label = get_fetcher()
    print(f"[db] {label}")
    expids = load_expids(args.inp)
    if args.limit:
        expids = expids[: args.limit]
    print(f"[in] {len(expids)} EXPIDs from {args.inp}")

    if args.discover:
        discover(fetch_all, expids[0])
        return

    # Which of the requested plain columns actually exist (check a sample row).
    sample = fetch_all("SELECT * FROM exposure.exposure WHERE id = %s LIMIT 1", (expids[0],))
    have = set(sample[0].keys()) if sample else set()
    plain = [c for c in PLAIN_COLUMNS if c in have]
    missing = [c for c in PLAIN_COLUMNS if c not in have]
    if missing:
        print(f"[warn] not columns of exposure.exposure, skipped: {missing}", file=sys.stderr)
        print("       run with --discover to see the real names, then edit PLAIN_COLUMNS.", file=sys.stderr)

    out_fields = ["EXPID"] + plain + [name for name, _, _ in JSONB_FIELDS]
    n_matched = 0
    with open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields)
        writer.writeheader()
        for i in range(0, len(expids), args.batch):
            chunk = expids[i : i + args.batch]
            rows = fetch_all("SELECT * FROM exposure.exposure WHERE id = ANY(%s)", (chunk,))
            by_id = {r["id"]: r for r in rows}
            for eid in chunk:
                r = by_id.get(eid)
                out = {"EXPID": eid}
                if r is not None:
                    n_matched += 1
                    for c in plain:
                        out[c] = r.get(c)
                    for name, blob, key in JSONB_FIELDS:
                        b = r.get(blob)
                        out[name] = b.get(key) if isinstance(b, dict) else None
                writer.writerow(out)
            print(f"  {min(i + args.batch, len(expids))}/{len(expids)}", flush=True)

    print(f"[out] {args.out}: {n_matched}/{len(expids)} exposures matched in exposure.exposure")
    if n_matched < len(expids):
        print("      (unmatched EXPIDs get an EXPID-only row — expected if any were purged from the DB.)")


if __name__ == "__main__":
    main()
