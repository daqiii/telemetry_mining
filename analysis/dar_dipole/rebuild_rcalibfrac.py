"""Mac Claude's positive test (from_mac_to_nersc.md, 2026-08-06): reconstruct RCALIBFRAC ourselves
from the raw model+data pieces (desispec.scripts.select_calib_stars logic, reimplemented inline
using the real desispec functions -- not retyped math) so we can:

  Step 1 (reproduce): rebuild RCALIBFRAC per star and confirm it matches the on-disk
  calibstars-<expid>.csv values -- the validation gate.

  Step 2 (localize model vs data): fit the same rotating/fixed dipole+quadrupole decomposition used
  throughout this investigation (fit_dipole_quadrupole.py's design matrix) separately to
  -log(MODELRFLUX) and log(rflux) (each demeaned per exposure, pre-normalization) instead of to
  `loss`. Whichever carries the zenith-tied, airmass-growing dipole localizes D_rot to the model
  term or the data term.

Source of truth for the per-star reconstruction: read directly from
desispec/scripts/select_calib_stars.py on this NERSC desiconda install (path below) -- same
functions (read_frame, read_fiberflat, read_sky, read_stdstar_models, apply_fiberflat,
subtract_sky, flat_to_psf_flux_correction), same wavelength window (6000-7300A), same psf
correction call (exposure_seeing_fwhm=1.1, normalize=False). We additionally keep MODELRFLUX and
the raw (pre-normalization) rflux per star, which the on-disk calibstars-*.csv does not save.
"""
import glob
import logging
import os
import sys
import time
from multiprocessing import Pool

import fitsio
import numpy as np
import pandas as pd
from astropy.table import Table

sys.path.insert(0, '/global/common/software/desi/perlmutter/desiconda/20260227-2.3.1/code/desispec/main/py')
from desispec.io import read_stdstar_models, read_frame, read_fiberflat, read_sky
from desispec.fiberflat import apply_fiberflat
from desispec.sky import subtract_sky
from desispec.fiberfluxcorr import flat_to_psf_flux_correction

logging.disable(logging.INFO)

REDUX = '/global/cfs/cdirs/desi/spectro/redux/daily/exposures'
WAVEMIN, WAVEMAX = 6000., 7300.


def exposure_dir(night, expid):
    return os.path.join(REDUX, str(night), f'{expid:08d}')


def process_exposure(night, expid):
    """Reproduce select_calib_stars.py's per-star table for one exposure, r-camera only,
    keeping MODELRFLUX and raw rflux (pre-normalization) in addition to RCALIBFRAC."""
    d = exposure_dir(night, expid)
    if not os.path.isdir(d):
        return None

    rows = {k: [] for k in ('FIBER', 'X', 'Y', 'MODELRFLUX', 'RFLUX', 'RATIO_RAW')}

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
        subtract_sky(frame, sky)

        f2i = {f: i for i, f in enumerate(frame.fibermap['FIBER'])}
        indices = np.array([f2i[f] for f in fibers])
        jj = np.where((frame.wave >= WAVEMIN) & (frame.wave <= WAVEMAX))[0]

        psf_correction = flat_to_psf_flux_correction(frame.fibermap, exposure_seeing_fwhm=1.1, normalize=False)
        frame.flux *= psf_correction[:, None]

        rivar = np.sum(frame.ivar[indices][:, jj] * (frame.mask[indices][:, jj] == 0), axis=1)
        rflux = np.sum(frame.ivar[indices][:, jj] * frame.flux[indices][:, jj] * (frame.mask[indices][:, jj] == 0), axis=1)
        rflux[rivar > 0] /= rivar[rivar > 0]
        ratio = rflux / modelrflux

        rows['FIBER'].append(fibers)
        rows['X'].append(X)
        rows['Y'].append(Y)
        rows['MODELRFLUX'].append(modelrflux)
        rows['RFLUX'].append(rflux)
        rows['RATIO_RAW'].append(ratio)

    if not rows['FIBER']:
        return None

    table = pd.DataFrame({k: np.hstack(v) for k, v in rows.items()})
    ok = table.RATIO_RAW > 0
    if ok.sum() == 0:
        return None
    medval = table.RATIO_RAW[ok].median()
    table['RCALIBFRAC_rebuilt'] = table.RATIO_RAW / medval
    table['medval'] = medval
    table['EXPID'] = expid
    table['night'] = night
    return table


