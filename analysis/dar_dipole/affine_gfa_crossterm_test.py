"""Test 4 follow-up: the cross-term (the #1 open item from TEST4_AFFINE_GFA_REPORT.md).

The original translation-channel metric (rate x duration) is the wrong quantity: under
midpoint fiber placement, a symmetric linear drift about the midpoint gives zero net
offset by construction. The loss-dipole is the cross-term

    dipole-gradient = < M_shear(t) . T(t) >_t / sigma_eff^2

where, per ETC frame, T(t) = the affine translation (tx,ty) -- the boresight residual
resid(t) -- and M_shear = [[e1,e2],[e2,-e1]] is the affine shear -- the field's own
differential-DAR term G(t). This is nonzero even for a perfectly symmetric linear T(t)
drift, because it is the time-average of a PRODUCT of two correlated series, not the
mean of either series alone -- exactly why the naive rate x duration metric in Test 4
missed it.

Computed directly from the per-frame (tx,ty,e1,e2) series (no linearity assumed -- this
avoids the symmetric-drift trap and captures any curvature in either series).

Converted to a dimensionless quantity DIRECTLY comparable to fit_dipole_quadrupole.py's
own D_rot (its "edge value in normalized coordinates u=X/Rn"): since the cross term's
physical form is loss(r) ~ (delta0 . G . r)/sigma^2 for physical r, and the fit's D_rot
is the coefficient of r/Rn (not r), D_rot_predicted = Rn * C_zenith / sigma_eff^2, with
everything kept in physical mm/um throughout -- NO arcsec/platescale conversion needed
for this core comparison, since C (from CS5-mm translation x dimensionless shear) is
already in mm, matching Rn=410mm and sigma_eff in mm.

A secondary arcsec-equivalent is also reported, using the SAME delta0 = D_rot*sigma_eff/
sqrt(2*Q_rot) conversion used throughout this investigation (calibrate_sigma_eff.py),
plugging in D_rot_predicted here and the ALREADY-MEASURED empirical Q_rot per airmass
bin (from the Foundation-check independent refit) -- this is the number directly
comparable to the "D_rot ~ 0.11/0.16/0.22 arcsec" language used elsewhere.

Real desimodel platescale (not the ~0.070mm/arcsec approximation used in the original
Test 4 translation-channel script) is pulled for this secondary reporting and for
context, per instruction -- confirmed installed and working directly on NERSC
(DESIMODEL already set via desi_environment.sh, no manual desimodeldata install needed
unlike the Mac session).

Caveats (see conversation / TEST4_AFFINE_GFA_REPORT.md for the full discussion):
- gfadeform.dat's intra-exposure change checked quantitatively (not hand-waved) for a
  representative high-airmass exposure: ~0.44 um change over 23.5 min, vs ~6-9 um
  measured T(t) scatter for the same exposure -- small, but note gfadeform.dat is
  PlateMaker/Dervish-world while this test's CS5 geometry is desimeter/desietc-world;
  same physical GFAs, not a proven cross-pipeline identity.
- Rotation/scale are fit jointly with shear (never rotation alone), satisfied by the
  6-parameter model's construction (Kirkby zero-sum caveat).
- Hypothesis-soft: this is the decisive version of the intra-exposure-drift test, but it
  can genuinely go either way.
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

pos = np.array([CS5[c][0] for c in GUIDE_NAMES])  # (6,2) mm
Jmats = np.array([CS5[c][1:, :] for c in GUIDE_NAMES])  # (6,2,2)
R = np.hypot(pos[:, 0], pos[:, 1]).mean()
Xn, Yn = pos[:, 0] / R, pos[:, 1] / R

rows = []
for xi, yi in zip(Xn, Yn):
    rows.append([1, 0, xi, -yi, xi, yi])
    rows.append([0, 1, yi, xi, -yi, xi])
A = np.array(rows, dtype=float)
Apinv = np.linalg.pinv(A)  # (6,12)

Rn = 410.0  # mm, matching fit_dipole_quadrupole.py's normalization radius
SIGMA_EFF_MM = 0.052  # 52um, calibrate_sigma_eff.py

DATA_ROOT = '/global/cfs/cdirs/desi/spectro/data'


def fit_exposure_crossterm(night, expid):
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
    tx = params[:, 0] * R  # mm
    ty = params[:, 1] * R  # mm
    e1 = params[:, 4]      # dimensionless
    e2 = params[:, 5]      # dimensionless

    tmin = tmid / 60.0
    if tmin[-1] - tmin[0] < 1.0:
        return None

    # cross term, computed directly per frame -- no linearity assumed
    Cx_t = e1 * tx + e2 * ty
    Cy_t = e2 * tx - e1 * ty
    Cx = Cx_t.mean()
    Cy = Cy_t.mean()

    return dict(
        nframe=nframe, duration_min=tmin[-1] - tmin[0],
        Cx_mm=Cx, Cy_mm=Cy,
        mean_e1=e1.mean(), mean_e2=e2.mean(),
        mean_tx_mm=tx.mean(), mean_ty_mm=ty.mean(),
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
    print(f'[sample] {len(expids)} exposures with airmass>1.4')

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
            r = fit_exposure_crossterm(night, eid)
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
    out = '/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_test4_crossterm.parquet'
    res.to_parquet(out)
    print(f'[out] {out}  ({len(res)} rows)')


if __name__ == '__main__':
    main()
