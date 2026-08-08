"""Test 6 (guide != science boresight bias): per-guide-star post-fit astrometric
residuals from the real PlateMaker product `pm-<expid>.fits`, per exposure.

Background: Test 5 showed intra-exposure guiding drift explains only ~3-4% of D_rot
-- not the dominant mechanism. Per the "correct placement" reasoning, the dipole must
then be a STATIC per-exposure offset. The one static, zenith-tied, airmass-growing
offset the guider's closed loop would NOT remove is a guide!=science boresight bias:
the guider nulls the mean of the GUIDE-STAR sample, not the true field center, so if
that sample is a biased DAR estimator, the SCIENCE fibers sit statically off-center.

Source data: every exposure directory (same as desi-<expid>.fits.fz) also has
`pm-<expid>.fits` -- the real PlateMaker product, confirmed to have:
  - PMGSTARS: one row per matched guide star (GFA_LOC, RA, DEC catalog position,
    ROW, COL observed pixel position, MAG, GUIDE_FLAG)
  - PMGWCS: one row per GFA (GFA_LOC as an int 0/2/3/5/7/8, plus a GFA_LOC=99 overall
    field-center entry), giving a standard TAN WCS (CRVAL/CRPIX/CD) -- this WCS has
    ALREADY absorbed the global 4-parameter (translate+rotate+scale) astrometric
    correction (the ~1-40" applied pointing correction Test 1 measured via
    tcs.mount_offset_ra/dec / ocs_gfadata.xi0/eta0 -- NOT what this test measures).

This test computes the LEFTOVER per-star scatter AFTER that correction is applied:
for each star, predict its pixel position from its catalog RA/DEC via the GFA's own
already-corrected WCS, compare to the observed pixel position, and convert the
residual to a sky-frame (RA,Dec-like, arcsec) offset. This is a fundamentally
different, much smaller quantity than the applied correction (confirmed with the
user before scaling up) -- exactly the "post-fit residual" needed to test whether the
guide-star sample is a biased estimator of the true field distortion.

Validated on 2 single exposures before scaling (see conversation): high airmass
(EXPID 360097, am~1.98) mean dDec=-0.85", uniform sign across all 6 GFAs (dipole-like);
low airmass (EXPID 355421, am~1.00) mean dDec=-0.13", mixed sign across GFAs
(quadrupole-like) -- qualitatively exactly the signature hunted for (small/differential
at low airmass, larger/coherent at high airmass). Read speed ~3-30ms/file, fast.

Per-exposure mean (dRA, dDec) [already in arcsec, no platescale conversion needed --
these are sky-frame residuals directly] is decomposed into a zenith-tied ("rotating")
and fixed component using the SAME q-rotation convention as
`analysis/dar_dipole/acquisition_offset_test.py`'s "convention A" (chosen there because
its regression slope matched the right order of magnitude for known atmospheric
refraction): up = dRA*sin(q) + dDec*cos(q), vp = dRA*cos(q) - dDec*sin(q).
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


def star_residuals(night, expid):
    path = f'{DATA_ROOT}/{night}/{expid:08d}/pm-{expid:08d}.fits'
    try:
        f = fitsio.FITS(path)
        gs = f['PMGSTARS'].read()
        wc = f['PMGWCS'].read()
    except Exception:
        return None
    if len(gs) == 0:
        return None
    wcs_by_gfa = {}
    for row in wc:
        gid = int(row['GFA_LOC'])
        if gid == 99:
            continue
        wcs_by_gfa[gid] = row

    resra, resdec = [], []
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
        resra.append(dra)
        resdec.append(ddec)

    if len(resra) < 3:
        return None
    resra = np.array(resra)
    resdec = np.array(resdec)
    return dict(
        n_stars=len(resra),
        mean_dra=resra.mean(), mean_ddec=resdec.mean(),
        std_dra=resra.std(), std_ddec=resdec.std(),
    )


def main():
    cfg = Config.default()
    df = pd.read_parquet('/global/u1/k/klaushon/telemetry_mining-trunk/notebooks/data/dar_calibstars_dataset.parquet',
                          columns=['EXPID', 'airmass'])
    df = df.drop_duplicates('EXPID')
    pt = pd.read_csv('/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_exposure_pointing.csv',
                      usecols=['EXPID', 'parallactic'])
    df = df.merge(pt, on='EXPID', how='inner')
    expids = df.EXPID.tolist()
    print(f'[sample] {len(expids)} exposures (full population, matching Test 1)')

    rows_db = db.fetch_all(cfg, "SELECT id, night FROM exposure.exposure WHERE id = ANY(%s)", (expids,))
    night_map = {r['id']: r['night'] for r in rows_db}

    results = []
    t0 = time.time()
    n_ok = n_fail = 0
    for i, eid in enumerate(expids):
        night = night_map.get(eid)
        if night is None:
            n_fail += 1
            continue
        try:
            r = star_residuals(night, eid)
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
    out = '/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_pmgstars_residuals.parquet'
    res.to_parquet(out)
    print(f'[out] {out}  ({len(res)} rows)')


if __name__ == '__main__':
    main()
