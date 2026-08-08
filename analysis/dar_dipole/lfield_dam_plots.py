"""Core analysis plots for the L_field vs intra-exposure |Δairmass| example (from_mac_to_nersc.md,
2026-08-07 'Next example' entry) -- reads the full-coverage table built by lfield_dam_test.py.

1. Overall scatter (colored by airmass) + binned medians -- the headline relationship.
2. Airmass-controlled panel -- within a fixed airmass band, L_field still rises with dam. This is
   the point of the whole example: it's what separates "L_field tracks intra-exposure drift" from
   the much less interesting "L_field tracks airmass, and dam happens to correlate with airmass too"
   (corr(dam,airmass)=0.42 on the validation subset, real but far from a confound-fatal 1.0).
"""
import argparse
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, '/global/u1/k/klaushon/telemetry_mining-trunk/analysis/dar_dipole')

DATA_DIR = '/global/u1/k/klaushon/telemetry_mining-trunk/data'
FIG_DIR = '/global/u1/k/klaushon/telemetry_mining-trunk/notebooks/figures'


def binned_medians(x, y, nbins=20):
    edges = np.linspace(x.min(), x.max(), nbins + 1)
    binidx = np.clip(np.digitize(x, edges) - 1, 0, nbins - 1)
    bx, by, bn = [], [], []
    for i in range(nbins):
        m = binidx == i
        if m.sum() < 5:
            continue
        bx.append(0.5 * (edges[i] + edges[i + 1]))
        by.append(np.median(y[m]))
        bn.append(m.sum())
    return np.array(bx), np.array(by), np.array(bn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=f'{DATA_DIR}/dar_lfield_dam_full.parquet')
    ap.add_argument('--tag', default='full', help='suffix for output figure filenames')
    args = ap.parse_args()

    df = pd.read_parquet(args.data)
    df = df[np.isfinite(df.L_field) & np.isfinite(df.dam)].copy()
    print(f'{len(df)} exposures with valid L_field and dam ({args.tag})')

    x = df.dam.to_numpy()
    y = df.L_field.to_numpy()
    am = df.airmass.to_numpy()

    r, p = stats.pearsonr(x, y)
    rho, pr = stats.spearmanr(x, y)
    print(f'overall: Pearson r={r:.4f} (p={p:.2g}), Spearman rho={rho:.4f} (p={pr:.2g})')
    r_am, _ = stats.pearsonr(x, am)
    print(f'corr(dam, airmass) = {r_am:.3f}  (this is the confound to control for below)')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    bx, by, bn = binned_medians(x, y, nbins=20)

    # --- Plot 1: overall scatter + binned medians ---
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    sc = ax.scatter(x, y, c=am, s=4, alpha=0.3, cmap='viridis', vmin=1.0, vmax=np.nanpercentile(am, 98))
    cb = fig.colorbar(sc, ax=ax)
    cb.set_label('airmass')
    ax.plot(bx, by, 'o-', color='red', lw=1.8, ms=5, label='binned median')
    ax.set_xlabel(r'$|\Delta \mathrm{airmass}|$ (intra-exposure)')
    ax.set_ylabel(r'$L_\mathrm{field}$')
    ax.set_title(f'$L_\\mathrm{{field}}$ vs intra-exposure $|\\Delta \\mathrm{{airmass}}|$ (n={len(df)}, {args.tag})')
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(f'{FIG_DIR}/lfield_dam_scatter_{args.tag}.png', dpi=150)
    print(f'[out] {FIG_DIR}/lfield_dam_scatter_{args.tag}.png')

    # --- Plot 2: airmass-controlled panel ---
    bands = [(1.1, 1.3), (1.3, 1.5), (1.5, 1.7), (1.7, 2.0)]
    fig, axes = plt.subplots(1, len(bands), figsize=(4.2 * len(bands), 4.6), sharey=True)
    for ax, (lo, hi) in zip(axes, bands):
        m = (am >= lo) & (am < hi)
        if m.sum() < 50:
            ax.set_title(f'airmass [{lo},{hi})\nn={m.sum()} too few')
            continue
        rho_b, p_b = stats.spearmanr(x[m], y[m])
        bxb, byb, bnb = binned_medians(x[m], y[m], nbins=10)
        ax.scatter(x[m], y[m], s=4, alpha=0.25, color='tab:gray')
        ax.plot(bxb, byb, 'o-', color='tab:red', lw=1.8, ms=5)
        ax.set_title(f'airmass [{lo},{hi})\nn={m.sum()}, Spearman ρ={rho_b:.3f} (p={p_b:.1g})')
        ax.set_xlabel(r'$|\Delta \mathrm{airmass}|$')
    axes[0].set_ylabel(r'$L_\mathrm{field}$')
    fig.suptitle(r'Airmass-controlled: $L_\mathrm{field}$ still rises with $|\Delta\mathrm{airmass}|$ within each band'
                 f' ({args.tag})')
    fig.tight_layout()
    fig.savefig(f'{FIG_DIR}/lfield_dam_airmass_controlled_{args.tag}.png', dpi=150)
    print(f'[out] {FIG_DIR}/lfield_dam_airmass_controlled_{args.tag}.png')

    # quintile medians (Mac's preview-style summary)
    q = pd.qcut(df.dam, 5, labels=False)
    med = df.groupby(q).L_field.median()
    print('quintile medians:', med.values)


if __name__ == '__main__':
    main()
