"""Standalone reimplementation of desimeter's field-rotation rate model.

Drop-in replacement for `desimeter.fieldmodel.dfieldrotdt` (and the
`dfieldrotdt_empirical_model` it forwards to, ignoring `mjd`) with **no
desimeter or astropy dependency** -- only `numpy`.

This exists to answer a real question: `dfieldrotdt` itself only does
arithmetic (no coordinate transforms, no time handling), but it lives in
`desimeter/fieldmodel.py`, whose *top-of-file* imports pull in
`astropy.table`, `astropy.time`, and three `desimeter.transform` submodules
-- none of which `dfieldrotdt` actually uses, but Python loads them anyway
the moment anything is imported from that file. Copying just the arithmetic
out, verified byte-for-byte identical to the real function (see
`compare_rot_rate_models.py` in this same directory), removes the need to
install/import `desimeter` at all for this one calculation.

These are the *original* (September 2022, credited to S. Kent) coefficients
-- unchanged from production. For the recalibrated version fit against
current guider data, see `recalibrated_rot_rate.py`.

Sign convention: returns the same value as `dfieldrotdt`/
`dfieldrotdt_empirical_model` directly (i.e. NOT yet negated) -- the online
code computes `rot_rate = -dfieldrotdt(...)` itself. This module
deliberately mirrors the original function's own convention, not the
already-negated `rot_rate`/`hexapod['rot_rate']` convention used elsewhere
in this project (e.g. `recalibrated_rot_rate.py`).
"""

import numpy as np


def dfieldrotdt(ra, dec, mjd, lst_deg):
    """Field-rotation rate derivative, arcsec/min. Drop-in for desimeter's function.

    Args:
        ra: RA, in degrees. Scalar or array-like.
        dec: Dec, in degrees. Scalar or array-like (same shape as `ra`).
        mjd: MJD, in days. Accepted but unused (matches the original
            function's own signature, which also ignores it).
        lst_deg: LST, in degrees (`ha = lst_deg - ra`). Scalar or array-like.

    Returns:
        Field rotation rate derivative, arcsec/min. Scalar if `ra` was
        scalar, else a numpy array of the same shape.
    """
    del mjd  # unused, kept for signature compatibility

    scalar = np.isscalar(ra)
    ra = np.atleast_1d(ra).astype(float)
    dec = np.atleast_1d(dec).astype(float)

    if np.any(np.abs(dec) > 90.0):
        raise ValueError(f"Unphysical Dec in degrees: {dec}")

    ha = (lst_deg - ra) % 360.0
    ha[ha > 180.0] -= 360.0

    x = ha / 60.0
    y = (dec - 30.0) / 30.0

    rate = (
        -0.447
        + 0.065 * x
        - 0.067 * y
        + 0.382 * x**2
        + 0.021 * x * y
        - 0.121 * y**2
        - 0.031 * x**3
        + 0.196 * x**2 * y
        + 0.096 * x * y**2
        - 0.043 * y**3
    )

    min_val, max_val = -1.5, 1.5
    rate[rate < min_val] = min_val
    rate[rate > max_val] = max_val

    return rate[0] if scalar else rate
