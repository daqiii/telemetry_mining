"""Task 1 (from_mac_to_nersc.md, 2026-08-06 'Two things: intra-exposure shear DRIFT + rebuild the
GFA metric' entry): Klaus's insight -- the PMGWCS guide-star shear used for the Q_rot cross-check is
a SINGLE-EPOCH SNAPSHOT, but the loss a star accumulates is intra-exposure-accumulated over the whole
~20-minute exposure. The physically apt quantity for comparing to Kirkby's guide-star-motion-based
estimate (DESI-8586) is therefore the intra-exposure DRIFT of the shear, not a static post-fit residual.

Reuses Test 5's exact per-frame affine-fit machinery (affine_gfa_crossterm_test.py: ETC
`thru/dx_gfa,dy_gfa`, CS5 geometry, per-frame 6-parameter fit tx,ty,s,theta,e1,e2) but instead of the
dipole cross-term keeps the full per-frame (e1(t),e2(t)) shear series and computes its drift relative
to the first frame (t=0, closest to fiber placement): de(t) = e(t) - e(0). Rotates de(t) into the
zenith frame via the exposure's parallactic angle (2q, spin-2 like all shear quantities in this
investigation) BEFORE taking the RMS over frames -- an RMS/motion-based quantity, matching Kirkby's
own guide-star-motion approach, rather than a simple time-mean (which would mostly cancel for a
roughly-symmetric drift).

e1,e2 here are genuine GEOMETRIC shear (CS5 mm positions normalized by Rn=410mm, same convention as
Test 4/5), so -- like the PMGWCS static-shear and dither-quadrupole comparisons elsewhere in this
investigation -- convert DIRECTLY to a physical edge offset (amplitude * Rn), no sigma_eff/quadratic
conversion (that conversion is only needed for Q_rot, which is fit from LOSS/flux data, not from
positions directly).

UPDATED 2026-08-06 (from_mac_to_nersc.md 'Answer: Option 1' entry, step 2/'Complete B'): also tracks the
isotropic SCALE drift `ds(t) = s(t) - s(0)` alongside e1,e2 -- needed downstream by
gfa_fiber_loss_metric_v2.py to build a metric with a real quadrupole (pure shear alone is provably
radial-only, FIBER_LOSS_METRICS.md Sec 3.1). Unlike e1,e2 (spin-2), scale is rotation-invariant, so
mean_ds needs no zenith-frame rotation.
"""
import json
import os
import sys
import time
from multiprocessing import Pool

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

pos = np.array([CS5[c][0] for c in GUIDE_NAMES])
Jmats = np.array([CS5[c][1:, :] for c in GUIDE_NAMES])
R = np.hypot(pos[:, 0], pos[:, 1]).mean()
Xn, Yn = pos[:, 0] / R, pos[:, 1] / R

rows = []
for xi, yi in zip(Xn, Yn):
    rows.append([1, 0, xi, -yi, xi, yi])
    rows.append([0, 1, yi, xi, -yi, xi])
A = np.array(rows, dtype=float)
Apinv = np.linalg.pinv(A)

Rn = 410.0  # mm

DATA_ROOT = '/global/cfs/cdirs/desi/spectro/data'


def fit_exposure_sheardrift(night, expid, parallactic):
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
    params = b @ Apinv.T
    s = params[:, 2]
    e1 = params[:, 4]
    e2 = params[:, 5]

    tmin = tmid / 60.0
    if tmin[-1] - tmin[0] < 1.0:
        return None

    good = np.isfinite(s) & np.isfinite(e1) & np.isfinite(e2)
    if good.sum() < 20:
        return None
    s, e1, e2 = s[good], e1[good], e2[good]

    de1 = e1 - e1[0]
    de2 = e2 - e2[0]
    ds = s - s[0]  # isotropic scale drift -- rotation-invariant, no zenith-frame rotation needed
                   # (unlike e1,e2 which are spin-2); see FIBER_LOSS_METRICS.md Sec 3.1: the DAR
                   # field-differential is scale+shear in equal parts, not shear alone.

    q2 = 2 * np.deg2rad(parallactic)
    c2, s2 = np.cos(q2), np.sin(q2)
    de1_rot = de1 * c2 + de2 * s2
    de2_rot = -de1 * s2 + de2 * c2

    rms_rot = np.sqrt(np.mean(de1_rot ** 2 + de2_rot ** 2))
    rms_fix = np.sqrt(np.mean(de1 ** 2 + de2 ** 2))
    mean_de1_rot = de1_rot.mean()
    mean_de2_rot = de2_rot.mean()
    mean_rot_mag = np.hypot(mean_de1_rot, mean_de2_rot)
    mean_ds = ds.mean()

    return dict(
        nframe=int(good.sum()), duration_min=tmin[-1] - tmin[0],
        rms_rot=rms_rot, rms_fix=rms_fix, mean_rot_mag=mean_rot_mag,
        mean_de1_rot=mean_de1_rot, mean_de2_rot=mean_de2_rot, mean_ds=mean_ds,
    )


def _worker(args):
    eid, night, airmass, parallactic = args
    try:
        r = fit_exposure_sheardrift(night, eid, parallactic)
    except Exception:
        return None
    if r is None:
        return None
    r['EXPID'] = eid
    r['airmass'] = airmass
    r['parallactic'] = parallactic
    return r


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
    sample['night'] = sample.EXPID.map(night_map)
    sample = sample.dropna(subset=['night'])

    jobs = list(zip(sample.EXPID.astype(int), sample.night.astype(int), sample.airmass, sample.parallactic))
    t0 = time.time()
    results = []
    with Pool(16) as pool:
        for i, r in enumerate(pool.imap_unordered(_worker, jobs)):
            if r is not None:
                results.append(r)
            if (i + 1) % 500 == 0:
                elapsed = time.time() - t0
                print(f'  {i+1}/{len(jobs)}  ok={len(results)}  elapsed={elapsed:.0f}s '
                      f'~{elapsed/(i+1)*len(jobs):.0f}s total est.', flush=True)

    print(f'[done] {len(results)} ok / {len(jobs)}, {time.time()-t0:.0f}s total')
    res = pd.DataFrame(results)
    out = '/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_shear_drift.parquet'
    res.to_parquet(out)
    print(f'[out] {out}  ({len(res)} rows)')


if __name__ == '__main__':
    main()
