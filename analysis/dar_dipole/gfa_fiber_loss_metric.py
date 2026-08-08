"""Milestone 1 of the GFA-based, artifact-free fiber-loss metric (docs/FIBER_LOSS_METRICS.md;
build spec in from_mac_to_nersc.md, 2026-08-06 'NEW BUILD' entry).

Both RCALIBFRAC and this metric estimate the same physical quantity -- the aperture-coupling
fraction FF = A(sigma, |delta|) (desimodel FastFiberAcceptance, "POINT") -- but RCALIBFRAC
measures it from sky-subtracted spectroscopic flux (inherits the sky-subtraction artifact this
whole investigation traced), while this metric PREDICTS it purely from imaging: guide-star PSF
size (sigma, from the offline GFA summary) and the affine guide-star offset field delta(r) = t + G*r
(from PMGSTARS/PMGWCS, the same machinery already used for the Test 6 / Q_rot guide-star
cross-check in pmgstars_quadrupole_test.py -- reused via its output, data/dar_pmgstars_shear.parquet,
not re-fit from scratch).

THE GATING TEST: fit the same derotated dipole/quadrupole decomposition on the DEMEANED metric's
loss(r) field. This construction structurally cannot carry the sky-subtraction artifact -- it never
touches sky-subtracted flux -- so if it's sound it should reproduce Q_rot/ΔG (0.11/0.16/0.22" at
airmass 1.48/1.69/1.86) while D_rot stays small/absent (set by the affine model + noise, not the
~2x-Q_rot loss dipole RCALIBFRAC shows). If Q_rot does NOT reproduce, the sigma/delta->FF pipeline
needs debugging before anything downstream is trustworthy.
"""
import sys
sys.path.insert(0, 'analysis/dar_dipole')
sys.path.insert(0, 'src')

import numpy as np
import pandas as pd

from affine_fit_lib import fit_and_bootstrap
from desimodel.fastfiberacceptance import FastFiberAcceptance
from desimodel.io import load_platescale
from telemetry_mining.gfa import load_gfa_summary
from telemetry_mining.config import Config

FIELD_RADIUS_DEG = 1.6   # same normalization pmgstars_quadrupole_test.py fit (t, G) in
FIELD_RADIUS_MM = 410.0  # same CS5-frame edge radius used throughout the rest of the investigation
SIGMA_EFF_UM = 52.0      # the DAR-study's effective acceptance scale, reused ONLY for the ΔG
                          # cross-check conversion (comparing this metric's Q_rot to the same target
                          # in the same units as the rest of the report) -- the metric's own
                          # prediction below uses the REAL per-exposure sigma, not this fixed value.

FA = FastFiberAcceptance()
PS = load_platescale()


def platescale_um_per_arcsec(r_mm):
    r2 = np.asarray(r_mm) ** 2
    return np.interp(r2, PS['radius'] ** 2, np.sqrt(PS['radial_platescale'] * PS['az_platescale']))


def build_grid(n=7):
    """A grid of normalized (u,v) points (edge=1) covering the field disk, reused for every
    exposure -- deterministic, not per-exposure star positions, since this metric predicts the
    field from the affine model, not from a variable set of measured stars."""
    lin = np.linspace(-0.9, 0.9, n)
    U, V = np.meshgrid(lin, lin)
    U, V = U.ravel(), V.ravel()
    keep = (U ** 2 + V ** 2) <= 0.85 ** 2
    return U[keep], V[keep]


