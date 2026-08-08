"""Test 6 quadrupole follow-up (Mac Claude's proposal #2, highest-value, pre/post-correction
independent): decompose the guide-star astrometric residual (dRA,dDec vs. sky position, same
data as Test 6) into translation (dipole, already measured) AND its across-GFA/across-star
VARIATION (shear/quadrupole), per exposure -- then compare the shear's edge-scale magnitude to
the ALREADY-ESTABLISHED ΔG table (quad_compare_weiner_kirkby.py: 8.0/11.6/15.5 um at
airmass 1.48/1.69/1.86, matching Weiner DESI-9817 and Kirkby DESI-8586 independently).

This is an internal consistency check that does NOT depend on whether PMGWCS is pre- or
post-mount-correction: if guide stars and science fibers see the SAME differential-DAR field,
the guide-star residual's quadrupole/shear component should match ΔG regardless of what the
guide-star DIPOLE/translation component is referenced to.

Method: per exposure, per star, compute the field-relative tangent-plane position
(xip, etap, degrees, same convention/tan_project as distort_model_vs_measured_test.py),
normalized by the DESI field radius (1.6 deg, matching steve_dar_shifts.py's convention so the
fitted shear directly gives an EDGE value comparable to ΔG). Fit the 6-parameter affine model
(translation + rotation + isotropic scale + shear) exactly as in the CS5-frame Test 4/5 work,
but now in sky coordinates:
    dRA_i  = tx + s*X_i - theta*Y_i + e1*X_i + e2*Y_i
    dDec_i = ty + s*Y_i + theta*X_i + e2*X_i - e1*Y_i
The rotation-invariant shear magnitude sqrt(e1^2+e2^2) is the edge-scale quadrupole/compression
amplitude, directly in arcsec -- no sigma_eff or platescale conversion needed (unlike the
Q_rot -> ΔG conversion used elsewhere), since this is a direct astrometric measurement, not a
loss-based inference.
"""
import sys
import time

import fitsio
import numpy as np
import pandas as pd
from astropy.wcs import WCS

sys.path.insert(0, '/global/u1/k/klaushon/telemetry_mining-trunk/src')
from telemetry_mining import db
from telemetry_mining.config import Config

DATA_ROOT = '/global/cfs/cdirs/desi/spectro/data'
GFA_NUM = {'GUIDE0': 0, 'GUIDE2': 2, 'GUIDE3': 3, 'GUIDE5': 5, 'GUIDE7': 7, 'GUIDE8': 8}
FIELD_RADIUS_DEG = 1.6


def tan_project(ra, dec, ra0, dec0):
    rra, rdec = np.radians(ra), np.radians(dec)
    rra0, rdec0 = np.radians(ra0), np.radians(dec0)
    xip = (rra - rra0) * np.cos(rdec0)
    etap = rdec - rdec0
    return np.degrees(xip), np.degrees(etap)


def fit_exposure_shear(night, expid, raBore, decBore):
    path = f'{DATA_ROOT}/{night}/{expid:08d}/pm-{expid:08d}.fits'
    try:
        f = fitsio.FITS(path)
        gs = f['PMGSTARS'].read()
        wc = f['PMGWCS'].read()
    except Exception:
        return None
    if len(gs) == 0:
        return None
    wcs_by_gfa = {int(row['GFA_LOC']): row for row in wc if int(row['GFA_LOC']) != 99}

    Xs, Ys, dRAs, dDecs = [], [], [], []
    for star in gs:
        if star['GUIDE_FLAG'] != 1:
            continue
        gid = GFA_NUM.get(star['GFA_LOC'])
        if gid is None or gid not in wcs_by_gfa:
            continue
        w = wcs_by_gfa[gid]
        aw = WCS(naxis=2)
        aw.wcs.ctype = ["RA---TAN", "DEC--TAN"]
        aw.wcs.crval = [w['CRVAL1'], w['CRVAL2']]
        aw.wcs.crpix = [w['CRPIX1'], w['CRPIX2']]
        aw.wcs.cd = [[w['CD1_1'], w['CD1_2']], [w['CD2_1'], w['CD2_2']]]
        ra_pred, dec_pred = aw.wcs_pix2world(star['COL'], star['ROW'], 0)
        dra = (float(ra_pred) - star['RA']) * np.cos(np.radians(star['DEC'])) * 3600.0
        ddec = (float(dec_pred) - star['DEC']) * 3600.0
        xip, etap = tan_project(star['RA'], star['DEC'], raBore, decBore)
        Xs.append(xip / FIELD_RADIUS_DEG)
        Ys.append(etap / FIELD_RADIUS_DEG)
        dRAs.append(dra)
        dDecs.append(ddec)

    n = len(Xs)
    if n < 8:   # need enough stars for a stable 6-param fit
        return None
    Xs, Ys = np.array(Xs), np.array(Ys)
    dRAs, dDecs = np.array(dRAs), np.array(dDecs)

    rows = []
    for xi, yi in zip(Xs, Ys):
        rows.append([1, 0, xi, -yi, xi, yi])
        rows.append([0, 1, yi, xi, -yi, xi])
    A = np.array(rows, dtype=float)
    b = np.empty(2 * n)
    b[0::2] = dRAs
    b[1::2] = dDecs
    try:
        params, *_ = np.linalg.lstsq(A, b, rcond=None)
    except Exception:
        return None
    tx, ty, s, theta, e1, e2 = params
    cond = np.linalg.cond(A)
    return dict(n_stars=n, tx=tx, ty=ty, scale=s, theta=theta, e1=e1, e2=e2, cond=cond)


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

    rows_db = db.fetch_all(cfg, "SELECT id, night, reqra, reqdec FROM exposure.exposure WHERE id = ANY(%s)",
                            (expids,))
    meta = {r['id']: r for r in rows_db}

    results = []
    t0 = time.time()
    n_ok = n_fail = 0
    for i, eid in enumerate(expids):
        m = meta.get(eid)
        if m is None or m['night'] is None:
            n_fail += 1
            continue
        try:
            r = fit_exposure_shear(m['night'], eid, m['reqra'], m['reqdec'])
        except Exception:
            r = None
        if r is None:
            n_fail += 1
            continue
        r['EXPID'] = eid
        results.append(r)
        n_ok += 1
        if (i + 1) % 2000 == 0:
            print(f'  {i+1}/{len(expids)}  ok={n_ok} fail={n_fail}  elapsed={time.time()-t0:.0f}s')

    print(f'[done] {n_ok} ok, {n_fail} failed/skipped, {time.time()-t0:.0f}s total')
    res = pd.DataFrame(results)
    res = res.merge(df, on='EXPID', how='left')
    out = '/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_pmgstars_shear.parquet'
    res.to_parquet(out)
    print(f'[out] {out}  ({len(res)} rows)')


if __name__ == '__main__':
    main()
