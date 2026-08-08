"""Test 6 color follow-up (Mac Claude's proposal): does the per-star Test 6 residual correlate
with guide-star COLOR (Gaia BP-RP)? Distinguishes a chromatic/wavelength-mismatch systematic
(a significant slope of residual-vs-color) from a non-chromatic systematic refraction-constant
error (flat vs color, nonzero mean) -- both would explain the ~1.3% systematic refraction error
found in Test 6 (measured zenith-tied slope -0.58"/tan(z) vs ~45" refraction constant), but they
point to different physical fixes.

Per star: residual_zenith = dRA*sin(q) + dDec*cos(q) (same convention as Test 6), divided by that
exposure's tan(z) (well-defined for the am>1.4 sample used here, tan(z)>~0.98) to remove the
known/established airmass dependence -- if the systematic is a fixed FRACTIONAL refraction-constant
error eps(color) = eps0 + eps1*(color-mean), then residual_zenith/tan(z) ~= -R*eps(color), so
regressing (residual_zenith/tan_z) against color gives intercept=-R*eps0 (should reproduce the
already-measured -0.58"/tan(z)) and slope=-R*eps1 (the chromatic term Mac's test is asking for).

Color source: Gaia DR3 "lightweight" healpix catalog (nside=32, nested,
/global/cfs/cdirs/desi/target/gaia_dr3/lightweight/), cross-matched by nearest RA/DEC (validated
to sub-0.01" separation for a real guide star -- these ARE the same Gaia catalog entries, not an
independent astrometric solution).
"""
import sys
import time

import fitsio
import healpy as hp
import numpy as np
import pandas as pd

sys.path.insert(0, '/global/u1/k/klaushon/telemetry_mining-trunk/src')
from telemetry_mining import db
from telemetry_mining.config import Config

DATA_ROOT = '/global/cfs/cdirs/desi/spectro/data'
GAIA_ROOT = '/global/cfs/cdirs/desi/target/gaia_dr3/lightweight'
GFA_NUM = {'GUIDE0': 0, 'GUIDE2': 2, 'GUIDE3': 3, 'GUIDE5': 5, 'GUIDE7': 7, 'GUIDE8': 8}
NSIDE = 32

_gaia_cache = {}


def gaia_color(ra, dec):
    pix = hp.ang2pix(NSIDE, ra, dec, lonlat=True, nest=True)
    if pix not in _gaia_cache:
        path = f'{GAIA_ROOT}/healpix-{pix:05d}.fits'
        try:
            _gaia_cache[pix] = fitsio.read(path, columns=['RA', 'DEC', 'PHOT_BP_MEAN_MAG', 'PHOT_RP_MEAN_MAG'])
        except Exception:
            _gaia_cache[pix] = None
    d = _gaia_cache[pix]
    if d is None or len(d) == 0:
        return None, None
    sep = np.hypot((d['RA'] - ra) * np.cos(np.radians(dec)), d['DEC'] - dec) * 3600.0
    best = np.argmin(sep)
    if sep[best] > 1.0:  # arcsec tolerance
        return None, None
    return d['PHOT_BP_MEAN_MAG'][best] - d['PHOT_RP_MEAN_MAG'][best], sep[best]


def star_rows(night, expid, airmass, parallactic):
    from astropy.wcs import WCS
    path = f'{DATA_ROOT}/{night}/{expid:08d}/pm-{expid:08d}.fits'
    try:
        f = fitsio.FITS(path)
        gs = f['PMGSTARS'].read()
        wc = f['PMGWCS'].read()
    except Exception:
        return []
    if len(gs) == 0:
        return []
    wcs_by_gfa = {int(row['GFA_LOC']): row for row in wc if int(row['GFA_LOC']) != 99}

    rows = []
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
        color, sep = gaia_color(star['RA'], star['DEC'])
        rows.append(dict(EXPID=expid, airmass=airmass, parallactic=parallactic,
                          dra=dra, ddec=ddec, mag=star['MAG'], color=color, gaia_sep=sep))
    return rows


def main():
    cfg = Config.default()
    df = pd.read_parquet('/global/u1/k/klaushon/telemetry_mining-trunk/notebooks/data/dar_calibstars_dataset.parquet',
                          columns=['EXPID', 'airmass'])
    df = df.drop_duplicates('EXPID')
    pt = pd.read_csv('/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_exposure_pointing.csv',
                      usecols=['EXPID', 'parallactic'])
    df = df.merge(pt, on='EXPID', how='inner')
    sample = df[df.airmass > 1.4].copy()
    expids = sample.EXPID.tolist()
    print(f'[sample] {len(expids)} exposures with airmass>1.4')

    rows_db = db.fetch_all(cfg, "SELECT id, night FROM exposure.exposure WHERE id = ANY(%s)", (expids,))
    night_map = {r['id']: r['night'] for r in rows_db}
    am_map = dict(zip(sample.EXPID, sample.airmass))
    par_map = dict(zip(sample.EXPID, sample.parallactic))

    all_rows = []
    t0 = time.time()
    n_ok = n_fail = 0
    for i, eid in enumerate(expids):
        night = night_map.get(eid)
        if night is None:
            n_fail += 1
            continue
        try:
            rows = star_rows(night, eid, am_map[eid], par_map[eid])
        except Exception:
            rows = []
        if not rows:
            n_fail += 1
            continue
        all_rows.extend(rows)
        n_ok += 1
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(expids)}  ok={n_ok} fail={n_fail}  stars={len(all_rows)}  elapsed={time.time()-t0:.0f}s')

    print(f'[done] {n_ok} exposures ok, {n_fail} failed, {len(all_rows)} star rows, {time.time()-t0:.0f}s total')
    res = pd.DataFrame(all_rows)
    out = '/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_pmgstars_color.parquet'
    res.to_parquet(out)
    print(f'[out] {out}')


if __name__ == '__main__':
    main()
