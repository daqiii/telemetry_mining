"""Calibrate sigma_eff (the loss<->offset parabola scale) from the REAL desimodel
FastFiberAcceptance table, then convert the measured rotating dipole/quadrupole
amplitudes to a physical offset delta0.

Requires desimodel + desimodeldata; point DESIMODEL at a desimodel-data checkout.
On the mac (2026-08-04): DESIMODEL=/Users/klaus/software/pyro5/desimodeldata-0.13.1

loss(offset) ~ offset^2 / (2 sigma_eff^2)   (small-offset limit)
delta0 = D_rot * sigma_eff / sqrt(2 * Q_rot)      (see robustness_and_delta0.py for D_rot,Q_rot)

Result (2026-08-04): sigma_eff ~= 52 um (fiber-size dominated, ~insensitive to seeing/radius)
                     delta0 ~= 8-12 um (central ~10 um = 0.14")
"""
import os, glob, numpy as np, pandas as pd
np.seterr(all='ignore')

root = os.environ.get('DESIMODEL_DATA_ROOT', '/Users/klaus/software/pyro5/desimodeldata-0.13.1')
hit = glob.glob(root + '/**/galsim-fiber-acceptance.fits', recursive=True)
assert hit, 'galsim-fiber-acceptance.fits not found under ' + root
os.environ['DESIMODEL'] = hit[0].split('/data/')[0]
import desimodel.io
from desimodel.fastfiberacceptance import FastFiberAcceptance
fa = FastFiberAcceptance()
ps = desimodel.io.load_platescale()
def plate_um_arcsec(r_mm):
    return np.interp(r_mm**2, ps['radius']**2,
                     np.sqrt(ps['radial_platescale']*ps['az_platescale']))

# seeing distribution of the high-airmass sample
df = pd.read_parquet('notebooks/data/dar_calibstars_dataset.parquet', columns=['EXPID','airmass','seeing'])
s = df[df.airmass > 1.6].drop_duplicates('EXPID')['seeing'].dropna()
sq = np.percentile(s, [25, 50, 75])
print("seeing FWHM(arcsec) airmass>1.6: 25/50/75 = %.2f/%.2f/%.2f (n=%d)" % (sq[0], sq[1], sq[2], len(s)))

def sigma_eff(seeing_fwhm, r_mm):
    sig = seeing_fwhm / 2.355 * plate_um_arcsec(r_mm)          # source sigma, focal-plane um
    ds = np.array([2., 4., 6., 8., 10.])
    A0 = fa.value('POINT', np.array([sig]), np.array([0.]))[0]
    loss = np.array([1 - fa.value('POINT', np.array([sig]), np.array([d]))[0] / A0 for d in ds])
    slope = np.polyfit(ds**2, loss, 1)[0]                      # loss ~ d^2 / (2 sigeff^2)
    return sig, 1.0 / np.sqrt(2 * slope)

print("\nsigma_eff (um) from the real table:")
print("%7s | r=0mm  r=300mm  r=410mm" % "seeing")
for sk in sq:
    print("%7.2f |  %5.1f   %5.1f   %5.1f" %
          (sk, sigma_eff(sk, 0)[1], sigma_eff(sk, 300)[1], sigma_eff(sk, 410)[1]))

# convert measured rotating amplitudes (airmass>1.6, from fit) to delta0
meas = {0.30: (0.0557, 0.0289), 0.15: (0.0436, 0.0235), 0.08: (0.0268, 0.0138)}   # clip:(D_rot,Q_rot)
se = sigma_eff(sq[1], 300)[1]
print("\nsigma_eff(median seeing, r=300mm) = %.1f um" % se)
print("delta0 = D_rot*sigma_eff/sqrt(2*Q_rot):")
for clip, (D, Q) in meas.items():
    print("  clip %.2f: D_rot=%.4f Q_rot=%.4f -> delta0 = %.1f um" % (clip, D, Q, D * se / np.sqrt(2 * Q)))
