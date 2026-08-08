"""Mac Claude's next candidate after _model_variance's disconfirmation (from_mac_to_nersc.md,
2026-08-06 '_model_variance out -- next: throughput-correction on/off test' entry):
`subtract_sky`'s `apply_throughput_correction_to_lines` (default True) applies a PER-FIBER
multiplicative correction (`skymodel.throughput_corrections`, fit from bright sky lines) to the sky
model's line flux before subtracting. Premise verified first (per Mac's ask, this is the check that
would have caught the _model_variance premise issue earlier): `throughput_corrections` is active
(not None) and varies substantially fiber-to-fiber (std ~0.11-0.18, range 0.6-2.8x, checked on exposure
349792) -- structurally a much bigger per-fiber effect than the ~0.7% near-uniform shift from
_model_variance.

Mechanism-agnostic on/off test (per Mac: test it, don't reason into it): run the REAL `subtract_sky`
twice on independent copies of the same post-fiberflat frame, once with
`apply_throughput_correction_to_lines=True` (production default, matches RFLUX_std from
variance_inflation_test.py) and once with `apply_throughput_correction_to_lines=False`, re-reduce, and
refit the dipole/quadrupole. If D_rot collapses with the correction off, that's the step. If unchanged,
it isn't -- per Mac's inflection-point note, a second null here means handing the last ingredient to the
desispec sky-subtraction authors rather than continuing to reverse-engineer sky.py from outside.
"""
import copy
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


def _reduce(flux, ivar, mask, indices, jj):
    rivar = np.sum(ivar[indices][:, jj] * (mask[indices][:, jj] == 0), axis=1)
    rflux = np.sum(ivar[indices][:, jj] * flux[indices][:, jj] * (mask[indices][:, jj] == 0), axis=1)
    rflux[rivar > 0] /= rivar[rivar > 0]
    return rflux


def process_exposure_tc_variants(night, expid):
    d = exposure_dir(night, expid)
    if not os.path.isdir(d):
        return None

    rows = {k: [] for k in ('FIBER', 'X', 'Y', 'MODELRFLUX', 'RFLUX_on', 'RFLUX_off')}

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

        frame0 = read_frame(frame_path)
        fiberflat = read_fiberflat(flat_path)
        sky = read_sky(sky_path)
        if sky.throughput_corrections is None:
            continue  # can't do this test without it

        apply_fiberflat(frame0, fiberflat)

        f2i = {f: i for i, f in enumerate(frame0.fibermap['FIBER'])}
        indices = np.array([f2i[f] for f in fibers])
        jj = np.where((frame0.wave >= WAVEMIN) & (frame0.wave <= WAVEMAX))[0]

        frame_on = copy.deepcopy(frame0)
        subtract_sky(frame_on, sky, apply_throughput_correction_to_lines=True)  # production default
        rflux_on = _reduce(frame_on.flux, frame_on.ivar, frame_on.mask, indices, jj)

        frame_off = copy.deepcopy(frame0)
        subtract_sky(frame_off, sky, apply_throughput_correction_to_lines=False)
        rflux_off = _reduce(frame_off.flux, frame_off.ivar, frame_off.mask, indices, jj)

        rows['FIBER'].append(fibers)
        rows['X'].append(X)
        rows['Y'].append(Y)
        rows['MODELRFLUX'].append(modelrflux)
        rows['RFLUX_on'].append(rflux_on)
        rows['RFLUX_off'].append(rflux_off)

    if not rows['FIBER']:
        return None

    table = pd.DataFrame({k: np.hstack(v) for k, v in rows.items()})
    table['EXPID'] = expid
    table['night'] = night
    return table


def _worker(args):
    night, expid, airmass, parallactic = args
    try:
        t = process_exposure_tc_variants(night, expid)
    except Exception:
        return None
    if t is None:
        return None
    t['airmass'] = airmass
    t['parallactic'] = parallactic
    return t


def run(exposure_list, n_workers=16, out='data/dar_throughput_correction.parquet'):
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
