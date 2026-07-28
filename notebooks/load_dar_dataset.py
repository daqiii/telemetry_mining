"""Load the pooled DAR/fiber-flux-loss standard-star dataset.

See `notebooks/data/README.md` for how this dataset was built and what
population it covers. Usage:

    import sys
    sys.path.insert(0, "/global/homes/k/klaushon/telemetry_mining/notebooks")
    from load_dar_dataset import load_dar_calibstars
    df = load_dar_calibstars()
"""
import os

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PARQUET_PATH = os.path.join(DATA_DIR, "dar_calibstars_dataset.parquet")
CSV_PATH = os.path.join(DATA_DIR, "dar_calibstars_dataset.csv.gz")


def load_dar_calibstars(path=None):
    """Return the pooled per-star DAR/fiber-flux-loss dataset as a DataFrame.

    One row per (VALID==1) standard-star measurement from `calibstars`, across
    every DESI DARK/BRIGHT/DARK1B/BRIGHT1B science exposure (totteff>60) this
    was fetched against. Columns: EXPID, FIBER, PETAL (0-9, = FIBER // 500),
    X, Y (focal-plane mm), RCALIBFRAC, loss (= 1 - RCALIBFRAC), radius
    (= sqrt(X**2+Y**2)), airmass, seeing, night.

    `path` overrides the default location; tries the parquet file first (much
    smaller/faster), falls back to the gzipped CSV if parquet isn't available
    (e.g. no pyarrow/fastparquet installed).
    """
    if path is not None:
        if str(path).endswith(".csv.gz") or str(path).endswith(".csv"):
            return pd.read_csv(path)
        return pd.read_parquet(path)
    try:
        return pd.read_parquet(PARQUET_PATH)
    except ImportError:
        return pd.read_csv(CSV_PATH)
