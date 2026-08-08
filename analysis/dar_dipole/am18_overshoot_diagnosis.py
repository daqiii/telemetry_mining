"""Diagnose the am>1.8 metric-B (scale+shear) Q_rot overshoot vs the dark-sky RCALIBFRAC target
(from_mac_to_nersc.md, 2026-08-06 'Step 2 reviewed -- diagnose the am>1.8 overshoot BEFORE step 3'
entry). Runs Mac's tests A-D in priority order.

Test A (outlier tail): split am>1.8 into 1.8-2.05 vs >2.05.
Test B (target error bar): bootstrap the dark-sky RCALIBFRAC Q_rot->ΔG target at am>1.8 (CI-vs-CI,
  not point-vs-CI). Reconstructs the sky-tercile split from the full population + a fresh skylevel
  DB pull, since the report's sky-split table numbers weren't left behind as a committed script --
  cross-checked against the report's stated 8.7/9.9/11.1 um at am>1.4/1.6/1.8 as a build sanity check.
Test C (metric vs geometry, not metric vs flux): compare metric-B ΔG at am>1.8 to the non-flux
  geometric drift probes already in data/dar_shear_drift.parquet (undirected RMS drift ~ Kirkby;
  zenith-projected mean drift ~ the DAR-loss-relevant directional piece).
Test D (leverage): jackknife the am>1.8 metric-B Q_rot by exposure (cheap: XtX/Xty are already
  per-exposure additive in affine_fit_lib, so leave-one-out = total minus one).
"""
import sys
sys.path.insert(0, 'analysis/dar_dipole')
sys.path.insert(0, 'src')

import numpy as np
import pandas as pd

from affine_fit_lib import design_matrix, within_demean, per_exp_normal, solve, amps, NAMES
from telemetry_mining import db
from telemetry_mining.config import Config

SIGMA_EFF_UM = 52.0
Rn = 410.0


def fit(u, v, q, y, eid):
    M = design_matrix(u, v, q)
    Xd, yd, e = within_demean(M, y, eid)
    XtX, Xty, yty, uniq = per_exp_normal(Xd, yd, e)
    beta = solve(XtX, Xty)
    Drot, Qrot, Dfix, Qfix = amps(beta)
    return dict(Q_rot=Qrot, D_rot=Drot, n_exp=len(uniq), XtX=XtX, Xty=Xty, uniq=uniq)


def bootstrap_ci(XtX, Xty, n_boot=300, seed=0):
    rng = np.random.default_rng(seed)
    n = XtX.shape[0]
    qs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        beta = solve(XtX[idx], Xty[idx])
        _, qr, _, _ = amps(beta)
        qs.append(qr)
    return np.percentile(qs, [16, 50, 84])


def dG(qrot):
    return SIGMA_EFF_UM * np.sqrt(2 * max(qrot, 0))


print('=' * 78)
print('TEST A: outlier tail -- am>1.8 population by sub-bin')
print('=' * 78)
v2 = pd.read_parquet('data/dar_gfa_fiber_loss_metric_v2.parquet')
v2_exp = v2.drop_duplicates('EXPID')[['EXPID', 'airmass']]
n_18_205 = ((v2_exp.airmass > 1.8) & (v2_exp.airmass <= 2.05)).sum()
n_205 = (v2_exp.airmass > 2.05).sum()
print(f'metric-B am>1.8 population: {len(v2_exp[v2_exp.airmass>1.8])} exposures total; '
      f'{n_18_205} in [1.8,2.05], {n_205} above 2.05')
print('-> essentially no >2.05 tail to trim; Test A premise (outlier tail) does not apply here.\n')

q = np.deg2rad(v2.parallactic.values)
eid = v2.EXPID.values
am = v2.airmass.values
u_, v_ = v2.U.values, v2.V.values
y_ = v2.loss.values
for lo, hi, lbl in [(1.8, 2.05, '[1.8,2.05]'), (2.05, 999, '>2.05')]:
    mask = (am > lo) & (am <= hi)
    if mask.sum() < 30:
        print(f'  {lbl}: n_row={mask.sum()} -- too few rows to fit, skip')
        continue
    r = fit(u_[mask], v_[mask], q[mask], y_[mask], eid[mask])
    print(f'  metric-B {lbl}: n_exp={r["n_exp"]}  Q_rot={r["Q_rot"]:.4f} -> ΔG={dG(r["Q_rot"]):.1f} um')


print()
print('=' * 78)
print('TEST B: bootstrap the dark-sky RCALIBFRAC target (CI-vs-CI)')
print('=' * 78)
cfg = Config.default()
cal = pd.read_parquet('notebooks/data/dar_calibstars_dataset.parquet',
                       columns=['EXPID', 'X', 'Y', 'loss', 'airmass'])
pt = pd.read_csv('data/dar_exposure_pointing.csv', usecols=['EXPID', 'parallactic'])
cal = cal.merge(pt, on='EXPID', how='inner')
cal = cal[np.isfinite(cal.loss) & cal.loss.between(-0.3, 0.3) &
          np.isfinite(cal.X) & np.isfinite(cal.Y) & np.isfinite(cal.parallactic)]

expids = cal.EXPID.unique().tolist()
rows = db.fetch_all(cfg, 'SELECT id AS "EXPID", skylevel FROM exposure.exposure WHERE id = ANY(%s)', (expids,))
sky = pd.DataFrame(rows)
cal = cal.merge(sky, on='EXPID', how='inner')
cal = cal[np.isfinite(cal.skylevel)]
print(f'{len(cal)} star-rows / {cal.EXPID.nunique()} exposures with skylevel')

