"""Combined 2-panel summary figure for the L_field vs |Δairmass| example (Klaus's design, 2026-08-07):
tells the whole story in one figure instead of 4 separate per-band panels.

Left: all 4 airmass-band binned-median[mean] curves overlaid on one zoomed axis, colored low->high
airmass, SEM error bars, min-count-per-bin floor. Two things should be visible at once: every curve
slopes up (the |Δairmass| effect is real WITHIN each band, not an airmass confound), and the curves
fan out -- higher-airmass bands are steeper and reach further right (the effect strengthens with
airmass).

Right: Spearman rho vs band-mean airmass, with bootstrap CIs -- turns the rho climb (previously only
visible in per-panel titles) into an explicit, quantitative upward line, i.e. the tan(zenith angle)
signature DAR predicts.
"""
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, '/global/u1/k/klaushon/telemetry_mining-trunk/analysis/dar_dipole')

DATA_PATH = '/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_lfield_dam_full.parquet'
FIG_DIR = '/global/u1/k/klaushon/telemetry_mining-trunk/notebooks/figures'

BANDS = [(1.1, 1.3), (1.3, 1.5), (1.5, 1.7), (1.7, 2.0)]


def binned_means(x, y, nbins=8, min_count=20):
    """Mean +/- SEM of y in nbins equal-width bins of x; a bin is dropped if it has fewer than
    min_count points (the whole point of the floor: an unconstrained tail bin -- like the single
    thin bin that wobbled in the per-band panels -- shouldn't get to fake a slope)."""
    edges = np.linspace(x.min(), x.max(), nbins + 1)
    idx = np.clip(np.digitize(x, edges) - 1, 0, nbins - 1)
    bx, by, bye = [], [], []
    for i in range(nbins):
        m = idx == i
        if m.sum() < min_count:
            continue
        bx.append(0.5 * (edges[i] + edges[i + 1]))
        by.append(y[m].mean())
        bye.append(y[m].std() / np.sqrt(m.sum()))
    return np.array(bx), np.array(by), np.array(bye)


def bootstrap_rho_ci(dam, lfield, n_boot=500, seed=0):
    rng = np.random.default_rng(seed)
    n = len(dam)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        boots[i] = stats.spearmanr(dam[idx], lfield[idx])[0]
    lo, hi = np.percentile(boots, [16, 84])
    return lo, hi


def main():
    df = pd.read_parquet(DATA_PATH)
    df = df[np.isfinite(df.L_field) & np.isfinite(df.dam)].copy()
    print(f'{len(df)} exposures with valid L_field and dam')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.5, 4.8))

    am_centers, rhos, rho_los, rho_his = [], [], [], []
    for i, (lo, hi) in enumerate(BANDS):
        b = df[(df.airmass >= lo) & (df.airmass < hi)]
        bx, by, bye = binned_means(b.dam.values, b.L_field.values, nbins=8, min_count=20)
        rho, p = stats.spearmanr(b.dam.values, b.L_field.values)
        rho_lo, rho_hi = bootstrap_rho_ci(b.dam.values, b.L_field.values)
        color = plt.cm.viridis(i / (len(BANDS) - 1))
        axL.errorbar(bx, by, yerr=bye, fmt='o-', color=color, capsize=2, ms=4,
                     label=f'am [{lo},{hi}):  n={len(b)}, ρ={rho:.2f}')
        am_centers.append(b.airmass.mean())
        rhos.append(rho)
        rho_los.append(rho - rho_lo)
        rho_his.append(rho_hi - rho)
        print(f'  am[{lo},{hi}): n={len(b)} rho={rho:.3f} [{rho_lo:.3f},{rho_hi:.3f}] p={p:.2g}')

    axL.set_ylim(0, 0.03)
    axL.set_xlabel(r'$|\Delta \mathrm{airmass}|$ (intra-exposure)')
    axL.set_ylabel(r'mean $L_\mathrm{field}$')
    axL.legend(fontsize=8.5, loc='upper left')
    axL.set_title(r'$L_\mathrm{field}$ rises with $|\Delta\mathrm{airmass}|$ in every band'
                  '\n-- and steepens with airmass', fontsize=11)

    axR.errorbar(am_centers, rhos, yerr=[rho_los, rho_his], fmt='s-', color='k', capsize=3, ms=6)
    axR.axhline(0, color='gray', lw=0.6)
    axR.set_xlabel('airmass (band mean)')
    axR.set_ylabel(r'Spearman $\rho$ [$L_\mathrm{field}$, $|\Delta\mathrm{airmass}|$]')
    axR.set_title('The excursion effect strengthens with airmass\n(the DAR tan(zenith angle) signature)', fontsize=11)

    fig.suptitle(f'$L_\\mathrm{{field}}$ tracks intra-exposure airmass excursion, at every airmass (n={len(df)})',
                 y=1.04, fontsize=12)
    fig.tight_layout()
    outpath = f'{FIG_DIR}/lfield_dam_summary_panel.png'
    fig.savefig(outpath, dpi=150, bbox_inches='tight')
    print(f'[out] {outpath}')


if __name__ == '__main__':
    main()
