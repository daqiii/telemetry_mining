"""Test 4 (DAR_DIPOLE_NERSC_HANDOFF.md): per-frame affine (translation+rotation+
scale+shear) decomposition of the 6 guide-GFA offset vectors (ETC
`thru/dx_gfa`,`dy_gfa`), tracking the TRANSLATION (boresight) over each exposure
to isolate the intra-exposure drift resid(t) -- the quantity that (per the
"correct placement" reasoning in memory dar-guider-bias-hypothesis) actually
produces the D_rot loss-dipole, as opposed to Test 1's once-per-exposure
acquisition offset (~100-300x too large, dominated by the legitimate bulk
pointing/refraction correction).

Validated on two single exposures first (analysis/dar_dipole/ scratch, not
committed -- see conversation): design-matrix condition number 1.23 (the
co-radial-GFA degeneracy worry does not bite once positions are properly
non-dimensionalized by the GFA-ring radius); ETC-per-GFA rotation has ~1.4-2.1x
lower frame-to-frame scatter than the guider's own per-star `rotation` column
(telemetry.guider_centroids), confirming the noise premise, at both high and
low airmass.

GFA geometry/units/order all confirmed against desietc-master source (uploaded
to trunk root, desietc/gfa.py): dx_gfa/dy_gfa are in PIXELS, ordered by
`GFACamera.guide_names = ['GUIDE0','GUIDE2','GUIDE3','GUIDE5','GUIDE7','GUIDE8']`
(matches exposure.exposure.guide_cameras). `CS5` dict below is copied verbatim
from that source: each camera's nominal CS5 (focal-plane, mm) position plus the
exact pixel->CS5-mm linear (rotation+scale) conversion, from
desimeter.transform.gfa2fp.

Model per frame: dX_i = tx + s*X_i - theta*Y_i + e1*X_i + e2*Y_i
                 dY_i = ty + s*Y_i + theta*X_i + e2*X_i - e1*Y_i
(X_i,Y_i = GFA i's CS5 position, normalized by the ring radius R so all 6
parameters share comparable units -- unnormalized mixes tx,ty (~1) with
s/theta/e1/e2 (~X,Y~400mm) and makes the condition number a scaling artifact,
not a real degeneracy check; see the caveat this test was built to satisfy.)
Design matrix A is IDENTICAL for every frame (only depends on fixed GFA
geometry) so all frames of an exposure are fit in one matrix multiply via a
precomputed pseudo-inverse -- no per-frame Python loop.

Per-exposure "drift" = linear-in-time slope of tx(t), ty(t), theta(t) across
all frames (same precedent as fieldrotationcorrection.ipynb's
rotation_rate_slope -- agreed to keep this simple for now, not a robust fit).
Translation-drift RATE (mm/min) x exposure duration (min) = a total drift
MAGNITUDE (arcsec, via the ~0.070 mm/arcsec focal-plane platescale near the
GFA radius) comparable in scale to D_rot/D_fix. Decomposed into a
"rotating"(zenith/DAR-tied) and "fixed"(instrument-tied) component using the
SAME q-rotation convention as fit_dipole_quadrupole.py (up=tx*cos(q)+ty*sin(q),
vp=-tx*sin(q)+ty*cos(q)) -- appropriate here because CS5 is the same
focal-plane-fixed coordinate family as that script's per-star X/Y, NOT the
RA/Dec sky frame Test 1 used (whose zenith-projection convention doesn't carry
over).

Caveats not addressed here (see conversation): gfadeform.dat's intra-exposure
change is assumed (not verified) negligible; rotation+shear are fit jointly
(never rotation alone) per Kirkby's zero-sum argument, satisfied by construction
of the 6-param model.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, '/global/u1/k/klaushon/telemetry_mining-trunk/src')
from telemetry_mining import db
from telemetry_mining.config import Config

GUIDE_NAMES = ['GUIDE0', 'GUIDE2', 'GUIDE3', 'GUIDE5', 'GUIDE7', 'GUIDE8']

CS5 = {
    'GUIDE0': np.array([
        [9.18450162e+01, -3.97013561e+02],
        [1.42573799e-02, 4.66981235e-03],
        [-4.65492774e-03, 1.41892856e-02]]),
    'GUIDE2': np.array([
        [4.05753952e+02, -3.52939152e+01],
        [4.31199162e-05, 1.50010651e-02],
        [-1.49338639e-02, 3.37050638e-05]]),
    'GUIDE3': np.array([
        [3.48896107e+02, 2.10237056e+02],
        [-8.86064348e-03, 1.21055081e-02],
        [-1.20477346e-02, -8.82590456e-03]]),
    'GUIDE5': np.array([
        [-9.18888483e+01, 3.96855686e+02],
        [-1.42618407e-02, -4.65682022e-03],
        [4.64286359e-03, -1.41935916e-02]]),
    'GUIDE7': np.array([
        [-4.05816895e+02, 3.54535663e+01],
        [-1.00846756e-05, -1.50027231e-02],
        [1.49362446e-02, -1.36688551e-06]]),
    'GUIDE8': np.array([
        [-3.49403148e+02, -2.09911349e+02],
        [8.75839914e-03, -1.21795768e-02],
        [1.21237342e-02, 8.72473620e-03]]),
}

PLATESCALE_MM_PER_ARCSEC = 0.0700  # approx, near GFA radius r~407mm; not desimodel-precise

pos = np.array([CS5[c][0] for c in GUIDE_NAMES])
Jmats = np.array([CS5[c][1:, :] for c in GUIDE_NAMES])  # (6,2,2)
R = np.hypot(pos[:, 0], pos[:, 1]).mean()
Xn, Yn = pos[:, 0] / R, pos[:, 1] / R

rows = []
for xi, yi in zip(Xn, Yn):
    rows.append([1, 0, xi, -yi, xi, yi])
    rows.append([0, 1, yi, xi, -yi, xi])
A = np.array(rows, dtype=float)
cond = np.linalg.cond(A)
Apinv = np.linalg.pinv(A)  # (6,12)
print(f'[setup] design matrix condition number = {cond:.2f} (fixed geometry, same for every exposure)')

DATA_ROOT = '/global/cfs/cdirs/desi/spectro/data'


def fit_exposure(night, expid):
    path = f'{DATA_ROOT}/{night}/{expid:08d}/etc-{expid:08d}.json'
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    thru = d.get('thru')
    if thru is None or 'dx_gfa' not in thru:
        return None
    dx = np.array(thru['dx_gfa'], dtype=float)
    dy = np.array(thru['dy_gfa'], dtype=float)
    if dx.ndim != 2 or dx.shape[1] != 6:
        return None
    nframe = dx.shape[0]
    if nframe < 20:
        return None
    dt1 = np.array(thru['dt1'], dtype=float)
    dt2 = np.array(thru['dt2'], dtype=float)
    tmid = 0.5 * (dt1 + dt2)

    dXmm = np.empty((nframe, 6))
    dYmm = np.empty((nframe, 6))
    for g in range(6):
        dpix = np.stack([dx[:, g], dy[:, g]], axis=1)
        dmm = dpix @ Jmats[g]
        dXmm[:, g] = dmm[:, 0]
        dYmm[:, g] = dmm[:, 1]
    b = np.empty((nframe, 12))
    b[:, 0::2] = dXmm / R
    b[:, 1::2] = dYmm / R
    params = b @ Apinv.T  # (nframe,6): tx',ty',s,theta,e1,e2 (normalized units)
    tx = params[:, 0] * R
    ty = params[:, 1] * R
    theta_arcsec = params[:, 3] * 206265.0

    tmin = tmid / 60.0
    if tmin[-1] - tmin[0] < 1.0:  # need at least ~1 min span for a meaningful slope
        return None
    tx_slope, tx0 = np.polyfit(tmin, tx, 1)
    ty_slope, ty0 = np.polyfit(tmin, ty, 1)
    th_slope, th0 = np.polyfit(tmin, theta_arcsec, 1)
    duration_min = tmin[-1] - tmin[0]

    return dict(
        nframe=nframe, duration_min=duration_min,
        tx_slope_mmpermin=tx_slope, ty_slope_mmpermin=ty_slope,
        theta_slope_arcsecpermin=th_slope,
        tx0_mm=tx0, ty0_mm=ty0,
    )


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
    print(f'[sample] {len(expids)} exposures with airmass>1.4 (matches the D_rot am>1.4 bin)')

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
            r = fit_exposure(night, eid)
        except Exception:
            r = None
        if r is None:
            n_fail += 1
            continue
        r['EXPID'] = eid
        results.append(r)
        n_ok += 1
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(expids)}  ok={n_ok} fail={n_fail}  elapsed={time.time()-t0:.0f}s')

    print(f'[done] {n_ok} ok, {n_fail} failed/skipped, {time.time()-t0:.0f}s total')
    res = pd.DataFrame(results)
    res = res.merge(sample, on='EXPID', how='left')
    out = '/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_test4_drift.parquet'
    res.to_parquet(out)
    print(f'[out] {out}  ({len(res)} rows)')


if __name__ == '__main__':
    main()
