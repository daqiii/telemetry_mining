"""Mac Claude's Test 1 (from_mac_to_nersc.md, 2026-08-06 'SHARPER lead' entry): does the
flat_to_psf point-source aperture correction applied inside select_calib_stars.py -- which
divides flux by fiber_frac(DELTA_X, DELTA_Y) at a fixed 1.1" seeing -- itself carry a
zenith-tied, airmass-growing dipole? If so, that correction step (data-side, not the stellar
model) could be manufacturing D_rot out of a DELTA field the dither's actual-light measurement
says has none (dither result: no rotating dipole in the real fiber-to-light offset).

No re-reduction needed: DELTA_X/DELTA_Y/FIBER_X/FIBER_Y are already available per-exposure via
`Exposure.fiberqa_table` (one lightweight whole-focal-plane QA file per exposure), confirmed
byte-identical to the frame.fibermap columns flat_to_psf_flux_correction actually reads (checked
against cframe_table('r0') for exposure 349792, 500/500 fibers, max|diff|=0.0).

Reimplements flat_to_psf_flux_correction's exact formula (desispec/fiberfluxcorr.py) rather than
importing it, because that function wants an astropy Table fibermap with FIBER_X/Y column
mutation semantics -- trivial vectorized numpy version here, formula copied verbatim:
  isotropic_platescale = interp(FIBER_X^2+FIBER_Y^2, ps.radius^2, sqrt(ps.radial*ps.az))  [um/arcsec]
  sigma_um = seeing_fwhm/2.35 * isotropic_platescale
  offset_um = sqrt(DELTA_X^2+DELTA_Y^2)*1000
  fiber_frac = FastFiberAcceptance().value("POINT", sigma_um, offset_um)
  correction = 1/fiber_frac/isotropic_platescale^2   (normalize=False, matching select_calib_stars)

Fit target: y = -log(correction), demeaned per exposure -- same sign/log convention as comparing
against `loss` (higher correction -> higher RCALIBFRAC -> lower loss), using the SAME
affine_fit_lib decomposition as fit_dipole_quadrupole.py, on the SAME calibstars
(EXPID, FIBER, X, Y, airmass) sample so this is an apples-to-apples comparison to the
established D_rot/Q_rot amplitudes.
"""
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, 'src')
sys.path.insert(0, 'analysis/dar_dipole')
from telemetry_mining.exposure import Exposure
from telemetry_mining.config import Config
from affine_fit_lib import fit_and_bootstrap

from desimodel.fastfiberacceptance import FastFiberAcceptance
from desimodel.io import load_platescale

FA = FastFiberAcceptance()
PS = load_platescale()
SEEING_FWHM = 1.1  # arcsec, hardcoded in select_calib_stars.py


def psf_correction(fiber_x, fiber_y, delta_x, delta_y):
    r2 = fiber_x ** 2 + fiber_y ** 2
    isotropic_platescale = np.interp(r2, PS['radius'] ** 2, np.sqrt(PS['radial_platescale'] * PS['az_platescale']))
    sigma_um = SEEING_FWHM / 2.35 * isotropic_platescale
    offset_um = np.sqrt(delta_x ** 2 + delta_y ** 2) * 1000.
    fiber_frac = FA.value('POINT', sigma_um, offset_um)
    ok = fiber_frac > 0.01
    corr = np.full(len(fiber_x), np.nan)
    corr[ok] = 1. / fiber_frac[ok] / isotropic_platescale[ok] ** 2
    return corr


def fetch_deltas(cfg, expid, night):
    exp = Exposure(int(expid), int(night), config=cfg)
    fq = exp.fiberqa_table
    if fq is None:
        return None
    fq = fq.reset_index()
    return fq[['FIBER', 'FIBER_X', 'FIBER_Y', 'DELTA_X', 'DELTA_Y']]


def _fetch_worker(args):
    expid, night = args
    cfg = Config.default()
    fq = fetch_deltas(cfg, expid, night)
    if fq is None:
        return None
    fq = fq.copy()
    fq['EXPID'] = expid
    return fq


