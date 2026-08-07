"""Direct computation of the two GFA fiber-loss metrics, L_see and L_field.

See docs/FIBER_LOSS_METRICS.md. Both are artifact-free (built from GFA imaging, never sky-subtracted
flux) and dipole-free:

  L_see   whole-array seeing loss level = 1 - A(sigma, 0) / A(sigma_ref, 0), from the offline GFA seeing
          FWHM. The RCALIBFRAC-*level* replacement.
  L_field field-distortion (DAR) loss = mean over the focal plane of [1 - A(sigma, |G.r|) / A(sigma, 0)],
          from the ETC per-frame scale+shear DRIFT (G = scale+shear) and the same seeing.

`desimodel` (FastFiberAcceptance + platescale) is imported *lazily* inside the compute helpers, so
importing telemetry_mining never requires it; if it (or the offline data) is unavailable, the helpers
return None and the caller (Exposure.L_see / .L_field) falls back to a precomputed table source.

The drift fit (`sheardrift_from_thru`) is a faithful port of analysis/dar_dipole/shear_drift_test.py
(`fit_exposure_sheardrift`) -- same CS5 guide geometry, same per-frame 6-parameter affine fit, same
zenith-frame (2q) rotation. NERSC should validate it reproduces data/dar_shear_drift.parquet before it
is trusted (mean_ds is parallactic-independent and validates the fit; mean_de*_rot validates the
parallactic source).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import numpy as np

REF_SEEING_ASEC = 1.1        # desispec flat_to_psf reference seeing (matches gfa_seeing_level_metric.py)
R_MAX_MM = 410.0             # focal-plane field radius
FWHM_TO_SIGMA = 2.35         # rounded factor used throughout this investigation
_MIN_FRAMES = 20             # minimum ETC frames for an intra-exposure drift

GUIDE_NAMES = ["GUIDE0", "GUIDE2", "GUIDE3", "GUIDE5", "GUIDE7", "GUIDE8"]

# CS5 guide geometry: per camera, row 0 = position (mm), rows 1-2 = pixel->mm Jacobian.
# Constants copied verbatim from analysis/dar_dipole/shear_drift_test.py.
_CS5 = {
    "GUIDE0": np.array([[9.18450162e+01, -3.97013561e+02],
                        [1.42573799e-02, 4.66981235e-03],
                        [-4.65492774e-03, 1.41892856e-02]]),
    "GUIDE2": np.array([[4.05753952e+02, -3.52939152e+01],
                        [4.31199162e-05, 1.50010651e-02],
                        [-1.49338639e-02, 3.37050638e-05]]),
    "GUIDE3": np.array([[3.48896107e+02, 2.10237056e+02],
                        [-8.86064348e-03, 1.21055081e-02],
                        [-1.20477346e-02, -8.82590456e-03]]),
    "GUIDE5": np.array([[-9.18888483e+01, 3.96855686e+02],
                        [-1.42618407e-02, -4.65682022e-03],
                        [4.64286359e-03, -1.41935916e-02]]),
    "GUIDE7": np.array([[-4.05816895e+02, 3.54535663e+01],
                        [-1.00846756e-05, -1.50027231e-02],
                        [1.49362446e-02, -1.36688551e-06]]),
    "GUIDE8": np.array([[-3.49403148e+02, -2.09911349e+02],
                        [8.75839914e-03, -1.21795768e-02],
                        [1.21237342e-02, 8.72473620e-03]]),
}

_pos = np.array([_CS5[c][0] for c in GUIDE_NAMES])
_Jmats = np.array([_CS5[c][1:, :] for c in GUIDE_NAMES])
_Rguide = np.hypot(_pos[:, 0], _pos[:, 1]).mean()
_Xn, _Yn = _pos[:, 0] / _Rguide, _pos[:, 1] / _Rguide
_rows = []
for _xi, _yi in zip(_Xn, _Yn):
    _rows.append([1, 0, _xi, -_yi, _xi, _yi])   # dX = tx + s*x - theta*y + e1*x + e2*y
    _rows.append([0, 1, _yi, _xi, -_yi, _xi])   # dY = ty + s*y + theta*x - e1*y + e2*x
_A = np.array(_rows, dtype=float)
_Apinv = np.linalg.pinv(_A)


# ---- lazy desimodel-backed acceptance model (cached) ----

@lru_cache(maxsize=1)
def _fa():
    from desimodel.fastfiberacceptance import FastFiberAcceptance
    return FastFiberAcceptance()


@lru_cache(maxsize=1)
def _platescale_center_um_per_arcsec() -> float:
    from desimodel.io import load_platescale
    ps = load_platescale()
    return float(np.interp(0.0, ps["radius"] ** 2, np.sqrt(ps["radial_platescale"] * ps["az_platescale"])))


@lru_cache(maxsize=1)
def _a_ref() -> float:
    sigma_ref_um = REF_SEEING_ASEC / FWHM_TO_SIGMA * _platescale_center_um_per_arcsec()
    return float(_fa().value("POINT", np.array([sigma_ref_um]), np.array([0.0]))[0])


@lru_cache(maxsize=8)
def _field_grid(n: int):
    xs = np.linspace(-R_MAX_MM, R_MAX_MM, n)
    X, Y = np.meshgrid(xs, xs)
    inside = (X ** 2 + Y ** 2) <= R_MAX_MM ** 2
    return X[inside], Y[inside]


def _finite(*vals) -> bool:
    return all(v is not None and np.isfinite(v) for v in vals)


# ---- the two metrics ----

def l_see_from_fwhm(fwhm_asec) -> Optional[float]:
    """Seeing loss level from the offline GFA FWHM (arcsec). None if input bad or desimodel absent."""
    if fwhm_asec is None or not np.isfinite(fwhm_asec) or fwhm_asec <= 0:
        return None
    try:
        sigma_um = fwhm_asec / FWHM_TO_SIGMA * _platescale_center_um_per_arcsec()
        a0 = float(_fa().value("POINT", np.array([sigma_um]), np.array([0.0]))[0])
        return 1.0 - a0 / _a_ref()
    except (ImportError, FileNotFoundError, OSError):
        # desimodel not installed, or its data files unavailable (e.g. DESIMODEL unset / KPNO)
        return None


def sheardrift_from_thru(thru: dict, parallactic: float) -> Optional[dict]:
    """Per-exposure intra-exposure scale+shear DRIFT from the ETC 'thru' block.

    Faithful port of shear_drift_test.fit_exposure_sheardrift. `thru` is the ETC JSON 'thru' dict
    (e.g. Exposure.etc['thru']); `parallactic` is in degrees. Returns a dict with mean_ds,
    mean_de1_rot, mean_de2_rot (and nframe, duration_min), or None if the exposure lacks a usable
    multi-frame guide series.
    """
    if not thru or "dx_gfa" not in thru or parallactic is None or not np.isfinite(parallactic):
        return None
    dx = np.asarray(thru["dx_gfa"], dtype=float)
    dy = np.asarray(thru["dy_gfa"], dtype=float)
    if dx.ndim != 2 or dx.shape[1] != 6:
        return None
    nframe = dx.shape[0]
    if nframe < _MIN_FRAMES:
        return None
    dt1 = np.asarray(thru["dt1"], dtype=float)
    dt2 = np.asarray(thru["dt2"], dtype=float)
    tmid = 0.5 * (dt1 + dt2)

    dXmm = np.empty((nframe, 6))
    dYmm = np.empty((nframe, 6))
    for g in range(6):
        dmm = np.stack([dx[:, g], dy[:, g]], axis=1) @ _Jmats[g]
        dXmm[:, g] = dmm[:, 0]
        dYmm[:, g] = dmm[:, 1]
    b = np.empty((nframe, 12))
    b[:, 0::2] = dXmm / _Rguide
    b[:, 1::2] = dYmm / _Rguide
    params = b @ _Apinv.T
    s, e1, e2 = params[:, 2], params[:, 4], params[:, 5]

    tmin = tmid / 60.0
    if tmin[-1] - tmin[0] < 1.0:
        return None
    good = np.isfinite(s) & np.isfinite(e1) & np.isfinite(e2)
    if good.sum() < _MIN_FRAMES:
        return None
    s, e1, e2 = s[good], e1[good], e2[good]

    de1 = e1 - e1[0]
    de2 = e2 - e2[0]
    ds = s - s[0]                       # isotropic scale drift -- rotation-invariant, no 2q rotation
    q2 = 2 * np.deg2rad(parallactic)
    c2, s2 = np.cos(q2), np.sin(q2)
    de1_rot = de1 * c2 + de2 * s2       # spin-2 rotation into the zenith frame
    de2_rot = -de1 * s2 + de2 * c2
    return dict(
        mean_ds=float(ds.mean()),
        mean_de1_rot=float(de1_rot.mean()),
        mean_de2_rot=float(de2_rot.mean()),
        nframe=int(good.sum()),
        duration_min=float(tmin[-1] - tmin[0]),
    )


def l_field_from_drift(mean_ds, mean_de1_rot, mean_de2_rot, fwhm_asec, grid_n: int = 25) -> Optional[float]:
    """Field-averaged DAR distortion loss from the per-exposure drift + seeing.

    G = scale+shear = [[ds+e1, e2],[e2, ds-e1]]; loss(r) = 1 - A(sigma, |G.r|)/A(sigma, 0), averaged
    over the focal plane. The average of an offset magnitude is rotation-invariant, so the zenith-frame
    drift components may be used directly. None if any input is bad or desimodel is absent.
    """
    if not _finite(mean_ds, mean_de1_rot, mean_de2_rot, fwhm_asec) or fwhm_asec <= 0:
        return None
    try:
        sigma_um = fwhm_asec / FWHM_TO_SIGMA * _platescale_center_um_per_arcsec()
        a0 = float(_fa().value("POINT", np.array([sigma_um]), np.array([0.0]))[0])
        gx, gy = _field_grid(grid_n)
        ds, e1, e2 = mean_ds, mean_de1_rot, mean_de2_rot
        dxm = (ds + e1) * gx + e2 * gy
        dym = e2 * gx + (ds - e1) * gy
        delta_um = np.hypot(dxm, dym) * 1000.0          # mm -> um
        acc = _fa().value("POINT", np.full(delta_um.shape, sigma_um), delta_um)
        return float((1.0 - acc / a0).mean())
    except (ImportError, FileNotFoundError, OSError):
        # desimodel not installed, or its data files unavailable (e.g. DESIMODEL unset / KPNO)
        return None
