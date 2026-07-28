#!/usr/bin/env python3
"""Match WIYN seeing measurements to DESI exposures -> an EXPID-indexed TableSource.

`WIYN-Seeing-*.cvs` is a timestamped (UT) seeing log from the WIYN telescope at Kitt
Peak -- an *independent* site-seeing monitor near the Mayall (correlated with, but not
identical to, DESI's own seeing). This assigns each DESI exposure the nearest-in-time
WIYN FWHM, within `--max-dt` minutes, and writes `data/wiyn_seeing.csv` (one row per matched
exposure) ready to register as a telemetry_mining TableSource:

    from telemetry_mining import Exposure
    from telemetry_mining.tables import TableSource
    exp = Exposure(expid, table_sources=[TableSource("wiyn_seeing", path="data/wiyn_seeing.csv")])
    row = exp.table_source("wiyn_seeing")          # None if this exposure had no WIYN match
    fwhm = None if row is None else row["WIYN_FWHM"]

(Re)build the table -- e.g. when earlier/later WIYN data becomes available:

    python scripts/build_wiyn_seeing.py --wiyn data/WIYN-Seeing-<file>.cvs --max-dt 30 --out data/wiyn_seeing.csv

Exposure timestamps come from an EXPID / `mjd_obs` / `exptime` table (default
`data/dar_exposure_pointing.csv`, offline; at NERSC query `exposure.exposure` for the same).
Exposures with no WIYN point within `--max-dt` are omitted, so `table_source()` returns
None for them (clean "no WIYN data" semantics) rather than a NaN row.

Matching is nearest-in-time to the exposure **midpoint** (`mjd_obs + exptime/2`).
`WIYN_SOURCE` is kept so you can down-select measurement types downstream
(e.g. drop `Focus`); `WIYN_DT_MIN` is signed (WIYN minus exposure midpoint).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent   # repo root (this script lives in scripts/)
MJD_EPOCH = pd.Timestamp("1858-11-17", tz="UTC")


def load_wiyn(path):
    w = pd.read_csv(path)
    w.columns = [c.strip() for c in w.columns]
    ut = pd.to_datetime(w["UT Date"] + " " + w["UT Time"], utc=True, errors="coerce")
    fwhm = pd.to_numeric(w["FWHM"], errors="coerce")
    w = w.assign(ut=ut, fwhm=fwhm).dropna(subset=["ut", "fwhm"])
    w = w.sort_values("ut").reset_index(drop=True)
    w["mjd"] = (w.ut - MJD_EPOCH) / pd.Timedelta(days=1)
    return w[["ut", "mjd", "fwhm", "Source"]]


def match(exp, wiyn, max_dt_min):
    exp = exp.dropna(subset=["mjd_obs", "exptime"]).copy()
    mid = exp.mjd_obs.values + (exp.exptime.values / 2.0) / 86400.0
    wm = wiyn.mjd.values
    idx = np.clip(np.searchsorted(wm, mid), 1, len(wm) - 1)
    left, right = mid - wm[idx - 1], wm[idx] - mid          # distance to the two bracketing points
    nearest = np.where(left <= right, idx - 1, idx)
    dt_min = (wm[nearest] - mid) * 24 * 60                  # signed minutes (WIYN - exposure midpoint)
    within = np.abs(dt_min) <= max_dt_min
    out = pd.DataFrame({
        "EXPID": exp.EXPID.values,
        "WIYN_FWHM": wiyn.fwhm.values[nearest],
        "WIYN_DT_MIN": np.round(dt_min, 2),
        "WIYN_SOURCE": wiyn.Source.values[nearest],
        "WIYN_UT": pd.to_datetime(wiyn.ut.values[nearest]).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })[within].reset_index(drop=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wiyn", default=str(ROOT / "data" / "WIYN-Seeing-05-13-26.cvs"), help="WIYN seeing log (.cvs/.csv)")
    ap.add_argument("--exposures", default=str(ROOT / "data" / "dar_exposure_pointing.csv"),
                    help="table with EXPID, mjd_obs, exptime columns")
    ap.add_argument("--out", default=str(ROOT / "data" / "wiyn_seeing.csv"), help="output EXPID-indexed CSV")
    ap.add_argument("--max-dt", type=float, default=30.0, help="max |WIYN - exposure| in minutes")
    args = ap.parse_args()

    wiyn = load_wiyn(args.wiyn)
    exp = pd.read_csv(args.exposures)
    print(f"[wiyn] {len(wiyn)} measurements, {wiyn.ut.min():%Y-%m-%d}..{wiyn.ut.max():%Y-%m-%d}")
    print(f"[exp]  {len(exp)} exposures from {args.exposures}")

    print("\nmatch rate vs. max-dt (minutes):")
    for dt in (5, 10, 20, 30, 60):
        n = len(match(exp, wiyn, dt))
        print(f"  <= {dt:3d} min : {n:6d} exposures matched  ({100*n/len(exp):.1f}%)")

    out = match(exp, wiyn, args.max_dt)
    out.to_csv(args.out, index=False)
    print(f"\n[out] {args.out}: {len(out)} exposures matched at max-dt={args.max_dt:.0f} min")
    print(f"      median |dt| = {out.WIYN_DT_MIN.abs().median():.1f} min; "
          f"WIYN_FWHM {out.WIYN_FWHM.min():.2f}..{out.WIYN_FWHM.max():.2f} (median {out.WIYN_FWHM.median():.2f})")
    print("      WIYN_SOURCE breakdown:", dict(out.WIYN_SOURCE.value_counts()))


if __name__ == "__main__":
    main()
