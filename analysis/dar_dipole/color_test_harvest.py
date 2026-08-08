"""Standard-star-vs-guide-star color test (Mac Claude proposal): harvest per-star MODEL_COLOR/
DATA_COLOR + TARGET_RA/DEC for the standard-star (calibstars) population, joined with the
existing X/Y/loss/airmass/parallactic data. Feeds Steps A (population color offset), B (DCR
magnitude closure), and C (the decisive within-standard-star color-binned D_rot refit).
"""
import sys
import time

import pandas as pd

sys.path.insert(0, '/global/u1/k/klaushon/telemetry_mining-trunk/src')
from telemetry_mining.query import harvest
from telemetry_mining.config import Config


def fn(exp):
    try:
        cal = exp.calibstars
    except Exception:
        return None
    if cal is None:
        return None
    cal = cal[cal.VALID == 1]
    if len(cal) == 0:
        return None
    try:
        fq = exp.fiberqa_table.reset_index().set_index('FIBER')
    except Exception:
        return None
    merged = cal.join(fq[['TARGET_RA', 'TARGET_DEC']], how='left')
    merged = merged[merged.TARGET_RA.notna()]
    if len(merged) == 0:
        return None
    return merged.reset_index()[['FIBER', 'X', 'Y', 'RCALIBFRAC', 'MODEL_COLOR', 'DATA_COLOR',
                                  'TARGET_RA', 'TARGET_DEC']]


def main():
    cfg = Config.default()
    df = pd.read_parquet('/global/u1/k/klaushon/telemetry_mining-trunk/notebooks/data/dar_calibstars_dataset.parquet',
                          columns=['EXPID', 'airmass'])
    df = df.drop_duplicates('EXPID')
    pt = pd.read_csv('/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_exposure_pointing.csv',
                      usecols=['EXPID', 'parallactic'])
    df = df.merge(pt, on='EXPID', how='inner')
    expids = df.EXPID.tolist()
    print(f'[sample] {len(expids)} exposures')

    t0 = time.time()
    pooled = harvest(expids, fn, config=cfg, concat=True, max_workers=16)
    print(f'{len(pooled)} star rows, {pooled.EXPID.nunique()} exposures, {time.time()-t0:.0f}s')

    pooled = pooled.merge(df, on='EXPID', how='left')
    out = '/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_standardstar_color.parquet'
    pooled.to_parquet(out)
    print(f'[out] {out}')


if __name__ == '__main__':
    main()
