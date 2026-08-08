"""Mac Claude's bisector test (from_mac_to_nersc.md, 2026-08-06 'The test we skipped: fully-UNWEIGHTED
rflux' entry): the two prior tests (_model_variance's prevar/std, and the throughput-correction on/off)
both kept the ivar-weighted reduction and only varied a narrow ingredient of the ivar itself -- neither
actually tested whether ivar-weighting the flux measurement matters AT ALL. `RFLUX` is an ivar-weighted
mean over the 6000-7300A band; `MODELRFLUX` (already ruled out as the dipole's source in
rebuild_rcalibfrac.py's model-vs-data localization) is an unweighted sum over the same band -- a
mismatch flagged early but never directly tested.

This is a class-level bisector, not another named-function guess: recompute the star's post-sky-
subtraction reduced flux as a plain (unweighted) mean over mask-good pixels in the same band, same
437-exposure subset, and refit. Uses the real, unmodified `subtract_sky` (standard settings, matching
production/RFLUX_std exactly) for the flux itself -- only the REDUCTION (weighted vs unweighted) differs.
- D_rot collapses with the unweighted reduction => it's an ivar-weighting artifact (the star's flux
  weighted by sky-influenced ivar, zenith-tied because sky level is) -- a nameable mechanism CLASS.
- D_rot persists => the bias is in the sky-subtracted flux itself, not the weighting -- localization is
  handoff-ready to the desispec sky-subtraction authors either way.
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
from desispec.io import read_stdstar_models, read_frame, read_fiberflat, read_sky
from desispec.fiberflat import apply_fiberflat
from desispec.sky import subtract_sky

sys.path.insert(0, 'analysis/dar_dipole')
from rebuild_rcalibfrac import exposure_dir

logging.disable(logging.INFO)

WAVEMIN, WAVEMAX = 6000., 7300.


def _reduce_weighted(flux, ivar, mask, indices, jj):
    rivar = np.sum(ivar[indices][:, jj] * (mask[indices][:, jj] == 0), axis=1)
    rflux = np.sum(ivar[indices][:, jj] * flux[indices][:, jj] * (mask[indices][:, jj] == 0), axis=1)
    rflux[rivar > 0] /= rivar[rivar > 0]
    return rflux


def _reduce_unweighted(flux, mask, indices, jj):
    good = (mask[indices][:, jj] == 0)
    n = np.sum(good, axis=1)
    rflux = np.sum(flux[indices][:, jj] * good, axis=1)
    rflux[n > 0] /= n[n > 0]
    rflux[n == 0] = np.nan
    return rflux


def process_exposure_weighting_variants(night, expid):
    d = exposure_dir(night, expid)
    if not os.path.isdir(d):
        return None

    rows = {k: [] for k in ('FIBER', 'X', 'Y', 'MODELRFLUX', 'RFLUX_weighted', 'RFLUX_unweighted')}

    for spectro in range(10):
        frame_path = os.path.join(d, f'frame-r{spectro}-{expid:08d}.fits.gz')
        flat_path = os.path.join(d, f'fiberflatexp-r{spectro}-{expid:08d}.fits.gz')
        sky_path = os.path.join(d, f'sky-r{spectro}-{expid:08d}.fits.gz')
        star_path = os.path.join(d, f'stdstars-{spectro}-{expid:08d}.fits.gz')
        if not all(os.path.exists(p) for p in (frame_path, flat_path, sky_path, star_path)):
            continue

        flux, wave, fibers, metadata = read_stdstar_models(star_path)
        fmap = fitsio.read(star_path, 'FIBERMAP')
        ii = (wave >= WAVEMIN) & (wave <= WAVEMAX)
        modelrflux = np.sum(flux[:, ii], axis=1)
        f2i_star = {f: i for i, f in enumerate(fmap['FIBER'])}
        star_idx = [f2i_star[f] for f in fibers]
        X = fmap['FIBERASSIGN_X'][star_idx]
        Y = fmap['FIBERASSIGN_Y'][star_idx]

        frame = read_frame(frame_path)
        fiberflat = read_fiberflat(flat_path)
        sky = read_sky(sky_path)
        apply_fiberflat(frame, fiberflat)

        f2i = {f: i for i, f in enumerate(frame.fibermap['FIBER'])}
        indices = np.array([f2i[f] for f in fibers])
        jj = np.where((frame.wave >= WAVEMIN) & (frame.wave <= WAVEMAX))[0]

        subtract_sky(frame, sky)  # standard production settings, matches RFLUX_std exactly

        rflux_w = _reduce_weighted(frame.flux, frame.ivar, frame.mask, indices, jj)
        rflux_u = _reduce_unweighted(frame.flux, frame.mask, indices, jj)

        rows['FIBER'].append(fibers)
        rows['X'].append(X)
        rows['Y'].append(Y)
        rows['MODELRFLUX'].append(modelrflux)
        rows['RFLUX_weighted'].append(rflux_w)
        rows['RFLUX_unweighted'].append(rflux_u)

    if not rows['FIBER']:
        return None

    table = pd.DataFrame({k: np.hstack(v) for k, v in rows.items()})
    table['EXPID'] = expid
    table['night'] = night
    return table


def _worker(args):
    night, expid, airmass, parallactic = args
    try:
        t = process_exposure_weighting_variants(night, expid)
    except Exception:
        return None
    if t is None:
        return None
    t['airmass'] = airmass
    t['parallactic'] = parallactic
    return t


def run(exposure_list, n_workers=16, out='data/dar_unweighted_reduction.parquet'):
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
    print(f'\n[out] {out}: {len(df)} stars, {df.EXPID.nunique()} exposures')
    return df


if __name__ == '__main__':
    good_exp_path = sys.argv[1] if len(sys.argv) > 1 else 'data/dar_good_reproduction_exposures.parquet'
    exposure_list = pd.read_parquet(good_exp_path)
    run(exposure_list)