def main():
    cfg = Config.default()
    shear = pd.read_parquet('data/dar_pmgstars_shear.parquet')
    shear = shear[(shear.cond < 50) & (shear.n_stars >= 8) &
                  np.isfinite(shear.parallactic) & np.isfinite(shear.airmass)]
    print(f'{len(shear)} exposures with a good affine guide-star fit')

    gfa = load_gfa_summary(cfg)[['FWHM_ASEC']]
    df = shear.merge(gfa, left_on='EXPID', right_index=True, how='inner')
    df = df[np.isfinite(df.FWHM_ASEC) & (df.FWHM_ASEC > 0)]
    print(f'{len(df)} exposures after joining GFA seeing (FWHM_ASEC)')

    U, V = build_grid(n=7)
    n_grid = len(U)
    print(f'{n_grid} grid points per exposure -> {len(df)*n_grid} total (exposure, grid-point) rows')

    # --- per-exposure vectorized evaluation ---
    tx = df.tx.values[:, None]; ty = df.ty.values[:, None]
    s = df.scale.values[:, None]; th = df.theta.values[:, None]
    e1 = df.e1.values[:, None]; e2 = df.e2.values[:, None]
    Ug = U[None, :]; Vg = V[None, :]

    dRA = tx + s * Ug - th * Vg + e1 * Ug + e2 * Vg     # arcsec, shape (n_exp, n_grid)
    dDec = ty + s * Vg + th * Ug + e2 * Ug - e1 * Vg    # arcsec
    delta_arcsec = np.hypot(dRA, dDec)

    r_mm = np.sqrt(Ug ** 2 + Vg ** 2) * FIELD_RADIUS_MM
    ps = platescale_um_per_arcsec(r_mm)                 # um/arcsec, broadcasts (1,n_grid) really same for all exp
    delta_um = delta_arcsec * ps

    sigma_arcsec = (df.FWHM_ASEC.values / 2.35)[:, None]
    sigma_um = sigma_arcsec * ps

    FF = FA.value('POINT', sigma_um.ravel(), delta_um.ravel()).reshape(delta_um.shape)

    field_mean_FF = FF.mean(axis=1, keepdims=True)
    GFIBERFRAC_demeaned = FF / field_mean_FF
    loss_demeaned = 1.0 - GFIBERFRAC_demeaned

    # flatten to (exposure, grid-point) rows
    n_exp = len(df)
    out = pd.DataFrame({
        'EXPID': np.repeat(df.EXPID.values, n_grid),
        'airmass': np.repeat(df.airmass.values, n_grid),
        'parallactic': np.repeat(df.parallactic.values, n_grid),
        'U': np.tile(U, n_exp),
        'V': np.tile(V, n_exp),
        'loss_demeaned': loss_demeaned.ravel(),
        'FF': FF.ravel(),
    })
    out.to_parquet('data/dar_gfa_fiber_loss_grid.parquet')
    print(f"[out] data/dar_gfa_fiber_loss_grid.parquet: {len(out)} rows")

    # --- Milestone 1 gating fit ---
    q = np.deg2rad(out.parallactic.values)
    eid = out.EXPID.values
    am = out.airmass.values
    u = out.U.values
    v = out.V.values
    y = out.loss_demeaned.values

    print('\n=== Milestone 1: demeaned GFA-loss dipole/quadrupole decomposition ===')
    print('Target: Q_rot -> ΔG should land near 0.11/0.16/0.22" at airmass 1.48/1.69/1.86')
    print('Win condition: Q_rot reproduces ΔG; D_rot stays small (NOT the ~2x-Q_rot RCALIBFRAC-scale dipole)')
    for lo in [1.2, 1.4, 1.6, 1.8]:
        mask = am > lo
        if mask.sum() < 200:
            print(f'am>{lo}: too few, skip')
            continue
        result = fit_and_bootstrap(u[mask], v[mask], q[mask], y[mask], eid[mask], n_boot=300, seed=0)
        dl, dh = result['D_rot_ci']
        ql, qh = result['Q_rot_ci']
        dG = SIGMA_EFF_UM * np.sqrt(2 * result['Q_rot'])
        dG_lo = SIGMA_EFF_UM * np.sqrt(2 * max(ql, 0))
        dG_hi = SIGMA_EFF_UM * np.sqrt(2 * max(qh, 0))
        print(f"am>{lo}: n_exp={result['n_exp']:5d} n_row={mask.sum():6d} R2={result['R2']:.3f}")
        print(f"  D_rot={result['D_rot']:.4f} [{dl:.4f},{dh:.4f}]   Q_rot={result['Q_rot']:.4f} [{ql:.4f},{qh:.4f}]"
              f"   D_rot/Q_rot={result['D_rot']/result['Q_rot'] if result['Q_rot']>0 else float('nan'):.2f}")
        print(f"  ΔG (edge um) = {dG:.1f} [{dG_lo:.1f},{dG_hi:.1f}]")


if __name__ == '__main__':
    main()
