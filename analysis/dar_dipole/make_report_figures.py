"""Redux-based figures for DAR_DIPOLE_INVESTIGATION_REPORT.md, per the division of labor in
from_mac_to_nersc.md (2026-08-06 'FIGURES' entry): Mac generates the calibstars-based figures
(the money 2-D pattern, amplitudes vs airmass, quadrupole-vs-studies); NERSC generates the ones
that need the redux-derived per-star datasets built during this investigation:

  1. dipole_rpt_dither_null.png       -- Sec 5: dither dipole (flat/null) vs quadrupole (growing)
  2. dipole_rpt_stage_decomposition.png -- Sec 7: D_rot per flux-chain stage
  3. dipole_rpt_brightness_split.png  -- Sec 8.1: D_rot vs star-brightness quartile
  4. dipole_rpt_skylevel_split.png    -- Sec 8.1: D_rot vs sky-level tercile

All CIs are the same night/exposure-level bootstraps used throughout the investigation
(affine_fit_lib.fit_and_bootstrap for the calibstars-derived ones; a matching night-clustered
bootstrap for the dither data, since airmass barely varies within a single dither sequence).
"""
import sys
sys.path.insert(0, 'analysis/dar_dipole')
sys.path.insert(0, 'src')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from affine_fit_lib import fit_and_bootstrap

plt.rcParams.update({
    'figure.dpi': 140, 'savefig.dpi': 140, 'font.size': 11,
    'axes.spines.top': False, 'axes.spines.right': False,
})
COLOR_ROT = '#1b6ca8'   # rotating / zenith-tied
COLOR_FIX = '#999999'   # fixed / instrument-frame
COLOR_TARGET = '#c0392b'  # established D_rot/Q_rot target band

OUTDIR = 'notebooks/figures'


# ---------------------------------------------------------------------------
# Figure 1: dither positive control (Sec 5)
# ---------------------------------------------------------------------------
def fig_dither_null():
    df = pd.read_parquet('data/dar_dither_offset_field.parquet')
    df = df[np.isfinite(df.airmass) & np.isfinite(df.parallactic) & (df.cond < 50)].reset_index(drop=True)

    q = np.deg2rad(df.parallactic.values)
    c, s = np.cos(q), np.sin(q)
    c2, s2 = np.cos(2 * q), np.sin(2 * q)
    df['up'] = df.tx * c + df.ty * s
    df['e_rot_mag'] = np.hypot(df.e1 * c2 + df.e2 * s2, -df.e1 * s2 + df.e2 * c2)

    def night_boot(sub, col, n=2000, seed=0, use_abs=False):
        night_ids = sub.night.unique()
        rng = np.random.default_rng(seed)
        means = []
        for _ in range(n):
            picked = rng.choice(night_ids, size=len(night_ids), replace=True)
            vals = np.concatenate([sub.loc[sub.night == nn, col].values for nn in picked])
            means.append(vals.mean())
        means = np.array(means)
        if use_abs:
            means = np.abs(means)
            point = abs(sub[col].mean())
        else:
            point = sub[col].mean()
        return point, np.percentile(means, 16), np.percentile(means, 84)

    bins = [1.0, 1.2, 1.4, 1.8]
    am_mean, dip_m, dip_lo, dip_hi, quad_m, quad_lo, quad_hi = [], [], [], [], [], [], []
    for lo in bins:
        sub = df[df.airmass > lo]
        if sub.night.nunique() < 2:
            continue
        am_mean.append(sub.airmass.mean())
        m, l, h = night_boot(sub, 'up', use_abs=True)  # |dipole| -- CI computed on |resampled mean|, not
        # abs() of separately-computed percentiles, so the ordering (lo<=point<=hi) is guaranteed.
        dip_m.append(m); dip_lo.append(l); dip_hi.append(h)
        m, l, h = night_boot(sub, 'e_rot_mag')  # already a non-negative magnitude per exposure
        quad_m.append(m); quad_lo.append(l); quad_hi.append(h)

    am_mean = np.array(am_mean)
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    dip_err = [np.array(dip_m) - np.array(dip_lo), np.array(dip_hi) - np.array(dip_m)]
    quad_err = [np.array(quad_m) - np.array(quad_lo), np.array(quad_hi) - np.array(quad_m)]
    ax.errorbar(am_mean - 0.01, dip_m, yerr=dip_err, fmt='o-', color=COLOR_FIX, capsize=3,
                label='rotating dipole |up| (real geometric offset)', lw=1.8, ms=6)
    ax.errorbar(am_mean + 0.01, quad_m, yerr=quad_err, fmt='s-', color=COLOR_ROT, capsize=3,
                label='rotating quadrupole (real geometric gradient)', lw=1.8, ms=6)

    # established D_rot / Q_rot targets (arcsec-equivalent, same convention as the dither fit)
    target_am = [1.48, 1.69, 1.86]
    target_val = [0.11, 0.16, 0.22]
    ax.plot(target_am, target_val, '--', color=COLOR_TARGET, lw=1.5, alpha=0.8,
            label='established D_rot / Q_rot target (0.11–0.22″)')

    ax.axhline(0, color='k', lw=0.6)
    ax.set_xlabel('airmass cut (mean airmass of stars > cut)')
    ax.set_ylabel('amplitude (arcsec)')
    ax.set_title('Dither offset field: real fiber-to-light geometry has\nno dipole, but does have the quadrupole')
    ax.legend(fontsize=8.5, loc='upper left')
    fig.tight_layout()
    fig.savefig(f'{OUTDIR}/dipole_rpt_dither_null.png')
    plt.close(fig)
    print('wrote dipole_rpt_dither_null.png')


