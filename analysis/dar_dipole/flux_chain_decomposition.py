"""Mac Claude's primary test (from_mac_to_nersc.md, 2026-08-06 'Model ruled out, D_rot is in RFLUX'
entry): the model-vs-data localization pinned D_rot to the measured r-band flux (RFLUX), not the
stellar model. This decomposes RFLUX's own dipole/quadrupole after each sub-step of the flux chain
(desispec.scripts.select_calib_stars.py order) to find which step introduces the rotating,
zenith-tied, airmass-growing dipole:

  stage 0: raw extracted frame.flux (straight off `read_frame`)
  stage 1: + apply_fiberflat
  stage 2: + subtract_sky
  stage 3: + flat_to_psf (the final RCALIBFRAC-construction flux -- already disconfirmed twice as
            the dipole's origin, included here only as a consistency check: it should add ~nothing)

Same reduction formula as select_calib_stars.py at every stage (ivar-weighted sum over 6000-7300A,
masked pixels excluded) -- flux/ivar/mask are snapshotted right after each step because
apply_fiberflat and subtract_sky both mutate frame.flux/ivar/mask in place, so the masking/weighting
must be evaluated at the same stage as the flux it's paired with, not re-used from a later stage.

Whichever step makes the ROTATING dipole jump from ~0 to ~D_rot localizes the mechanism -- also
tracks the FIXED dipole per Mac's note (fiberflat/extraction errors are instrument-frame, should
land in D_fix, not the rotating D_rot, unless something couples them to zenith).
"""
import logging
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
from desispec.fiberfluxcorr import flat_to_psf_flux_correction

sys.path.insert(0, 'analysis/dar_dipole')
from rebuild_rcalibfrac import exposure_dir, stratified_sample
from affine_fit_lib import fit_and_bootstrap

logging.disable(logging.INFO)

WAVEMIN, WAVEMAX = 6000., 7300.
STAGES = ['raw', 'flat', 'sky', 'psf']


def _reduce(flux, ivar, mask, indices, jj):
    rivar = np.sum(ivar[indices][:, jj] * (mask[indices][:, jj] == 0), axis=1)
    rflux = np.sum(ivar[indices][:, jj] * flux[indices][:, jj] * (mask[indices][:, jj] == 0), axis=1)
    rflux[rivar > 0] /= rivar[rivar > 0]
    return rflux


def process_exposure_stages(night, expid):
    d = exposure_dir(night, expid)
    import os
    if not os.path.isdir(d):
        return None

    rows = {k: [] for k in ('FIBER', 'X', 'Y', 'MODELRFLUX')}
    for s in STAGES:
        rows[f'RFLUX_{s}'] = []

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

        f2i = {f: i for i, f in enumerate(frame.fibermap['FIBER'])}
        indices = np.array([f2i[f] for f in fibers])
        jj = np.where((frame.wave >= WAVEMIN) & (frame.wave <= WAVEMAX))[0]

        stage_flux = {}
        stage_flux['raw'] = _reduce(frame.flux, frame.ivar, frame.mask, indices, jj)

        apply_fiberflat(frame, fiberflat)
        stage_flux['flat'] = _reduce(frame.flux, frame.ivar, frame.mask, indices, jj)

        subtract_sky(frame, sky)
        stage_flux['sky'] = _reduce(frame.flux, frame.ivar, frame.mask, indices, jj)

        psf_correction = flat_to_psf_flux_correction(frame.fibermap, exposure_seeing_fwhm=1.1, normalize=False)
        frame.flux *= psf_correction[:, None]
        stage_flux['psf'] = _reduce(frame.flux, frame.ivar, frame.mask, indices, jj)

        rows['FIBER'].append(fibers)
        rows['X'].append(X)
        rows['Y'].append(Y)
        rows['MODELRFLUX'].append(modelrflux)
        for s in STAGES:
            rows[f'RFLUX_{s}'].append(stage_flux[s])

    if not rows['FIBER']:
        return None

    table = pd.DataFrame({k: np.hstack(v) for k, v in rows.items()})
    table['EXPID'] = expid
    table['night'] = night
    return table


def _worker(args):
    night, expid, airmass, parallactic = args
    try:
        t = process_exposure_stages(night, expid)
    except Exception:
        return None
    if t is None:
        return None
    t['airmass'] = airmass
    t['parallactic'] = parallactic
    return t


def run_sample(n_per_bin=250, n_workers=16, out='data/dar_flux_chain_stages.parquet'):
    sample = stratified_sample(n_per_bin)  # same seed=0 -> same 1177 exposures as rebuild_rcalibfrac
    jobs = list(zip(sample.night.astype(int), sample.EXPID.astype(int), sample.airmass, sample.parallactic))
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
    run_sample()
