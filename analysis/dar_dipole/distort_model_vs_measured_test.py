"""Test 6 decisive follow-up (Mac Claude's proposal): does the ALREADY-VALIDATED distort.py
DAR model (rotation `rtheta` + differential refraction `f1-f4`), evaluated at the REAL
(imperfectly sampled) guide-star positions from `pm-<expid>.fits`'s PMGSTARS table, reproduce
the measured PMGWCS post-fit residual's coherent mean via ordinary sampling asymmetry?

Physical logic: distort.py has ZERO coherent boresight translation by construction (absolute
refraction explicitly zeroed, folded into a pure ROTATION term instead -- see
docs/DAR_DIPOLE_NERSC_HANDOFF.md's "ruled out" section). A pure rotation, averaged over the 6
GFAs' exact (balanced, antipodal-paired) center positions, cancels to zero. But the guide-star
SAMPLE used in a real exposure is NOT exactly balanced (different star counts per GFA -- e.g.
5/5/5/5/5/5 in one exposure, 1/4/4/5/2/3 in another) -- so the SAMPLE mean of an intrinsically
zero-mean rotation+differential field can be nonzero purely from sampling asymmetry. If this
sampling-induced bias, computed from the SAME real star positions used in the measured-residual
test, reproduces the measured coherent mean (same airmass growth, same zenith/fixed split),
that would mean the whole effect is ordinary incompleteness acting on the ALREADY-VALIDATED,
KNOWN DAR model -- i.e. the surviving "absolute-refraction residual" candidate, caught directly.

distort.py's rtheta computation validated against real `telemetry.ocs_gfadata` production values
for EXPID 360097 (matches to a few percent once the unit convention was resolved -- ocs_gfadata's
rpolar/rprecess/rtheta/rtheta0 are stored in RADIANS, not degrees, unlike xi0/eta0/psi/zd which
are degrees). f1-f4 already validated against the standard DAR formula in `steve_dar_shifts.py`.

IMPORTANT CAVEAT discovered before scaling: per-star differential-DAR scatter is large (~11-14
arcsec std at high airmass, the expected field-edge compression) -- with only ~20-30 stars per
exposure, a SINGLE exposure's sampling-induced mean has a standard error of ~2-2.5 arcsec, far
bigger than the ~0.1-0.9 arcsec signal being compared. A single-exposure eyeball comparison is
not statistically meaningful; this must be done as a population-level (bootstrap) comparison,
exactly like the measured-residual test, using the SAME real star positions/counts per exposure
for both the measured residual and the model-predicted sampling bias.
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
DEG2RAD = np.pi / 180.0
DESI = dict(a0=0.06, b0=1.55, z0=1.93, t0=0.76, b2=0.13, b4=0.04, theta1=-0.07, refract=45.0)


def compute_rtheta(ra, dec, st_deg, ha, mjd):
    i = 23.439
    a0, b0, z0, t0, b2, b4, theta1 = (DESI['a0'], DESI['b0'], DESI['z0'], DESI['t0'],
                                      DESI['b2'], DESI['b4'], DESI['theta1'])
    elong = ((mjd - 56373.0) * (360.0 / 365.25) - 90.0) % 360.0
    rra, rdec, ri = np.radians(ra), np.radians(dec), np.radians(i)
    rha, rlong, rst = np.radians(ha), np.radians(elong), np.radians(st_deg)
    vx = np.cos(rlong); vy = np.sin(rlong) * np.cos(ri); vz = np.sin(rlong) * np.sin(ri)
    px = np.cos(rra) * np.cos(rdec); py = np.sin(rra) * np.cos(rdec); pz = np.sin(rdec)
    ax = py * vz - pz * vy; ay = pz * vx - px * vz; az = px * vy - py * vx
    mx = ay * pz - az * py; my = az * px - ax * pz
    pmra = -1.0 * mx * np.sin(rra) + my * np.cos(rra)
    rthetaaberr = 1.e-4 * pmra * np.tan(rdec)
    dyear = (mjd - 51544.0) / 365.25
    romega = np.radians(125.0 - 19.34 * dyear)
    sinidpsi = (-6.8 / 206265.0) * np.sin(romega)
    deps = (9.2 / 206265.0) * np.cos(romega)
    P = (50.385 / 206265.0) * np.sin(ri) * dyear
    rnutat = (sinidpsi * np.sin(rra) - deps * np.cos(rra)) / np.cos(rdec)
    racp = -1.0 * P * np.sin(rst); rb = P * np.cos(rst)
    rprecess = (-racp * np.cos(rha) - rb * np.sin(rha)) / np.cos(rdec)
    arcmin = (z0 - a0 * np.cos(rha) / np.cos(rdec) - b0 * np.sin(rha) / np.cos(rdec)
              + t0 * np.tan(rdec) + b2 * np.sin(2. * rdec) + b4 * np.sin(4. * rha))
    rpolar = (arcmin / 60.0) * DEG2RAD
    rtheta0 = rprecess + rpolar + rnutat
    rtheta = rtheta0 + theta1 * DEG2RAD + rthetaaberr
    return rtheta


def f1234(zd_deg, psi_deg):
    R = DESI['refract'] / 206265.0
    rzen, rpsi = np.radians(zd_deg), np.radians(psi_deg)
    tz = np.tan(rzen)
    f1 = R * (1 + (np.sin(rpsi) * tz) ** 2)
    f2 = np.sin(rpsi) * np.cos(rpsi) * R * tz ** 2
    f3 = R * (1 + (np.cos(rpsi) * tz) ** 2)
    f4 = f2
    return f1, f2, f3, f4


def tan_project(ra, dec, ra0, dec0):
    rra, rdec = np.radians(ra), np.radians(dec)
    rra0, rdec0 = np.radians(ra0), np.radians(dec0)
    xip = (rra - rra0) * np.cos(rdec0)
    etap = rdec - rdec0
    return np.degrees(xip), np.degrees(etap)


def st_to_deg(st_str):
    h, m, s = st_str.split(':')
    return (float(h) + float(m) / 60.0 + float(s) / 3600.0) / 24.0 * 360.0


def process_exposure(night, expid, raBore, decBore, mountha, zd, psi, mjd, st_deg):
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

    try:
        rtheta = compute_rtheta(raBore, decBore, st_deg, mountha, mjd)
    except Exception:
        return None
    f1, f2, f3, f4 = f1234(zd, psi)
    csth, snth = np.cos(rtheta), np.sin(rtheta)

    resra, resdec, moddxi, moddeta = [], [], [], []
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

        xip, etap = tan_project(star['RA'], star['DEC'], raBore, decBore)
        xi = xip * csth + etap * snth - xip * f1 - etap * f2
        eta = etap * csth - xip * snth - etap * f3 - xip * f4
        moddxi.append((xi - xip) * 3600.0)
        moddeta.append((eta - etap) * 3600.0)

    if len(resra) < 3:
        return None
    resra, resdec = np.array(resra), np.array(resdec)
    moddxi, moddeta = np.array(moddxi), np.array(moddeta)
    return dict(
        n_stars=len(resra),
        mean_dra=resra.mean(), mean_ddec=resdec.mean(),
        model_mean_dxi=moddxi.mean(), model_mean_deta=moddeta.mean(),
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
    print(f'[sample] {len(expids)} exposures')

    rows_db = db.fetch_all(
        cfg,
        "SELECT id, night, st, mountha, zd, reqra, reqdec, mjd_obs FROM exposure.exposure WHERE id = ANY(%s)",
        (expids,))
    meta = {r['id']: r for r in rows_db}
    parallactic_map = dict(zip(df.EXPID, df.parallactic))

    results = []
    t0 = time.time()
    n_ok = n_fail = 0
    for i, eid in enumerate(expids):
        m = meta.get(eid)
        if m is None or m['night'] is None or m['st'] is None:
            n_fail += 1
            continue
        try:
            st_deg = st_to_deg(m['st'])
            r = process_exposure(m['night'], eid, m['reqra'], m['reqdec'], m['mountha'],
                                  m['zd'], parallactic_map[eid],
                                  m['mjd_obs'], st_deg)
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
    out = '/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_distort_model_vs_measured.parquet'
    res.to_parquet(out)
    print(f'[out] {out}  ({len(res)} rows)')


if __name__ == '__main__':
    main()
