"""Milestone 3, redone with L_see (from_mac_to_nersc.md, 2026-08-06 'Answer: Option 1' step 3):
swap the y-axis from the RCALIBFRAC-based whole-array median loss (artifact-compromised) to L_see,
the artifact-free GFA-imaging seeing-level scalar. Same physical rationale as the original run
(mirror_temp_flux_loss_test.py, kept as the RCALIBFRAC baseline): mirror-air convective plumes
degrade the PSF and should RAISE the whole-array loss, an isotropic, airmass-independent effect.

Being run interactively as an example (Klaus, 2026-08-06/07): iterate on plot type and exposure
selection with this script before writing a commented notebook, not a one-shot deliverable. Output
filenames are suffixed by the totteff cut so different selections don't clobber each other while
comparing.

Exposure selection: sequence='DESI' AND totteff>MIN_TOTTEFF (totteff is the effective-time quantity
used elsewhere in this investigation's own exposure selection, e.g. notebooks/data/README.md's
documented WHERE clause; Klaus's correction 2026-08-06 -- `actteff` is not a real DB column).
Default 600; pass --min-totteff to relax it and compare (e.g. 300).

UPDATED 2026-08-07 (from_mac_to_nersc.md 'Exposure integration landed' entry): L_see is now read via
the new `Exposure.L_see` attribute (src/telemetry_mining/exposure.py + fiber_loss.py) instead of a
bespoke local computation -- validated bit-identical to the direct-formula version this script used
before (see memory gfa-metrics-naming-and-availability). This is the intended end-user access
pattern: compute-direct at NERSC, transparent table-source fallback at KPNO.
"""
import argparse
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, '/global/u1/k/klaushon/telemetry_mining-trunk/src')
from telemetry_mining import db
from telemetry_mining.config import Config
from telemetry_mining.exposure import Exposure
from telemetry_mining.gfa import load_gfa_summary

REF_SEEING_ASEC = 1.1  # kept for the seeing-histogram reference line; matches fiber_loss.REF_SEEING_ASEC

DATA_DIR = '/global/u1/k/klaushon/telemetry_mining-trunk/data'
FIG_DIR = '/global/u1/k/klaushon/telemetry_mining-trunk/notebooks/figures'


def pull_telescope_temps(cfg, min_totteff):
    query = """
        SELECT id AS "EXPID",
               airmass,
               totteff,
               (telescope->>'mirror_temp')::float AS mirror_temp,
               (telescope->>'air_temp')::float AS air_temp
        FROM exposure.exposure
        WHERE sequence = 'DESI'
          AND totteff > %s
          AND telescope ? 'mirror_temp'
          AND telescope ? 'air_temp'
    """
    rows = db.fetch_all(cfg, query, (min_totteff,))
    df = pd.DataFrame(rows)
    print(f'DB pull: {len(df)} exposures with sequence=DESI, totteff>{min_totteff}, telescope temps present')
    return df


def build_lsee(cfg, expids):
    """L_see via the Exposure attribute (direct-compute path, validated bit-identical to the
    formula this script used directly before -- see memory gfa-metrics-naming-and-availability)."""
    gfa = load_gfa_summary(cfg)[['FWHM_ASEC']]
    gfa = gfa[gfa.index.isin(expids)]
    gfa = gfa[np.isfinite(gfa.FWHM_ASEC) & (gfa.FWHM_ASEC > 0)]
    print(f'{len(gfa)}/{len(expids)} exposures with valid GFA seeing')

    l_see = [Exposure(int(eid), config=cfg).L_see for eid in gfa.index]
    out = gfa.assign(L_see=l_see).reset_index()[['EXPID', 'L_see', 'FWHM_ASEC']]
    out = out[out.L_see.notna()]
    return out


def binned_means(x, y, nbins=20):
    edges = np.linspace(x.min(), x.max(), nbins + 1)
    binidx = np.clip(np.digitize(x, edges) - 1, 0, nbins - 1)
    bx, by, bye = [], [], []
    for i in range(nbins):
        m = binidx == i
        if m.sum() < 5:
            continue
        bx.append(0.5 * (edges[i] + edges[i + 1]))
        by.append(y[m].mean())
        bye.append(y[m].std() / np.sqrt(m.sum()))
    return np.array(bx), np.array(by), np.array(bye)


