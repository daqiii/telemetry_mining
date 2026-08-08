"""Task 2, design v2 (from_mac_to_nersc.md, 2026-08-06 'Task 1 nailed it — GREEN-LIGHT Task 2' entry):
rebuild the GFA fiber-loss metric's spatial (DAR) input on the ZENITH-PROJECTED intra-exposure drift
(Task 1's mean_de1_rot/mean_de2_rot from shear_drift_test.py), not the static PMGWCS snapshot (misses
intra-exposure accumulation) and not the raw translation `t` (guide-loop-corrected, never reaches the
fibers -- see the Milestone-1 gate failure).

UPDATED 2026-08-06 ('Task 2's zero-quadrupole is a real finding' entry, step 2/'Complete B' of the
follow-on 'Answer: Option 1' entry): the first pass here used shear (e1,e2) ONLY, which is provably
radial-only -- |shear.r|^2=(e1^2+e2^2)(u^2+v^2) exactly, verified to 1e-16 -- so its loss carried ZERO
quadrupole by construction, not a bug. The DAR field-differential is a 1-D zenith compression, which
decomposes into EQUAL PARTS isotropic scale and shear (G = (c/2)I + (c/2)*shear); the loss quadrupole is
specifically the scale x shear cross-term. Fix: add the isotropic scale drift `mean_ds` (now tracked by
shear_drift_test.py alongside e1,e2) into the field.

Construction per exposure:
  1. mean_de1_rot, mean_de2_rot are already in the ZENITH frame (rotated by 2q before averaging over
     frames). To evaluate a field on the FIXED (u,v) grid, rotate back to the fixed CS5 frame by -2q
     (shear is spin-2, same convention as the rest of this investigation) -- this reconstructs, per
     exposure, "the fixed-frame shear that would produce this exposure's own zenith-projected drift."
     mean_ds is rotation-invariant (isotropic), so it needs no such rotation.
  2. delta_DAR(r) = G . r, G = scale+shear (Test 4's per-frame model dX=s*X+e1*X+e2*Y,
     dY=s*Y+e2*X-e1*Y with the translation `t` and rotation `theta` dropped -- guide-loop-corrected and
     hexapod-corrected respectively, never delivered to the fibers, per the Milestone-1 gate failure).
  3. FF(r) = FastFiberAcceptance("POINT", sigma, |delta_DAR(r)|), sigma from GFA FWHM_ASEC (real
     platescale, consistent with Milestone 1).
  4. Demeaned per exposure (field-mean=1) -> loss(r) = 1 - GFIBERFRAC(r), the artifact-free spatial
     metric output B.

Validation: Task 1 already confirmed the arcsec-space (no-FF-round-trip) match -- zenith-projected
drift 11.20 um vs RCALIBFRAC dark-sky Q_rot ~11 um at am>1.8 (from_nersc_to_mac.md; for a 1-D compression
scale=shear so the shear amplitude alone was already a valid ΔG proxy -- this fix doesn't change that
check). This script's own refit of the dipole/quadrupole on the metric's OUTPUT (after the FF/loss
nonlinearity) is now a MEANINGFUL check (scale+shear genuinely produces a quadrupole; the earlier
"no round-trip needed" caveat was specific to the shear-only build) -- target is the dark-sky (low-sky
tercile) Q_rot->ΔG from DAR_FIBER_LOSS_REPORT.md's sky-split table: 8.7/9.9/11.1 um at am>1.4/1.6/1.8.
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
from gfa_fiber_loss_metric import build_grid, platescale_um_per_arcsec, FIELD_RADIUS_MM

FA = FastFiberAcceptance()
PS = load_platescale()


def main():
    cfg = Config.default()
    drift = pd.read_parquet('data/dar_shear_drift.parquet')
    drift = drift[np.isfinite(drift.parallactic) & np.isfinite(drift.airmass) &
                  np.isfinite(drift.mean_de1_rot) & np.isfinite(drift.mean_de2_rot) &
                  np.isfinite(drift.mean_ds)]
    print(f'{len(drift)} exposures with drift-shear+scale')

    # rotate the zenith-frame drift shear back to the fixed CS5 frame, per exposure's own q
    q2 = 2 * np.deg2rad(drift.parallactic.values)
    c2, s2 = np.cos(q2), np.sin(q2)
    e1r, e2r = drift.mean_de1_rot.values, drift.mean_de2_rot.values
    # inverse of (rot by +q2): fixed = R(-q2) . rot
    e1_fixed = e1r * c2 - e2r * s2
    e2_fixed = e1r * s2 + e2r * c2
    # scale is isotropic (rotation-invariant) -- no frame rotation needed
    s_fixed = drift.mean_ds.values
    drift = drift.assign(e1_fixed=e1_fixed, e2_fixed=e2_fixed, s_fixed=s_fixed)

    # --- consistency check FIRST (Mac's from_mac_to_nersc.md 'Step 2 detail' entry, 2026-08-06):
    # for a pure 1-D DAR zenith compression, scale = shear in magnitude (both = c/2), so population
    # mean |ds| should track the zenith-projected shear-drift magnitude (mean_rot_mag). If ds >> shear,
    # the scale drift carries non-DAR isotropic contamination (focus/thermal plate-scale drift) that
    # would inject a spurious quadrupole -- check BEFORE trusting the field build below.
    print('\n=== Consistency check: |ds| vs zenith-projected shear-drift magnitude, by airmass ===')
    am_all = drift.airmass.values
    abs_ds = np.abs(drift.mean_ds.values)
    shear_mag = drift.mean_rot_mag.values
    for lo in [1.4, 1.6, 1.8]:
        m = am_all > lo
        if m.sum() < 50:
            continue
        print(f'am>{lo}: n={m.sum():4d}  mean|ds|={abs_ds[m].mean():.5f}  '
              f'mean shear_mag={shear_mag[m].mean():.5f}  ratio={abs_ds[m].mean()/shear_mag[m].mean():.2f}')

    gfa = load_gfa_summary(cfg)[['FWHM_ASEC']]
    df = drift.merge(gfa, left_on='EXPID', right_index=True, how='inner')
    df = df[np.isfinite(df.FWHM_ASEC) & (df.FWHM_ASEC > 0)]
    print(f'{len(df)} exposures after joining GFA seeing')

    U, V = build_grid(n=7)
    n_grid = len(U)

    s = df.s_fixed.values[:, None]
    e1 = df.e1_fixed.values[:, None]
    e2 = df.e2_fixed.values[:, None]
    Ug = U[None, :]; Vg = V[None, :]

    # G = scale + shear (Test 4's per-frame model with t, theta dropped):
    #   dX = s*X + e1*X + e2*Y ,  dY = s*Y + e2*X - e1*Y
    dRA = s * Ug + e1 * Ug + e2 * Vg   # DIMENSIONLESS (mm-fraction, from the ETC/CS5 mm-based fit,
    dDec = s * Vg + e2 * Ug - e1 * Vg  # NOT arcsec like Milestone 1's PMGWCS e1,e2)
    delta_um = np.hypot(dRA, dDec) * FIELD_RADIUS_MM * 1000.  # -> physical mm -> um directly, no
    # platescale step: this is already a physical-length fraction, not an angular quantity.

    r_mm = np.sqrt(Ug ** 2 + Vg ** 2) * FIELD_RADIUS_MM
    ps = platescale_um_per_arcsec(r_mm)  # still needed for sigma, which IS angular (seeing FWHM in arcsec)
    sigma_um = (df.FWHM_ASEC.values / 2.35)[:, None] * ps

    FF = FA.value('POINT', sigma_um.ravel(), delta_um.ravel()).reshape(delta_um.shape)
    field_mean_FF = FF.mean(axis=1, keepdims=True)
    loss = 1.0 - FF / field_mean_FF

    n_exp = len(df)
    out = pd.DataFrame({
        'EXPID': np.repeat(df.EXPID.values, n_grid),
        'airmass': np.repeat(df.airmass.values, n_grid),
        'parallactic': np.repeat(df.parallactic.values, n_grid),
        'U': np.tile(U, n_exp), 'V': np.tile(V, n_exp),
        'loss': loss.ravel(),
    })
    out.to_parquet('data/dar_gfa_fiber_loss_metric_v2.parquet')
    print(f'[out] data/dar_gfa_fiber_loss_metric_v2.parquet: {len(out)} rows')

    q = np.deg2rad(out.parallactic.values)
    eid = out.EXPID.values
    am = out.airmass.values
    u = out.U.values
    v = out.V.values
    y = out.loss.values

    SIGMA_EFF_UM = 52.0
    # dark-sky (low-sky-tercile) RCALIBFRAC Q_rot -> ΔG, from DAR_FIBER_LOSS_REPORT.md's sky-split
    # table -- the clean, artifact-free DAR target this scale+shear metric should reproduce.
    DARK_SKY_TARGET_UM = {1.4: 8.7, 1.6: 9.9, 1.8: 11.1}
    print('\n=== Task 2 metric (scale+shear drift, FF round-trip): refit dipole/quadrupole ===')
    print('Target (dark-sky RCALIBFRAC Q_rot -> ΔG): 8.7/9.9/11.1 um at am>1.4/1.6/1.8')
    for lo in [1.4, 1.6, 1.8]:
        mask = am > lo
        if mask.sum() < 200:
            print(f'am>{lo}: too few, skip')
            continue
        r = fit_and_bootstrap(u[mask], v[mask], q[mask], y[mask], eid[mask], n_boot=300, seed=0)
        dl, dh = r['D_rot_ci']; ql, qh = r['Q_rot_ci']
        dG = SIGMA_EFF_UM * np.sqrt(2 * r['Q_rot'])
        dG_lo = SIGMA_EFF_UM * np.sqrt(2 * max(ql, 0)); dG_hi = SIGMA_EFF_UM * np.sqrt(2 * max(qh, 0))
        print(f"am>{lo}: n_exp={r['n_exp']:4d}  D_rot={r['D_rot']:.4f} [{dl:.4f},{dh:.4f}]  "
              f"Q_rot={r['Q_rot']:.4f} [{ql:.4f},{qh:.4f}]  ->  ΔG={dG:.1f} [{dG_lo:.1f},{dG_hi:.1f}] um "
              f"(target {DARK_SKY_TARGET_UM[lo]} um)")


if __name__ == '__main__':
    main()
