"""Test 1 (DAR_DIPOLE_NERSC_HANDOFF.md): decompose the applied acquisition/pointing
boresight offset into a zenith-projected (parallactic-direction) component vs an
orthogonal component, vs airmass, and compare to the measured loss-dipole D_rot
(zenith, grows with tan z, ~0.14") / D_fix (fixed, flat, ~half of D_rot).

Source of the "applied offset": `tcs.mount_offset_ra/dec` in exposure.exposure
(arcsec, equatorial), cross-checked against the live PlateMaker telemetry mirror
`telemetry.ocs_gfadata.xi0/eta0` (degrees). Confirmed via DervishTools-python
(~/DervishTools-python/python/desi/multiproc.py, ~line 447-469): xi0/eta0 are the
translation-only term of a 4-parameter (translate+rotate+scale) least-squares fit
of observed GFA guide-star positions against the Gaia catalog -- source's own
comment: "xi0 and eta0 are the pointing corrections." This is the literal applied
acquisition boresight offset, distinct from distort.py's differential/rotation
terms (already ruled out) and the open-loop gravity/GFA-deformation model
(telCenter/gfaCoeff, already ruled out, ~0.02" net).

Decomposition: for parallactic angle q (same column/convention already used in
fit_dipole_quadrupole.py), the zenith direction on the sky is at position angle q
from North (standard convention), so projecting the equatorial offset
(ra_off, dec_off) onto (sin q, cos q) isolates the "along the zenith direction"
component and (cos q, -sin q) the orthogonal one. The correct rotation sense
(which of q vs -q, which axis is zenith vs orthogonal) is NOT independently
verified against PlateMaker's internal xi/eta axis convention, so both senses
are reported -- pick whichever shows the expected airmass-growing signature and
flag it as empirical, not assumed.
"""
import pandas as pd, numpy as np

np.seterr(all='ignore')

df = pd.read_parquet('data/dar_acquisition_offset.parquet')

print('=== Using tcs.mount_offset_ra/dec (arcsec) ===')
d = df[df.mount_offset_ra.notna() & df.mount_offset_dec.notna() &
       np.isfinite(df.airmass) & np.isfinite(df.parallactic) & np.isfinite(df.zd_db)]
print(f'n exposures: {len(d)}')

q = np.deg2rad(d.parallactic.values)
c, s = np.cos(q), np.sin(q)
ra_off = d.mount_offset_ra.values
dec_off = d.mount_offset_dec.values
am = d.airmass.values
tanz = np.tan(np.deg2rad(d.zd_db.values))

# convention A: zenith=(sin q, cos q), orthogonal=(cos q, -sin q)
zenA = ra_off * s + dec_off * c
orthA = ra_off * c - dec_off * s
# convention B: zenith=(cos q, sin q), orthogonal=(-sin q, cos q)
zenB = ra_off * c + dec_off * s
orthB = -ra_off * s + dec_off * c


def boot_mean(x, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), (n, len(x)))
    means = x[idx].mean(axis=1)
    return x.mean(), np.percentile(means, 16), np.percentile(means, 84)


print(f'\nmedian |mount_offset| (arcsec): {np.median(np.hypot(ra_off, dec_off)):.2f}\n')

header = (f"{'bin':9s} {'n':>6s} | {'zenA':>8s} {'[16,84]':>18s} | {'orthA':>8s} {'[16,84]':>18s} | "
          f"{'zenB':>8s} {'[16,84]':>18s} | {'orthB':>8s} {'[16,84]':>18s}")
print(header)
for lo in [1.0, 1.2, 1.4, 1.6, 1.8]:
    m = am > lo
    za, zal, zah = boot_mean(zenA[m])
    oa, oal, oah = boot_mean(orthA[m])
    zb, zbl, zbh = boot_mean(zenB[m])
    ob, obl, obh = boot_mean(orthB[m])
    print(f"am>{lo:<5.1f} {m.sum():6d} | {za:8.3f} [{zal:7.3f},{zah:7.3f}] | {oa:8.3f} [{oal:7.3f},{oah:7.3f}] | "
          f"{zb:8.3f} [{zbl:7.3f},{zbh:7.3f}] | {ob:8.3f} [{obl:7.3f},{obh:7.3f}]")

print('\nRegression: offset_component = a + b*tan(z)  (all airmass>1.0, n=%d)' % len(d))
A = np.column_stack([np.ones(len(d)), tanz])
XtX_inv = np.linalg.inv(A.T @ A)
for name, y in [('zenA', zenA), ('orthA', orthA), ('zenB', zenB), ('orthB', orthB)]:
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    dof = len(y) - 2
    sigma2 = (resid @ resid) / dof
    se = np.sqrt(sigma2 * np.diag(XtX_inv))
    print(f'  {name:6s}: a={beta[0]:8.3f}+-{se[0]:.3f}   b={beta[1]:8.3f}+-{se[1]:.3f} arcsec/tan(z)')

print('\n=== Cross-check using telemetry.ocs_gfadata xi0/eta0 (degrees -> arcsec) ===')
d2 = df[df.xi0.notna() & df.eta0.notna() &
        np.isfinite(df.airmass) & np.isfinite(df.parallactic) & np.isfinite(df.zd_db)]
print(f'n exposures: {len(d2)}')
q2 = np.deg2rad(d2.parallactic.values)
c2, s2 = np.cos(q2), np.sin(q2)
xi0 = d2.xi0.values * 3600.0
eta0 = d2.eta0.values * 3600.0
am2 = d2.airmass.values
tanz2 = np.tan(np.deg2rad(d2.zd_db.values))
zenA2 = xi0 * s2 + eta0 * c2
orthA2 = xi0 * c2 - eta0 * s2
zenB2 = xi0 * c2 + eta0 * s2
orthB2 = -xi0 * s2 + eta0 * c2

print(header)
for lo in [1.0, 1.2, 1.4, 1.6, 1.8]:
    m = am2 > lo
    za, zal, zah = boot_mean(zenA2[m])
    oa, oal, oah = boot_mean(orthA2[m])
    zb, zbl, zbh = boot_mean(zenB2[m])
    ob, obl, obh = boot_mean(orthB2[m])
    print(f"am>{lo:<5.1f} {m.sum():6d} | {za:8.3f} [{zal:7.3f},{zah:7.3f}] | {oa:8.3f} [{oal:7.3f},{oah:7.3f}] | "
          f"{zb:8.3f} [{zbl:7.3f},{zbh:7.3f}] | {ob:8.3f} [{obl:7.3f},{obh:7.3f}]")
