"""Mac Claude's discriminator #3 (from_mac_to_nersc.md, 2026-08-06 'Sky subtraction localized' entry):
look at the sky residual directly, in the SKY FIBERS themselves (not the standard-star fibers -- a
star's own light swamps any sky mismatch in its own fiber). Form (measured sky flux - sky model flux)
in the same 6000-7300A band, at each sky fiber's own focal-plane position, and fit the same
dipole/quadrupole decomposition used throughout this investigation. A zenith-tied, airmass-growing
gradient in the sky residual itself -- caught directly at the sky fibers, not inferred from the
standard-star flux -- would be the mechanism, not just a consistent-with-it correlation.

skymodel.flux (from desispec's SkyModel, read via read_sky) is already PER-FIBER (same shape as
frame.flux, throughput/fiberflat-consistent with the frame it will be subtracted from) -- so
(frame.flux - skymodel.flux) at a SKY fiber, evaluated right after apply_fiberflat and before
subtract_sky, is exactly the sky model's residual against what was actually measured at that fiber's
position. No re-derivation of the sky model needed.

Runs on the same 437-exposure code-version-consistent "good reproduction" subset established in
rebuild_rcalibfrac.py / flux_chain_decomposition.py, reusing their exact star-based quality gate so the
exposure list is directly comparable to every other result in this investigation.
"""
import logging
import os
import sys
import time
from multiprocessing import Pool

import fitsio
import numpy as np
import pandas as pd

sys.path.insert(0, '/global/common/software/desi/perlmutter/desiconda/20260227-2.3.1/code/desispec/main/py')
from desispec.io import read_frame, read_fiberflat, read_sky
from desispec.fiberflat import apply_fiberflat

sys.path.insert(0, 'analysis/dar_dipole')
from rebuild_rcalibfrac import exposure_dir
from affine_fit_lib import fit_and_bootstrap

logging.disable(logging.INFO)

WAVEMIN, WAVEMAX = 6000., 7300.


def _reduce(flux, ivar, mask, jj):
    rivar = np.sum(ivar[:, jj] * (mask[:, jj] == 0), axis=1)
    rflux = np.sum(ivar[:, jj] * flux[:, jj] * (mask[:, jj] == 0), axis=1)
    rflux[rivar > 0] /= rivar[rivar > 0]
    return rflux


def process_exposure_sky_residual(night, expid):
    d = exposure_dir(night, expid)
    if not os.path.isdir(d):
        return None

    rows = {k: [] for k in ('FIBER', 'X', 'Y', 'sky_measured', 'sky_model')}

    for spectro in range(10):
        frame_path = os.path.join(d, f'frame-r{spectro}-{expid:08d}.fits.gz')
        flat_path = os.path.join(d, f'fiberflatexp-r{spectro}-{expid:08d}.fits.gz')
        sky_path = os.path.join(d, f'sky-r{spectro}-{expid:08d}.fits.gz')
        if not all(os.path.exists(p) for p in (frame_path, flat_path, sky_path)):
            continue

        frame = read_frame(frame_path)
        fiberflat = read_fiberflat(flat_path)
        sky = read_sky(sky_path)

        sky_idx = np.where(frame.fibermap['OBJTYPE'] == 'SKY')[0]
        if len(sky_idx) == 0:
            continue

        apply_fiberflat(frame, fiberflat)  # measured sky flux, post-fiberflat, pre-subtraction

        jj = np.where((frame.wave >= WAVEMIN) & (frame.wave <= WAVEMAX))[0]

        measured = _reduce(frame.flux[sky_idx], frame.ivar[sky_idx], frame.mask[sky_idx], jj)
        # same ivar/mask weights for the model reduction -- isolates the (measured - model) residual
        # under the identical weighting the measurement itself uses, rather than a differently-weighted
        # model reduction that would mix in a second effect.
        model = _reduce(sky.flux[sky_idx], frame.ivar[sky_idx], frame.mask[sky_idx], jj)

        X = frame.fibermap['FIBER_X'][sky_idx]
        Y = frame.fibermap['FIBER_Y'][sky_idx]
        fibers = frame.fibermap['FIBER'][sky_idx]

        rows['FIBER'].append(fibers)
        rows['X'].append(X)
        rows['Y'].append(Y)
        rows['sky_measured'].append(measured)
        rows['sky_model'].append(model)

    if not rows['FIBER']:
        return None

    table = pd.DataFrame({k: np.hstack(v) for k, v in rows.items()})
    table['EXPID'] = expid
    table['night'] = night
    return table


def _worker(args):
    night, expid, airmass, parallactic = args
    try:
        t = process_exposure_sky_residual(night, expid)
    except Exception:
        return None
    if t is None:
        return None
    t['airmass'] = airmass
    t['parallactic'] = parallactic
    return t


def run(exposure_list, n_workers=16, out='data/dar_sky_residual.parquet'):
    """exposure_list: DataFrame with columns night, EXPID, airmass, parallactic."""
    jobs = list(zip(exposure_list.night.astype(int), exposure_list.EXPID.astype(int),
                     exposure_list.airmass, exposure_list.parallactic))
    t0 = time.time()
    results = []
    with Pool(n_workers) as pool:
        for i, r in enumerate(pool.imap_unordered(_worker, jobs)):
            if r is not None:
                results.append(r)
            if (i + 1) % 25 == 0:
                elapsed = time.time() - t0
                print(f'{i+1}/{len(jobs)} exposures done ({len(results)} succeeded), '
                      f'{elapsed:.0f}s elapsed, ~{elapsed/(i+1)*len(jobs):.0f}s total est.', flush=True)
    df = pd.concat(results, ignore_index=True)
    df.to_parquet(out)
    print(f'\n[out] {out}: {len(df)} sky-fiber rows, {df.EXPID.nunique()} exposures')
    return df


if __name__ == '__main__':
    good_exp_path = sys.argv[1] if len(sys.argv) > 1 else 'data/dar_good_reproduction_exposures.parquet'
    exposure_list = pd.read_parquet(good_exp_path)
    run(exposure_list)
