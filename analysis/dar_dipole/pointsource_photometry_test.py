"""Julien's proposed metric (via from_mac_to_nersc.md, 2026-08-06 'Prototype Julien's metric' entry):
compare measured spectrograph counts/s to external photometry, over ALL point sources -- not just
calibstars, and model-free (no stellar template). Three payoffs: (1) independent-metric confirmation
of the sky-subtraction localization, (2) if the dipole survives, a bigger/more general finding for
Julien (desispec owner) since it would mean general point-source spectrophotometry is affected, not
just RCALIBFRAC's specific construction, (3) using ALL point sources (not just standard stars) breaks
any dependence on the standard-star selection -- a confound the investigation otherwise couldn't rule
out.

Construction, per spec:
  - point-source fibers: fibermap MORPHTYPE=='PSF' (Legacy Survey Tractor classification) with
    FLUX_R > 0 (some fields/fibers are Gaia-classified 'GPSF' with FLUX_R=-99, i.e. missing --
    excluded automatically by the FLUX_R>0 cut).
  - measured: sky-subtracted r-band RAW counts/s (pre-flux-calibration -- frame.flux after
    apply_fiberflat + subtract_sky is still in counts, not physical flux units; the "c" in cframe is
    what applies absolute flux calibration, which is deliberately NOT used here so this stays
    independent of the fluxcal vector, which is itself derived from standard stars). Integrated
    (summed, mask-respecting) over the same 6000-7300A window used throughout this investigation,
    divided by EXPTIME (frame.meta).
  - reference: fibermap FLUX_R (Legacy Survey photometry, nanomaggies).
  - residual = log(counts/s) - log(FLUX_R), per fiber, per-exposure demeaned in the decomposition
    (absorbs the unknown nominal-throughput normalization -- only the spatial shape matters).

Same 437-exposure code-version-consistent subset as the rest of the investigation, same
affine_fit_lib decomposition.
"""
import logging
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '/global/common/software/desi/perlmutter/desiconda/20260227-2.3.1/code/desispec/main/py')
from desispec.io import read_frame, read_fiberflat, read_sky
from desispec.fiberflat import apply_fiberflat
from desispec.sky import subtract_sky

sys.path.insert(0, 'analysis/dar_dipole')
from rebuild_rcalibfrac import exposure_dir

logging.disable(logging.INFO)

WAVEMIN, WAVEMAX = 6000., 7300.


def _reduce_sum(flux, mask, jj):
    good = (mask[:, jj] == 0)
    return np.sum(flux[:, jj] * good, axis=1)


def process_exposure_pointsource(night, expid):
    d = exposure_dir(night, expid)
    if not os.path.isdir(d):
        return None

    rows = {k: [] for k in ('FIBER', 'X', 'Y', 'FLUX_R', 'counts_per_s')}

    for spectro in range(10):
        frame_path = os.path.join(d, f'frame-r{spectro}-{expid:08d}.fits.gz')
        flat_path = os.path.join(d, f'fiberflatexp-r{spectro}-{expid:08d}.fits.gz')
        sky_path = os.path.join(d, f'sky-r{spectro}-{expid:08d}.fits.gz')
        if not all(os.path.exists(p) for p in (frame_path, flat_path, sky_path)):
            continue

        frame = read_frame(frame_path)
        fiberflat = read_fiberflat(flat_path)
        sky = read_sky(sky_path)

        fm = frame.fibermap
        morph = np.char.strip(np.asarray(fm['MORPHTYPE'], dtype=str))
        flux_r = np.asarray(fm['FLUX_R'], dtype=float)
        objtype = np.char.strip(np.asarray(fm['OBJTYPE'], dtype=str))
        sel = (morph == 'PSF') & (flux_r > 0) & np.isfinite(flux_r) & (objtype == 'TGT')
        idx = np.where(sel)[0]
        if len(idx) == 0:
            continue

        exptime = frame.meta.get('EXPTIME')
        if not exptime or exptime <= 0:
            continue

        apply_fiberflat(frame, fiberflat)
        subtract_sky(frame, sky)  # standard production settings

        jj = np.where((frame.wave >= WAVEMIN) & (frame.wave <= WAVEMAX))[0]
        counts = _reduce_sum(frame.flux[idx], frame.mask[idx], jj)
        counts_per_s = counts / exptime

        rows['FIBER'].append(fm['FIBER'][idx])
        rows['X'].append(fm['FIBER_X'][idx])
        rows['Y'].append(fm['FIBER_Y'][idx])
        rows['FLUX_R'].append(flux_r[idx])
        rows['counts_per_s'].append(counts_per_s)

    if not rows['FIBER']:
        return None

    table = pd.DataFrame({k: np.hstack(v) for k, v in rows.items()})
    table['EXPID'] = expid
    table['night'] = night
    return table


def _worker(args):
    night, expid, airmass, parallactic = args
    try:
        t = process_exposure_pointsource(night, expid)
    except Exception:
        return None
    if t is None:
        return None
    t['airmass'] = airmass
    t['parallactic'] = parallactic
    return t


def run(exposure_list, n_workers=16, out='data/dar_pointsource_photometry.parquet'):
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
    print(f'\n[out] {out}: {len(df)} point-source-fiber rows, {df.EXPID.nunique()} exposures')
    return df


if __name__ == '__main__':
    good_exp_path = sys.argv[1] if len(sys.argv) > 1 else 'data/dar_good_reproduction_exposures.parquet'
    exposure_list = pd.read_parquet(good_exp_path)
    run(exposure_list)
