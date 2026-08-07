#!/usr/bin/env python3
"""Build an EXPID-indexed fiber-loss-metrics table (L_see, L_field) -> a telemetry_mining TableSource.

This is the *precompute* path -- for a site (e.g. KPNO) or context where the direct
`Exposure.L_see` / `Exposure.L_field` computation can't run because the offline inputs aren't
available. Where those inputs *are* available (NERSC), you don't need this file at all: `exp.L_see`
computes directly. The metrics themselves are documented in docs/FIBER_LOSS_METRICS.md; the actual
computation lives in `telemetry_mining.fiber_loss` and is shared with `Exposure`, so this table and
the live attribute can never disagree.

  L_see   whole-array SEEING loss level = 1 - A(sigma, 0) / A(sigma_ref, 0), from the offline GFA
          seeing (FWHM_ASEC). Covers every exposure with valid GFA seeing.
  L_field FIELD-distortion (DAR) loss = mean over the focal plane of [1 - A(sigma, |G.r|)/A(sigma,0)],
          from the ETC per-frame scale+shear DRIFT. Covers only exposures with a computed drift.
          Reliable for detection/relative use at all airmass; absolute magnitude approximate above
          am ~ 1.8 (docs Sec 3.3).

REGISTER as a telemetry_mining TableSource (parquet -> the built-in `path=` loader now handles
.parquet directly):

    from telemetry_mining import Exposure
    from telemetry_mining.tables import TableSource, DEFAULT_TABLE_SOURCES

    FLM = TableSource("fiber_loss_metrics", path="data/fiber_loss_metrics.parquet", index_column="EXPID")
    DEFAULT_TABLE_SOURCES.append(FLM)          # process-wide, so every Exposure() sees it
    exp = Exposure(expid)
    exp.L_see, exp.L_field                       # <- served from the table where direct compute can't run

Once registered, `exp.L_see` / `exp.L_field` try the direct computation first and fall back to this
table automatically -- so the same attribute works at NERSC (direct) and KPNO (table).

INPUTS (both offline products -- this is why the metrics aren't available live at KPNO):
  --seeing : table with EXPID, FWHM_ASEC (offline GFA reconstruction seeing). Default
             data/dar_gfa_seeing_level.parquet (or query the offline GFA summary directly).
  --drift  : table with EXPID, mean_ds, mean_de1_rot, mean_de2_rot (intra-exposure scale+shear drift),
             from analysis/dar_dipole/shear_drift_test.py. Default data/dar_shear_drift.parquet.
             Rebuild/extend it (over all exposures, not just am>1.4) to widen L_field coverage.

REBUILD:
    python scripts/build_fiber_loss_metrics.py \
        --seeing data/dar_gfa_seeing_level.parquet \
        --drift  data/dar_shear_drift.parquet \
        --out    data/fiber_loss_metrics.parquet
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent   # repo root (this script lives in scripts/)
sys.path.insert(0, str(ROOT / "src"))
from telemetry_mining import fiber_loss as fl   # noqa: E402  (single source of truth for the math)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeing", default=str(ROOT / "data" / "dar_gfa_seeing_level.parquet"),
                    help="table with EXPID, FWHM_ASEC (offline GFA seeing)")
    ap.add_argument("--drift", default=str(ROOT / "data" / "dar_shear_drift.parquet"),
                    help="table with EXPID, mean_ds, mean_de1_rot, mean_de2_rot (ETC scale+shear drift)")
    ap.add_argument("--out", default=str(ROOT / "data" / "fiber_loss_metrics.parquet"),
                    help="output EXPID-indexed table (.parquet or .csv)")
    ap.add_argument("--grid", type=int, default=25, help="field-grid resolution per axis for L_field")
    args = ap.parse_args()

    # this script must be able to compute -- fail loudly if desimodel/data is missing
    if fl.l_see_from_fwhm(1.1) is None:
        raise SystemExit("desimodel (FastFiberAcceptance + platescale) unavailable -- set DESIMODEL and "
                         "install the data; this precompute script cannot run without it.")

    # ---- L_see (every exposure with valid GFA seeing) ----
    see = pd.read_parquet(args.seeing)
    if "FWHM_ASEC" not in see.columns:
        raise SystemExit(f"--seeing table needs a FWHM_ASEC column (has {list(see.columns)})")
    see = see[["EXPID", "FWHM_ASEC"]].drop_duplicates("EXPID")
    see = see[np.isfinite(see.FWHM_ASEC) & (see.FWHM_ASEC > 0)].copy()
    see["L_see"] = [fl.l_see_from_fwhm(f) for f in see.FWHM_ASEC.values]
    print(f"L_see: {see.L_see.notna().sum()} exposures")

    # ---- L_field (only where the drift table has coverage) ----
    dr = pd.read_parquet(args.drift)
    need = {"EXPID", "mean_ds", "mean_de1_rot", "mean_de2_rot"}
    if not need.issubset(dr.columns):
        raise SystemExit(f"--drift table needs {sorted(need)} (has {list(dr.columns)})")
    dr = dr[["EXPID", "mean_ds", "mean_de1_rot", "mean_de2_rot"]].drop_duplicates("EXPID")
    df = see.merge(dr, on="EXPID", how="left")
    df["L_field"] = [
        fl.l_field_from_drift(ds, e1, e2, f, grid_n=args.grid) if np.isfinite(ds) else None
        for ds, e1, e2, f in zip(df.mean_ds, df.mean_de1_rot, df.mean_de2_rot, df.FWHM_ASEC)
    ]
    print(f"L_field: {df.L_field.notna().sum()} exposures with drift coverage "
          f"({df.L_field.isna().sum()} L_see-only)")

    out = df[["EXPID", "L_see", "L_field"]].sort_values("EXPID").reset_index(drop=True)
    outpath = Path(args.out)
    (out.to_csv(outpath, index=False) if outpath.suffix.lower() == ".csv" else out.to_parquet(outpath))
    print(f"[out] {outpath}: {len(out)} rows "
          f"(L_see finite: {out.L_see.notna().sum()}, L_field finite: {out.L_field.notna().sum()})")


if __name__ == "__main__":
    main()
