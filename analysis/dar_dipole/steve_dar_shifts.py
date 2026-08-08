"""Compare Steve Kent's PlateMaker DAR (differential refraction) shift to the standard DAR
formula and to Weiner's quoted numbers, for a few (zd, airmass) pairs.

Steve's model (distort.py, refract=45"): a field-edge star at (xip,etap) [deg], parallactic psi, gets
the first-order refraction correction
    f1 = R*(1 + (sin psi tan z)^2),  f2 = f4 = sin psi cos psi R tan^2 z,  f3 = R*(1 + (cos psi tan z)^2)
    dxi  = -xip*f1 - etap*f2 ,  deta = -etap*f3 - xip*f4        (R = 45/206265 rad; aberration A dropped)
The DIFFERENTIAL refraction (edge star relative to field center) magnitude = the field compression.

Standard DAR compression: dR/dz * theta_field = R * sec^2 z * theta_field   (R in arcsec, theta in rad).
Both should give ~5" at z=60 (X=2), matching Weiner (4.8") -- because Steve's model IS standard DAR.

NB: this is the STATIC compression, which fiber placement removes. Our MEASURED quadrupole
(DeltaG ~ 0.2") is the intra-exposure RESIDUAL (~5% of the static compression).
"""
import numpy as np

REFRACT = 45.0            # arcsec (desi.par line 361, production)
R = REFRACT/206265.0      # radians
THETA_EDGE_DEG = 1.6      # DESI field radius, deg
theta = np.radians(THETA_EDGE_DEG)

def steve_edge_shift(zdeg, psideg):
    """distort.py refraction correction for an edge star; return |differential shift| in arcsec.
    Place the star at radius 1.6 deg along the zenith direction (angle psi from +eta/North)."""
    z = np.radians(zdeg); psi = np.radians(psideg)
    tz = np.tan(z)
    # star at radius theta along zenith: xip = theta_deg*sin(psi), etap = theta_deg*cos(psi)
    xip = THETA_EDGE_DEG*np.sin(psi); etap = THETA_EDGE_DEG*np.cos(psi)   # deg
    sp, cp = np.sin(psi), np.cos(psi)
    f1 = R*(1 + (sp*tz)**2); f2 = sp*cp*R*tz**2
    f3 = R*(1 + (cp*tz)**2); f4 = sp*cp*R*tz**2
    dxi  = -xip*f1 - etap*f2      # deg
    deta = -etap*f3 - xip*f4
    return np.hypot(dxi, deta)*3600.0    # arcsec

def standard_compression(zdeg):
    z = np.radians(zdeg)
    return REFRACT/np.cos(z)**2 * theta          # R*sec^2 z*theta_field, arcsec

def weiner_compression(zdeg):
    # Weiner: d_alt ~ 220 ppm * sec^2 z over 1.5 deg radius
    z = np.radians(zdeg)
    return 220e-6/np.cos(z)**2 * np.radians(1.5) * 206265.0   # arcsec

print("Field-edge DAR compression (arcsec), edge star along zenith (psi=0):")
print("%5s %8s | %10s %12s %10s | %s" % ("zd","airmass","Steve PM","std R*sec2z*θ","Weiner","Steve/std"))
for zd in [30, 45, 55, 60]:
    am = 1/np.cos(np.radians(zd))
    s  = steve_edge_shift(zd, 0.0)
    st = standard_compression(zd)
    w  = weiner_compression(zd)
    print("%5d %8.3f | %10.3f %12.3f %10.3f | %.3f" % (zd, am, s, st, w, s/st))

print("\nCheck psi-dependence of Steve's edge shift (z=60, X=2), a few parallactic angles:")
for psi in [0, 30, 45, 60, 90]:
    print("  psi=%3d deg: |shift| = %.3f arcsec" % (psi, steve_edge_shift(60, psi)))

print("\nRelation to our MEASURED quadrupole:")
print("  static compression at z~57 (X~1.86): %.2f arcsec (Steve/std)" % standard_compression(57.5))
print("  our measured intra-exposure quadrupole DeltaG at X=1.86: 0.22 arcsec")
print("  -> ratio ~ %.0f%% : the measured quadrupole is the intra-exposure residual of the static compression"
      % (0.22/standard_compression(57.5)*100))