def validate(night, expid):
    """Step 1: rebuild + compare to the on-disk calibstars-<expid>.csv (the pipeline's own output)."""
    rebuilt = process_exposure(night, expid)
    if rebuilt is None:
        print(f'{expid}: could not rebuild (missing files)')
        return None
    csv_path = os.path.join(exposure_dir(night, expid), f'calibstars-{expid:08d}.csv')
    if not os.path.exists(csv_path):
        print(f'{expid}: no on-disk calibstars csv to validate against')
        return rebuilt
    onsky = pd.read_csv(csv_path)[['FIBER', 'RCALIBFRAC']].rename(columns={'RCALIBFRAC': 'RCALIBFRAC_ondisk'})
    merged = rebuilt.merge(onsky, on='FIBER', how='inner')
    resid = merged.RCALIBFRAC_rebuilt - merged.RCALIBFRAC_ondisk
    print(f'{expid}: n_stars={len(rebuilt)}, matched={len(merged)}, '
          f'max|resid|={np.abs(resid).max():.2e}, rms={np.sqrt(np.mean(resid**2)):.2e}')
    return rebuilt


def _worker(args):
    night, expid, airmass, parallactic = args
    try:
        t = process_exposure(night, expid)
    except Exception as e:
        return None
    if t is None:
        return None
    t['airmass'] = airmass
    t['parallactic'] = parallactic
    return t


def stratified_sample(n_per_bin=250, seed=0):
    """Stratified sample of exposures across airmass bins, matched to the same exposure
    catalog (dar_calibstars_dataset.parquet) + parallactic (dar_exposure_pointing.csv) used
    throughout this investigation, so the airmass/parallactic values are guaranteed consistent
    with the original D_rot/Q_rot fits."""
    cal = pd.read_parquet('notebooks/data/dar_calibstars_dataset.parquet', columns=['EXPID', 'airmass', 'night'])
    g = cal.groupby('EXPID').agg(airmass=('airmass', 'first'), night=('night', 'first')).reset_index()
    pt = pd.read_csv('data/dar_exposure_pointing.csv', usecols=['EXPID', 'parallactic'])
    g = g.merge(pt, on='EXPID', how='inner')
    g = g[np.isfinite(g.airmass) & np.isfinite(g.parallactic)]

    bins = [(1.0, 1.2), (1.2, 1.4), (1.4, 1.6), (1.6, 1.8), (1.8, 2.2)]
    rng = np.random.default_rng(seed)
    picked = []
    for lo, hi in bins:
        sub = g[(g.airmass > lo) & (g.airmass <= hi)]
        n = min(n_per_bin, len(sub))
        idx = rng.choice(sub.index.values, size=n, replace=False)
        picked.append(sub.loc[idx])
    sample = pd.concat(picked)
    print(f'stratified sample: {len(sample)} exposures across {len(bins)} airmass bins')
    for lo, hi in bins:
        print(f'  ({lo},{hi}]: {((sample.airmass>lo)&(sample.airmass<=hi)).sum()}')
    return sample


def run_sample(n_per_bin=250, n_workers=16, out='data/dar_rebuilt_rcalibfrac.parquet'):
    sample = stratified_sample(n_per_bin)
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
    if len(sys.argv) > 1 and sys.argv[1] == 'validate':
        t0 = time.time()
        validate(20260501, 349792)
        print(f'[timing] {time.time()-t0:.1f}s for one exposure')
    else:
        run_sample()
