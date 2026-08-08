"""Metric (A) from docs/FIBER_LOSS_METRICS.md Sec 3/3.2 (build spec: from_mac_to_nersc.md,
2026-08-06 'Answer: Option 1' entry, step 1):

  L_see = 1 - A(sigma, 0) / A_ref     -- SCALAR per exposure, from GFA seeing alone (delta=0).

This is the artifact-free replacement for RCALIBFRAC's whole-array *level* -- it never touches
sky-subtracted flux, only the guide-star PSF size (FWHM_ASEC) reduced through desimodel's
FastFiberAcceptance at zero offset. It is the y-axis for external-influence studies (Milestone 3's
mirror-air ΔT scatter); it is NOT the same "radial" quantity as metric (B)'s field pattern
(dar_gfa_fiber_loss_metric_v2.parquet) -- see the doc's "three things kept separate" table. Do not
average B to get A.

A_ref = A(sigma_ref, 0) at a fixed reference seeing of 1.1" FWHM -- the same fixed seeing desispec's
own flat_to_psf_flux_correction assumes (analysis/dar_dipole/flat_to_psf_dipole_test.py docstring),
not an arbitrary choice, and it sits near the middle of the observed FWHM_ASEC distribution
(median ~1.05", mean ~1.17" over the full GFA summary). sigma is evaluated at the field center
(r=0mm) since this is a whole-array scalar, not a per-fiber map -- platescale is ~constant near
r=0 so the field-center value is representative.
"""
import sys
sys.path.insert(0, 'analysis/dar_dipole')
sys.path.insert(0, 'src')

import numpy as np
import pandas as pd

from desimodel.fastfiberacceptance import FastFiberAcceptance
from desimodel.io import load_platescale
from telemetry_mining.gfa import load_gfa_summary
from telemetry_mining.config import Config

REF_SEEING_ASEC = 1.1  # desispec's own fixed flat_to_psf seeing assumption

FA = FastFiberAcceptance()
PS = load_platescale()


def platescale_um_per_arcsec_center():
    """um/arcsec at the field center (r=0mm) -- a single scalar, consistent with the rest of
    this investigation's platescale interpolation (sqrt(radial*az))."""
    return float(np.interp(0.0, PS['radius'] ** 2, np.sqrt(PS['radial_platescale'] * PS['az_platescale'])))


def main():
    cfg = Config.default()
    exp = pd.read_csv('data/dar_exposure_pointing.csv')[['EXPID', 'airmass', 'parallactic']]

    gfa = load_gfa_summary(cfg)[['FWHM_ASEC']]
    df = exp.merge(gfa, left_on='EXPID', right_index=True, how='inner')
    df = df[np.isfinite(df.FWHM_ASEC) & (df.FWHM_ASEC > 0)]
    print(f'{len(df)}/{len(exp)} exposures with valid GFA seeing (of {len(exp)} in the am>1.4 pointing sample)')

    ps_center = platescale_um_per_arcsec_center()
    print(f'platescale at field center = {ps_center:.2f} um/arcsec')

    sigma_um = (df.FWHM_ASEC.values / 2.35) * ps_center
    sigma_ref_um = (REF_SEEING_ASEC / 2.35) * ps_center

    A0 = FA.value('POINT', sigma_um, np.zeros_like(sigma_um))
    A_ref = float(FA.value('POINT', np.array([sigma_ref_um]), np.array([0.0]))[0])

    L_see = 1.0 - A0 / A_ref

    out = df.assign(sigma_um=sigma_um, A0=A0, L_see=L_see)[
        ['EXPID', 'airmass', 'parallactic', 'FWHM_ASEC', 'sigma_um', 'A0', 'L_see']
    ]
    out.to_parquet('data/dar_gfa_seeing_level.parquet')
    print(f'[out] data/dar_gfa_seeing_level.parquet: {len(out)} rows')

    print(f'\nA_ref (sigma at {REF_SEEING_ASEC}", delta=0) = {A_ref:.4f}')
    print('L_see summary:')
    print(out.L_see.describe())
    print(f'\nsanity: FWHM_ASEC vs L_see Pearson r = {np.corrcoef(out.FWHM_ASEC, out.L_see)[0,1]:.4f} '
          '(should be strongly positive -- worse seeing -> more loss, monotonic by construction)')


if __name__ == '__main__':
    main()