def build_dataset(n_exposures=None, seed=0, n_workers=16):
    cal = pd.read_parquet('notebooks/data/dar_calibstars_dataset.parquet',
                           columns=['EXPID', 'FIBER', 'X', 'Y', 'airmass', 'night'])
    exps = cal.drop_duplicates('EXPID')[['EXPID', 'night']]
    if n_exposures is not None and n_exposures < len(exps):
        exps = exps.sample(n_exposures, random_state=seed)
    print(f'fetching DELTA/FIBER_X/Y for {len(exps)} exposures via fiberqa_table ({n_workers}-way parallel)...')

    jobs = list(zip(exps.EXPID.astype(int), exps.night.astype(int)))
    t0 = time.time()
    chunks = []
    n_ok = 0
    with Pool(n_workers) as pool:
        for i, fq in enumerate(pool.imap_unordered(_fetch_worker, jobs, chunksize=20)):
            if fq is not None:
                chunks.append(fq)
                n_ok += 1
            if (i + 1) % 2000 == 0:
                elapsed = time.time() - t0
                print(f'{i+1}/{len(exps)} exposures ({n_ok} ok), {elapsed:.0f}s elapsed, '
                      f'~{elapsed/(i+1)*len(exps):.0f}s total est.', flush=True)
    print(f'done: {n_ok}/{len(exps)} exposures fetched, {time.time()-t0:.0f}s')

    delta_df = pd.concat(chunks, ignore_index=True)
    merged = cal.merge(delta_df, on=['EXPID', 'FIBER'], how='inner')
    print(f'merged calibstars x fiberqa: {len(merged)} star-exposure rows '
          f'({len(cal)} calibstars rows, {merged.EXPID.nunique()} exposures matched)')
    return merged


def main():
    df = build_dataset(n_exposures=None)  # full population -- fiberqa reads are cheap (~0.1s each)
    df.to_parquet('data/dar_flat_to_psf_deltas.parquet')

    pt = pd.read_csv('data/dar_exposure_pointing.csv', usecols=['EXPID', 'parallactic'])
    df = df.merge(pt, on='EXPID', how='inner')

    df['psf_corr'] = psf_correction(df.FIBER_X.values, df.FIBER_Y.values, df.DELTA_X.values, df.DELTA_Y.values)
    df = df[np.isfinite(df['psf_corr']) & (df['psf_corr'] > 0) &
            np.isfinite(df.X) & np.isfinite(df.Y) & np.isfinite(df.parallactic) & np.isfinite(df.airmass)]
    df['y'] = -np.log(df['psf_corr'].values)

    Rn = 410.0
    u = df.X.values / Rn
    v = df.Y.values / Rn
    q = np.deg2rad(df.parallactic.values)
    y = df.y.values
    eid = df.EXPID.values
    am = df.airmass.values

    print(f'\n{len(df)} star-exposure rows with valid psf_correction, {df.EXPID.nunique()} exposures')
    print('\n=== flat_to_psf correction (-log(corr), demeaned per exposure) dipole/quadrupole fit ===')
    print('Compare directly to D_rot: 0.0349/0.0557/0.0804 (raw amplitude, am>1.4/1.6/1.8) '
          '/ Q_rot: 0.0172/0.0289/0.0460')
    for lo in [1.4, 1.6, 1.8]:
        mask = am > lo
        out = fit_and_bootstrap(u[mask], v[mask], q[mask], y[mask], eid[mask], n_boot=300, seed=0)
        drl, drh = out['D_rot_ci']
        qrl, qrh = out['Q_rot_ci']
        print(f"am>{lo}: n_exp={out['n_exp']} n_star={mask.sum()} R2={out['R2']:.3f}  "
              f"D_rot={out['D_rot']:.4f} [{drl:.4f},{drh:.4f}]  "
              f"Q_rot={out['Q_rot']:.4f} [{qrl:.4f},{qrh:.4f}]")


if __name__ == '__main__':
    main()