def plot_heatmap(x, y, bx, by, bye, out_path, title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    fig, ax = plt.subplots(figsize=(7, 5.5))
    h = ax.hist2d(x, y, bins=60, cmap='viridis', cmin=1, norm=LogNorm())
    cb = fig.colorbar(h[3], ax=ax)
    cb.set_label('count (log scale)')
    ax.errorbar(bx, by, yerr=bye, fmt='o-', color='red', lw=1.8, ms=5, capsize=3, label='binned mean')
    ax.set_xlabel('delta_T = mirror_temp - air_temp  [deg C]')
    ax.set_ylabel('L_see')
    ax.set_title(title)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f'Saved -> {out_path}')


def plot_binned(bx, by, bye, out_path, title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 5.5))
    ax.errorbar(bx, by, yerr=bye, fmt='o-', color='tab:blue', capsize=3, ms=6, label='binned mean')
    ax.set_xlabel('delta_T = mirror_temp - air_temp  [deg C]')
    ax.set_ylabel('L_see (bin mean)')
    ax.set_title(title)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f'Saved -> {out_path}')


def plot_seeing_hist(cfg, expids, out_path, title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    rows = db.fetch_all(cfg, 'SELECT id AS "EXPID", etcseeing FROM exposure.exposure WHERE id = ANY(%s)',
                         (list(expids),))
    etc = pd.DataFrame(rows).set_index('EXPID')
    gfa = load_gfa_summary(cfg)[['FWHM_ASEC']]
    gfa = gfa[gfa.index.isin(expids)]

    fig, ax = plt.subplots(figsize=(7, 5))
    bins = np.linspace(0.5, 2.5, 81)
    ax.hist(etc.etcseeing.dropna(), bins=bins, alpha=0.5,
            label=f'ETC seeing (median={etc.etcseeing.median():.3f}")', color='tab:blue')
    ax.hist(gfa.FWHM_ASEC.dropna(), bins=bins, alpha=0.5,
            label=f'GFA offline FWHM_ASEC (median={gfa.FWHM_ASEC.median():.3f}")', color='tab:orange')
    ax.axvline(REF_SEEING_ASEC, color='red', ls='--', lw=1.5, label=f'L_see reference ({REF_SEEING_ASEC}")')
    ax.set_xlabel('seeing FWHM [arcsec]')
    ax.set_ylabel('count')
    ax.set_title(title)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f'Saved -> {out_path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-totteff', type=float, default=600)
    args = ap.parse_args()
    tag = f'totteff{int(args.min_totteff)}'

    cfg = Config.default()
    temps = pull_telescope_temps(cfg, args.min_totteff)
    temps['delta_T'] = temps['mirror_temp'] - temps['air_temp']

    lsee = build_lsee(cfg, set(temps.EXPID))

    joined = temps.merge(lsee, on='EXPID', how='inner')
    print(f'Joined on EXPID: {len(joined)} exposures')

    out_data = f'{DATA_DIR}/dar_mirror_temp_lsee_{tag}.parquet'
    joined.to_parquet(out_data)
    print(f'Saved joined table -> {out_data}')

    x = joined['delta_T'].to_numpy()
    y = joined['L_see'].to_numpy()

    pearson_r, pearson_p = stats.pearsonr(x, y)
    spearman_r, spearman_p = stats.spearmanr(x, y)
    print(f'\nn = {len(joined)}')
    print(f'Pearson  r = {pearson_r:.4f}, p = {pearson_p:.3g}')
    print(f'Spearman r = {spearman_r:.4f}, p = {spearman_p:.3g}')

    bx, by, bye = binned_means(x, y, nbins=20)

    plot_heatmap(x, y, bx, by, bye, f'{FIG_DIR}/mirror_temp_lsee_heatmap_{tag}.png',
                 f'Mirror seeing proxy vs L_see -- log-count heatmap + binned curve\n'
                 f'(n={len(joined)}, sequence=DESI, totteff>{int(args.min_totteff)})')
    plot_binned(bx, by, bye, f'{FIG_DIR}/mirror_temp_lsee_binned_{tag}.png',
                f'Mirror seeing proxy vs L_see -- binned means\n'
                f'(n={len(joined)}, sequence=DESI, totteff>{int(args.min_totteff)})')
    plot_seeing_hist(cfg, set(joined.EXPID), f'{FIG_DIR}/seeing_check_hist_{tag}.png',
                      f'Seeing distributions (n={len(joined)}, sequence=DESI, totteff>{int(args.min_totteff)})')

    print(f'\nseeing summary this sample: GFA median={joined.FWHM_ASEC.median():.3f}"')


if __name__ == '__main__':
    main()
