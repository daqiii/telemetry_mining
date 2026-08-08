"""Bonus visual for the L_field notebook (from_mac_to_nersc.md, 2026-08-07 'Next example' entry):
stack the per-fiber L_field loss map over high-airmass exposures in (1) the fixed CS5 frame -- washed
out, since each exposure's real DAR pattern points along ITS OWN zenith direction -- vs (2) the
zenith-derotated frame, where rotating every exposure's field by its own parallactic angle q before
stacking should align the DAR pattern across exposures and reveal the two-lobed quadrupole.

Uses the already-built per-fiber field data/dar_gfa_fiber_loss_metric_v2.parquet (EXPID, airmass,
parallactic, U, V, loss -- 2942 am>1.4 exposures x 25 grid points), not the scalar L_field. Rotation
convention: up = U*cos(q) + V*sin(q), vp = -U*sin(q) + V*cos(q) -- the SAME convention used throughout
this investigation (affine_fit_lib.design_matrix, fit_dipole_quadrupole.py) so "vp" is the zenith axis
the rotating quadrupole basis (up^2-vp^2, 2*up*vp) is built from.
"""
import sys

import numpy as np
import pandas as pd
from scipy.stats import binned_statistic_2d

sys.path.insert(0, '/global/u1/k/klaushon/telemetry_mining-trunk/analysis/dar_dipole')

FIG_DIR = '/global/u1/k/klaushon/telemetry_mining-trunk/notebooks/figures'
AIRMASS_CUT = 1.6

# The per-fiber field only has 6 DISCRETE radii (a 7x7 Cartesian grid cut to a disk, not a
# continuous field) -- 0, 0.3, 0.424, 0.6, 0.671, 0.849. Rotating by each exposure's own
# parallactic angle smears these onto CONTINUOUS angles at those same fixed radii, so a plain
# Cartesian rebinning (tried first) lands most bins on empty gaps between rings and looks patchy.
# Binning in POLAR (radius, angle) instead matches this ring structure directly: radius edges
# below bracket each of the 6 rings in its own bin; angle gets many bins since that's the
# direction rotation actually populates continuously.
R_EDGES = np.array([0.0, 0.15, 0.35, 0.5, 0.65, 0.75, 0.9])
N_ANGLE_BINS = 16


def polar_stack(u, v, loss):
    r = np.hypot(u, v)
    theta = np.arctan2(v, u)
    theta_edges = np.linspace(-np.pi, np.pi, N_ANGLE_BINS + 1)
    stat, redge, tedge, _ = binned_statistic_2d(r, theta, loss, statistic='mean', bins=[R_EDGES, theta_edges])
    count, *_ = binned_statistic_2d(r, theta, loss, statistic='count', bins=[R_EDGES, theta_edges])
    return stat, count, redge, tedge


def radial_profile(u, v, loss):
    """Mean loss(r) per discrete ring -- the isotropic/monopole component. Radius is rotation-
    invariant, so this is identical whether computed from the fixed or derotated coordinates;
    subtracting it from each stacked map isolates the anisotropic (quadrupole) residual, which
    would otherwise be swamped by the much larger monopole in a raw map."""
    r = np.hypot(u, v)
    idx = np.clip(np.digitize(r, R_EDGES) - 1, 0, len(R_EDGES) - 2)
    means = np.array([loss[idx == i].mean() if (idx == i).any() else np.nan for i in range(len(R_EDGES) - 1)])
    return means


def subtract_radial(stat, means):
    # stat is (n_r_bins, n_theta_bins); means is per radius ring -- broadcast across angle.
    return stat - means[:, None]


def main():
    df = pd.read_parquet('data/dar_gfa_fiber_loss_metric_v2.parquet')
    df = df[df.airmass > AIRMASS_CUT]
    n_exp = df.EXPID.nunique()
    print(f'{n_exp} exposures, {len(df)} (exposure, grid-point) rows at airmass>{AIRMASS_CUT}')

    q = np.deg2rad(df.parallactic.values)
    c, s = np.cos(q), np.sin(q)
    U, V, loss = df.U.values, df.V.values, df.loss.values

    # (1) fixed CS5 frame -- no rotation
    fixed_stat, fixed_count, redge, tedge = polar_stack(U, V, loss)

    # (2) zenith-derotated frame -- rotate each exposure's grid by its own parallactic angle
    up = U * c + V * s
    vp = -U * s + V * c
    rot_stat, rot_count, _, _ = polar_stack(up, vp, loss)

    # Subtract the isotropic radial (monopole) component -- rotation-invariant, so it's identical
    # in both frames and would otherwise swamp the much smaller quadrupole we're trying to show.
    rmeans = radial_profile(U, V, loss)
    fixed_stat = subtract_radial(fixed_stat, rmeans)
    rot_stat = subtract_radial(rot_stat, rmeans)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    vmax = np.nanmax(np.abs([np.nanpercentile(fixed_stat[np.isfinite(fixed_stat)], [2, 98]),
                              np.nanpercentile(rot_stat[np.isfinite(rot_stat)], [2, 98])]))
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.8), subplot_kw={'projection': 'polar'})
    Theta, R = np.meshgrid(tedge, redge)
    for ax, stat, title, axis_label in [
        (axes[0], fixed_stat, 'Fixed CS5 frame (no derotation)\n"washed out"', 'CS5 angle'),
        (axes[1], rot_stat, 'Zenith-derotated frame\n(quadrupole should appear)', "angle from zenith (v' axis)"),
    ]:
        im = ax.pcolormesh(Theta, R, stat, cmap='RdBu_r', vmin=-vmax, vmax=vmax, shading='flat')
        ax.set_title(title, pad=20)
        ax.set_theta_zero_location('N')  # put "zenith" (v'=+, theta'=90deg in the derotated panel) at the top
        ax.set_rlabel_position(135)
        fig.colorbar(im, ax=ax, label='mean loss, monopole subtracted', shrink=0.75, pad=0.1)
    fig.suptitle(f'Stacked per-fiber L_field loss map (monopole-subtracted), airmass>{AIRMASS_CUT} (n={n_exp} exposures)')
    fig.tight_layout()
    outpath = f'{FIG_DIR}/lfield_derotated_map.png'
    fig.savefig(outpath, dpi=150)
    print(f'[out] {outpath}')

    # quick numeric check: variance of the map is a cheap proxy for "is there structure"
    print(f'fixed-frame map value std: {np.nanstd(fixed_stat):.5f}')
    print(f'derotated map value std:   {np.nanstd(rot_stat):.5f}  (should be visibly larger if this works)')


if __name__ == '__main__':
    main()