u = cal.X.values / Rn
v = cal.Y.values / Rn
q_all = np.deg2rad(cal.parallactic.values)
y_all = cal.loss.values.astype(float)
eid_all = cal.EXPID.values
am_all = cal.airmass.values

print('\nSanity check vs report\'s stated dark-sky targets (8.7/9.9/11.1 um @ am>1.4/1.6/1.8):')
for lo in [1.4, 1.6, 1.8]:
    ex_meta = cal[am_all > lo].drop_duplicates('EXPID')[['EXPID', 'skylevel']].set_index('EXPID')['skylevel']
    if len(ex_meta) < 30:
        print(f'  am>{lo}: too few exposures for a tercile split, skip')
        continue
    edges = ex_meta.quantile([0, 1 / 3, 2 / 3, 1.0]).values
    exp_bin = pd.cut(ex_meta, bins=edges, labels=['low', 'mid', 'high'], include_lowest=True, duplicates='drop')
    binv = cal.EXPID.map(exp_bin).values
    mask = (am_all > lo) & (binv == 'low')
    if mask.sum() < 200:
        print(f'  am>{lo} low-sky: n_row={mask.sum()} too few, skip')
        continue
    r = fit(u[mask], v[mask], q_all[mask], y_all[mask], eid_all[mask])
    lo_ci, med_ci, hi_ci = bootstrap_ci(r['XtX'], r['Xty'])
    print(f'  am>{lo} low-sky (dark): n_exp={r["n_exp"]:4d}  Q_rot={r["Q_rot"]:.4f} '
          f'[{lo_ci:.4f},{hi_ci:.4f}]  ->  ΔG={dG(r["Q_rot"]):.1f} [{dG(lo_ci):.1f},{dG(hi_ci):.1f}] um')

print('\nam>1.8 low-sky target, CI-vs-metric-B-CI comparison (metric-B was 16.3 [15.1,17.4] um):')
ex_meta = cal[am_all > 1.8].drop_duplicates('EXPID')[['EXPID', 'skylevel']].set_index('EXPID')['skylevel']
edges = ex_meta.quantile([0, 1 / 3, 2 / 3, 1.0]).values
exp_bin = pd.cut(ex_meta, bins=edges, labels=['low', 'mid', 'high'], include_lowest=True, duplicates='drop')
binv = cal.EXPID.map(exp_bin).values
mask = (am_all > 1.8) & (binv == 'low')
r18 = fit(u[mask], v[mask], q_all[mask], y_all[mask], eid_all[mask])
lo_ci, med_ci, hi_ci = bootstrap_ci(r18['XtX'], r18['Xty'], n_boot=1000)
print(f'  am>1.8 low-sky: n_exp={r18["n_exp"]}  Q_rot={r18["Q_rot"]:.4f} [{lo_ci:.4f},{hi_ci:.4f}]  '
      f'->  ΔG={dG(r18["Q_rot"]):.1f} [{dG(lo_ci):.1f},{dG(hi_ci):.1f}] um')


print()
print('=' * 78)
print('TEST C: metric-B vs non-flux geometric drift probes at am>1.8')
print('=' * 78)
drift = pd.read_parquet('data/dar_shear_drift.parquet')
m18 = drift.airmass > 1.8
print(f'n={m18.sum()} exposures with a good affine drift fit at am>1.8')
undirected_rms_um = (drift.rms_rot[m18] * Rn * 1000).mean()
zenith_mean_um = (drift.mean_rot_mag[m18] * Rn * 1000).mean()
print(f'  undirected RMS drift (~Kirkby-style motion amplitude):  {undirected_rms_um:.2f} um')
print(f'  zenith-projected mean drift (DAR-loss-relevant piece):   {zenith_mean_um:.2f} um')
print(f'  metric-B ΔG (scale+shear, this session):                 16.3 [15.1,17.4] um')
print(f'  dark-sky RCALIBFRAC target (report):                     11.1 um')


print()
print('=' * 78)
print('TEST D: jackknife metric-B Q_rot at am>1.8 by exposure (leverage check)')
print('=' * 78)
mask18 = am > 1.8
r18b = fit(u_[mask18], v_[mask18], q[mask18], y_[mask18], eid[mask18])
XtX, Xty, uniq = r18b['XtX'], r18b['Xty'], r18b['uniq']
A_tot, b_tot = XtX.sum(0), Xty.sum(0)
jk_qrot = np.empty(len(uniq))
for i in range(len(uniq)):
    A_loo = A_tot - XtX[i]
    b_loo = b_tot - Xty[i]
    beta_loo = np.linalg.solve(A_loo, b_loo)
    _, qr, _, _ = amps(beta_loo)
    jk_qrot[i] = qr
full_qrot = r18b['Q_rot']
delta = jk_qrot - full_qrot
order = np.argsort(np.abs(delta))[::-1]
print(f'full-sample Q_rot={full_qrot:.4f} (n_exp={len(uniq)})')
print('top 8 highest-leverage exposures (Q_rot shift when excluded):')
for i in order[:8]:
    print(f'  EXPID={uniq[i]}  Q_rot_excl={jk_qrot[i]:.4f}  delta={delta[i]:+.5f}')
print(f'jackknife Q_rot spread: min={jk_qrot.min():.4f} max={jk_qrot.max():.4f} '
      f'(vs full {full_qrot:.4f}) -- large spread relative to full value would flag a few '
      f'high-leverage exposures driving the result')