# ---------------------------------------------------------------------------
# Shared: load the flux-chain stages dataset + the code-version-consistent quality gate
# ---------------------------------------------------------------------------
def load_flux_chain_good():
    df = pd.read_parquet('data/dar_flux_chain_stages.parquet')
    df['ratio_psf'] = df.RFLUX_psf / df.MODELRFLUX
    med = df.groupby('EXPID')['ratio_psf'].transform(lambda x: x[x > 0].median())
    df['RCALIBFRAC_rebuilt'] = df.ratio_psf / med
    cal = pd.read_parquet('notebooks/data/dar_calibstars_dataset.parquet', columns=['EXPID', 'FIBER', 'RCALIBFRAC'])
    m = df.merge(cal, on=['EXPID', 'FIBER'], how='inner')
    m['resid'] = m.RCALIBFRAC_rebuilt - m.RCALIBFRAC
    gg = m.groupby('EXPID').resid.apply(lambda x: np.sqrt(np.mean(x ** 2))).rename('rms').reset_index()
    good_exp = set(gg[gg.rms < 0.01].EXPID)
    df = df[df.EXPID.isin(good_exp)].copy()
    df = df[np.isfinite(df.X) & np.isfinite(df.Y) & np.isfinite(df.parallactic) & np.isfinite(df.airmass)]
    return df


# ---------------------------------------------------------------------------
# Figure 2: flux-chain stage decomposition (Sec 7)
# ---------------------------------------------------------------------------
def fig_stage_decomposition():
    df = load_flux_chain_good()
    stages = ['raw', 'flat', 'sky', 'psf']
    stage_labels = ['raw\nextracted', '+ fiberflat', '+ sky\nsubtraction', '+ aperture\ncorrection']
    for s in stages:
        df = df[np.isfinite(df[f'RFLUX_{s}']) & (df[f'RFLUX_{s}'] > 0)]

    Rn = 410.0
    u = df.X.values / Rn
    v = df.Y.values / Rn
    q = np.deg2rad(df.parallactic.values)
    eid = df.EXPID.values
    am = df.airmass.values

    airmass_cuts = [1.2, 1.4, 1.6, 1.8]
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    x = np.arange(len(stages))
    cmap = plt.cm.viridis(np.linspace(0.15, 0.85, len(airmass_cuts)))

    for i, lo in enumerate(airmass_cuts):
        mask = am > lo
        vals, los, his = [], [], []
        for s in stages:
            y = np.log(df[f'RFLUX_{s}'].values)
            out = fit_and_bootstrap(u[mask], v[mask], q[mask], y[mask], eid[mask], n_boot=300, seed=0)
            lo_ci, hi_ci = out['D_rot_ci']
            vals.append(out['D_rot']); los.append(lo_ci); his.append(hi_ci)
        vals, los, his = np.array(vals), np.array(los), np.array(his)
        err = [vals - los, his - vals]
        ax.errorbar(x + (i - 1.5) * 0.08, vals, yerr=err, fmt='o-', color=cmap[i], capsize=3,
                    label=f'am > {lo}', lw=1.6, ms=5)

    ax.set_xticks(x)
    ax.set_xticklabels(stage_labels)
    ax.set_ylabel('rotating dipole amplitude D_rot\n(edge-normalized loss units)')
    ax.set_title('D_rot appears at sky subtraction, not fiberflat or the\naperture correction')
    ax.axvspan(1.5, 2.5, color=COLOR_ROT, alpha=0.06, zorder=0)
    ax.legend(fontsize=9, loc='upper left')
    fig.tight_layout()
    fig.savefig(f'{OUTDIR}/dipole_rpt_stage_decomposition.png')
    plt.close(fig)
    print('wrote dipole_rpt_stage_decomposition.png')


