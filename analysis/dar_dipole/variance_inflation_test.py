"""Mac Claude's decisive confirm (from_mac_to_nersc.md, 2026-08-06 'The mechanism is _model_variance'
entry): sky.py's `_model_variance` inflates the sky model's ivar per wavelength (to force chi2/ndf=1
against the sky fibers), and `subtract_sky` combines that INFLATED ivar into every fiber's ivar
(`frame.ivar = combine_ivar(frame.ivar, skymodel.ivar)`, sky.py:1096) -- including standard-star
fibers. The pre-inflation ("statistical only") ivar is saved separately on the SkyModel as
`stat_ivar` (sky.py:928, `io/sky.py`'s STATIVAR extension) -- confirmed on this desiconda install: the
FITS product genuinely carries both `ivar` (inflated) and `stat_ivar` (pre-inflation), no re-derivation
needed.

Decisive test: recompute each standard star's post-sky-subtraction ivar using `stat_ivar` instead of
`ivar` in the SAME combine_ivar step, re-reduce the SAME ivar-weighted 6000-7300A band flux, and refit
the dipole/quadrupole. If D_rot collapses toward 0, `_model_variance` is confirmed as the mechanism
(a bright star's high intrinsic ivar gets capped by the padded sky-model variance in a way a pre-padding
combine would not, and the padding itself is sky-level-dependent -- exactly the #1/#2 signatures already
found). If D_rot survives, the padding isn't the lever.

Only the ivar going into the final reduction changes between the two variants -- frame.flux (after sky
subtraction) and frame.mask are identical, matching real `subtract_sky` output exactly for the
"official" variant (a self-consistency check against `flux_chain_decomposition.py`'s RFLUX_sky column).
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
from desispec.util import combine_ivar

sys.path.insert(0, 'analysis/dar_dipole')
from rebuild_rcalibfrac import exposure_dir

logging.disable(logging.INFO)

WAVEMIN, WAVEMAX = 6000., 7300.


def _reduce(flux, ivar, mask, indices, jj):
    rivar = np.sum(ivar[indices][:, jj] * (mask[indices][:, jj] == 0), axis=1)
    rflux = np.sum(ivar[indices][:, jj] * flux[indices][:, jj] * (mask[indices][:, jj] == 0), axis=1)
    rflux[rivar > 0] /= rivar[rivar > 0]
    return rflux


def process_exposure_variance_variants(night, expid):
    d = exposure_dir(night, expid)
    if not os.path.isdir(d):
        return None

    rows = {k: [] for k in ('FIBER', 'X', 'Y', 'MODELRFLUX', 'RFLUX_std', 'RFLUX_prevar')}

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
        if sky.stat_ivar is None:
            continue  # older reduction without STATIVAR saved -- skip, can't do this test on it

        apply_fiberflat(frame, fiberflat)

        f2i = {f: i for i, f in enumerate(frame.fibermap['FIBER'])}
        indices = np.array([f2i[f] for f in fibers])
        jj = np.where((frame.wave >= WAVEMIN) & (frame.wave <= WAVEMAX))[0]

        ivar_before = frame.ivar.copy()
        subtract_sky(frame, sky)  # real production function -- correct flux (incl. line-throughput
        # corrections), ivar (combine_ivar with the INFLATED sky.ivar), and mask, matching
        # flux_chain_decomposition.py's RFLUX_sky stage exactly.
        flux_after = frame.flux
        mask_after = frame.mask
        ivar_std = frame.ivar  # = combine_ivar(ivar_before, sky.ivar), already done by subtract_sky

        ivar_prevar = combine_ivar(ivar_before, sky.stat_ivar)  # pre-_model_variance-inflation, only
        # this one input swapped; flux_after/mask_after held identical to isolate the ivar effect.

        rflux_std = _reduce(flux_after, ivar_std, mask_after, indices, jj)
        rflux_prevar = _reduce(flux_after, ivar_prevar, mask_after, indices, jj)

        rows['FIBER'].append(fibers)
        rows['X'].append(X)
        rows['Y'].append(Y)
        rows['MODELRFLUX'].append(modelrflux)
        rows['RFLUX_std'].append(rflux_std)
        rows['RFLUX_prevar'].append(rflux_prevar)

    if not rows['FIBER']:
        return None

    table = pd.DataFrame({k: np.hstack(v) for k, v in rows.items()})
    table['EXPID'] = expid
    table['night'] = night
    return table


def _worker(args):
    night, expid, airmass, parallactic = args
    try:
        t = process_exposure_variance_variants(night, expid)
    except Exception:
        return None
    if t is None:
        return None
    t['airmass'] = airmass
    t['parallactic'] = parallactic
    return t


def run(exposure_list, n_workers=16, out='data/dar_variance_inflation.parquet'):
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
