"""Milestone 3 (from_mac_to_nersc.md, 2026-08-06 'Milestone 3, made concrete' entry): the external-
influence proof-of-concept for the whole-array (radial-only) fiber-loss channel. Physical rationale:
when the primary mirror is warmer than the ambient air, convective plumes off the glass produce
"mirror seeing" that degrades the delivered PSF and should RAISE the whole-array fiber loss -- an
isotropic, airmass-independent effect, distinct from the airmass-driven DAR signal this investigation
otherwise studies.

Pulls mirror_temp/air_temp from the `telescope` jsonb blob in exposure.exposure (DB-only, no FITS
reads -- Mac's instruction explicitly replaces an earlier, heavier per-exposure-header-pull plan),
computes delta_T = mirror_temp - air_temp per EXPID, and joins to the whole-array flux-loss level
(median loss = 1 - RCALIBFRAC over calibstars fibers, from notebooks/data/dar_calibstars_dataset.parquet)
on EXPID.
"""
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, '/global/u1/k/klaushon/telemetry_mining-trunk/src')
from telemetry_mining import db
from telemetry_mining.config import Config

OUT_DATA = '/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_mirror_temp_flux_loss.parquet'
OUT_FIG = '/global/u1/k/klaushon/telemetry_mining-trunk/notebooks/figures/mirror_temp_flux_loss_scatter.png'
CALIBSTARS_PATH = '/global/u1/k/klaushon/telemetry_mining-trunk/notebooks/data/dar_calibstars_dataset.parquet'


def pull_telescope_temps(cfg):
    query = """
        SELECT id AS expid,
               airmass,
               exptime,
               (telescope->>'mirror_temp')::float AS mirror_temp,
               (telescope->>'air_temp')::float AS air_temp
        FROM exposure.exposure
        WHERE sequence = 'DESI'
          AND exptime > 60
          AND telescope ? 'mirror_temp'
          AND telescope ? 'air_temp'
    """
    rows = db.fetch_all(cfg, query)
    df = pd.DataFrame(rows)
    print(f'DB pull: {len(df)} exposures with sequence=DESI, exptime>60, telescope temps present')
    return df


def whole_array_loss(calibstars_path):
    stars = pd.read_parquet(calibstars_path, columns=['EXPID', 'loss'])
    per_exp = stars.groupby('EXPID')['loss'].median().rename('median_loss').reset_index()
    print(f'Calibstars dataset: {len(stars)} star rows -> {len(per_exp)} exposures (median loss)')
    return per_exp


def main():
    cfg = Config.default()
    temps = pull_telescope_temps(cfg)
    temps['delta_T'] = temps['mirror_temp'] - temps['air_temp']

    loss = whole_array_loss(CALIBSTARS_PATH)

    joined = temps.merge(loss, left_on='expid', right_on='EXPID', how='inner')
    joined = joined.drop(columns=['EXPID'])
    print(f'Joined on EXPID: {len(joined)} exposures')

    joined.to_parquet(OUT_DATA)
    print(f'Saved joined table -> {OUT_DATA}')

    x = joined['delta_T'].to_numpy()
    y = joined['median_loss'].to_numpy()

    lr = stats.linregress(x, y)
    pearson_r, pearson_p = stats.pearsonr(x, y)
    spearman_r, spearman_p = stats.spearmanr(x, y)

    print()
    print(f'n = {len(joined)}')
    print(f'slope = {lr.slope:.6g} +/- {lr.stderr:.2g} (loss per degC), intercept = {lr.intercept:.6g}')
    print(f'Pearson  r = {pearson_r:.4f}, p = {pearson_p:.3g}')
    print(f'Spearman r = {spearman_r:.4f}, p = {spearman_p:.3g}')

    # Confound check: also fit within a narrow airmass band, since delta_T can correlate with
    # time-of-night/season and possibly airmass.
    am = joined['airmass'].to_numpy()
    band_lo, band_hi = 1.1, 1.3
    band_mask = (am >= band_lo) & (am <= band_hi)
    if band_mask.sum() > 30:
        lr_band = stats.linregress(x[band_mask], y[band_mask])
        pear_band = stats.pearsonr(x[band_mask], y[band_mask])
        spear_band = stats.spearmanr(x[band_mask], y[band_mask])
        print()
        print(f'Airmass band [{band_lo},{band_hi}]: n = {band_mask.sum()}')
        print(f'  slope = {lr_band.slope:.6g} +/- {lr_band.stderr:.2g}')
        print(f'  Pearson  r = {pear_band[0]:.4f}, p = {pear_band[1]:.3g}')
        print(f'  Spearman r = {spear_band[0]:.4f}, p = {spear_band[1]:.3g}')
    else:
        lr_band = None
        print(f'\nAirmass band [{band_lo},{band_hi}]: only {band_mask.sum()} exposures, skipping band fit')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 5.5))
    sc = ax.scatter(x, y, c=am, s=6, alpha=0.5, cmap='viridis', vmin=1.0, vmax=np.nanpercentile(am, 98))
    cb = fig.colorbar(sc, ax=ax)
    cb.set_label('airmass')

    xs = np.linspace(x.min(), x.max(), 50)
    ax.plot(xs, lr.intercept + lr.slope * xs, color='red', lw=1.5,
            label=f'all: slope={lr.slope:.2e}/degC (Pearson r={pearson_r:.3f}, p={pearson_p:.2g})')
    if lr_band is not None:
        ax.plot(xs, lr_band.intercept + lr_band.slope * xs, color='black', lw=1.5, ls='--',
                label=f'airmass {band_lo}-{band_hi}: slope={lr_band.slope:.2e}/degC '
                      f'(r={pear_band[0]:.3f}, p={pear_band[1]:.2g})')

    ax.set_xlabel('delta_T = mirror_temp - air_temp  [deg C]')
    ax.set_ylabel('whole-array median loss (1 - RCALIBFRAC)')
    ax.set_title(f'Mirror seeing proxy vs flux loss (n={len(joined)}, sequence=DESI, exptime>60)')
    ax.legend(fontsize=8, loc='best')
    ax.axhline(0, color='gray', lw=0.5)
    ax.axvline(0, color='gray', lw=0.5)
    fig.tight_layout()
    fig.savefig(OUT_FIG, dpi=150)
    print(f'\nSaved figure -> {OUT_FIG}')


if __name__ == '__main__':
    main()