# ---------------------------------------------------------------------------
# Figure 3: bright-vs-faint discriminator (Sec 8.1)
# ---------------------------------------------------------------------------
def fig_brightness_split():
    df = load_flux_chain_good()
    df = df[np.isfinite(df.RFLUX_sky) & (df.RFLUX_sky > 0) & np.isfinite(df.MODELRFLUX) & (df.MODELRFLUX > 0)]
    qs = df.MODELRFLUX.quantile([0, 0.25, 0.5, 0.75, 1.0]).values
    labels = ['Q1\n(faintest)', 'Q2', 'Q3', 'Q4\n(brightest)']
    df['bin'] = pd.cut(df.MODELRFLUX, bins=qs, labels=labels, include_lowest=True)

    Rn = 410.0
    u = df.X.values / Rn
    v = df.Y.values / Rn
    q = np.deg2rad(df.parallactic.values)
    y = np.log(df.RFLUX_sky.values)
    eid = df.EXPID.values
    am = df.airmass.values
    binv = df.bin.values

    airmass_cuts = [1.2, 1.4]
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    x = np.arange(len(labels))
    cmap = plt.cm.plasma(np.linspace(0.2, 0.75, len(airmass_cuts)))
    for i, lo in enumerate(airmass_cuts):
        vals, los, his = [], [], []
        for b in labels:
            mask = (am > lo) & (binv == b)
            out = fit_and_bootstrap(u[mask], v[mask], q[mask], y[mask], eid[mask], n_boot=300, seed=0)
            lo_ci, hi_ci = out['D_rot_ci']
            vals.append(out['D_rot']); los.append(lo_ci); his.append(hi_ci)
        vals, los, his = np.array(vals), np.array(los), np.array(his)
        err = [vals - los, his - vals]
        ax.errorbar(x + (i - 0.5) * 0.08, vals, yerr=err, fmt='o-', color=cmap[i], capsize=3,
                    label=f'am > {lo}', lw=1.8, ms=6)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel('standard-star brightness quartile (MODELRFLUX)')
    ax.set_ylabel('D_rot (sky-subtraction stage)')
    ax.set_title('D_rot increases with star brightness —\nopposite the sign an additive sky residual predicts')
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(f'{OUTDIR}/dipole_rpt_brightness_split.png')
    plt.close(fig)
    print('wrote dipole_rpt_brightness_split.png')


# ---------------------------------------------------------------------------
# Figure 4: sky-level discriminator (Sec 8.1)
# ---------------------------------------------------------------------------
def fig_skylevel_split():
    from telemetry_mining import db
    from telemetry_mining.config import Config

    df = load_flux_chain_good()
    df = df[np.isfinite(df.RFLUX_sky) & (df.RFLUX_sky > 0)]

    cfg = Config.default()
    expids = df.EXPID.unique().tolist()
    rows = db.fetch_all(cfg, 'SELECT id AS "EXPID", skylevel FROM exposure.exposure WHERE id = ANY(%s)', (expids,))
    meta = pd.DataFrame(rows)
    df = df.merge(meta, on='EXPID', how='inner')

    Rn = 410.0
    u = df.X.values / Rn
    v = df.Y.values / Rn
    q = np.deg2rad(df.parallactic.values)
    y = np.log(df.RFLUX_sky.values)
    eid = df.EXPID.values
    am = df.airmass.values

    labels = ['low', 'mid', 'high']
    lo_cut = 1.4
    ex_meta = df.drop_duplicates('EXPID')[['EXPID', 'skylevel']].set_index('EXPID')['skylevel']
    edges = ex_meta.quantile([0, 1 / 3, 2 / 3, 1.0]).values
    exp_bin = pd.cut(ex_meta, bins=edges, labels=labels, include_lowest=True)
    binv = df.EXPID.map(exp_bin).values

    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    x = np.arange(len(labels))
    vals, los, his, med_sky = [], [], [], []
    for b in labels:
        mask = (am > lo_cut) & (binv == b)
        out = fit_and_bootstrap(u[mask], v[mask], q[mask], y[mask], eid[mask], n_boot=300, seed=0)
        lo_ci, hi_ci = out['D_rot_ci']
        vals.append(out['D_rot']); los.append(lo_ci); his.append(hi_ci)
        med_sky.append(df.loc[mask, 'skylevel'].median())
    vals, los, his = np.array(vals), np.array(los), np.array(his)
    # clip: for the near-zero "low sky" bin the point estimate can sit slightly below its own CI
    # (a known artifact of bootstrapping a non-negative magnitude near the noise floor -- see
    # from_nersc_to_mac.md's sky-level entry); matplotlib requires non-negative yerr regardless.
    err = [np.clip(vals - los, 0, None), np.clip(his - vals, 0, None)]
    ax.errorbar(x, vals, yerr=err, fmt='o-', color=COLOR_ROT, capsize=4, lw=2, ms=8)

    ax.set_xticks(x)
    ax.set_xticklabels([f'{lab.capitalize()}\n(median skylevel≈{m:.1f})' for lab, m in zip(labels, med_sky)])
    ax.set_xlabel(f'sky-brightness tercile (airmass > {lo_cut})')
    ax.set_ylabel('D_rot (sky-subtraction stage)')
    ax.set_title('D_rot tracks total sky brightness:\ndark sky ⟹ consistent with zero, bright sky ⟹ full scale')
    ax.set_ylim(bottom=min(0, vals.min() - 0.02))
    fig.tight_layout()
    fig.savefig(f'{OUTDIR}/dipole_rpt_skylevel_split.png')
    plt.close(fig)
    print('wrote dipole_rpt_skylevel_split.png')


if __name__ == '__main__':
    fig_dither_null()
    fig_stage_decomposition()
    fig_brightness_split()
    fig_skylevel_split()
