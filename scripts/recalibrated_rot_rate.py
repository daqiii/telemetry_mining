"""Recalibrated DESI field-rotation rate model.

Candidate replacement for `desimeter.fieldmodel.dfieldrotdt_empirical_model`
(the empirical polynomial fit last calibrated September 2022, credited to
S. Kent). Refit 2026-07-21 directly against ~9,320 guider-measured rotation
rates spanning 2023-01-18 to 2026-07-01, recovered as
`rot_rate_model + rotation_measured` -- since the guider-measured value is
the residual left over *after* `rot_rate_model` was already applied as the
correction, this recovers the true underlying rate as the fit target.

Same functional form as the original: a cubic polynomial in normalized hour
angle and declination. Held-out validation (random 70/30 split, never seen
during fitting), versus the original 2022 coefficients:

    mean bias:  -0.042 -> -0.001 arcsec/min
    RMS:         0.140 ->  0.126 arcsec/min

Region (2 NGC patches + 1 SGC, confirmed against the real DESI footprint)
and airmass were both tested as additional predictors. Both add
statistically significant structure (large sample size makes even small
effects detectable) but neither clears a practical bar in held-out RMS
terms (<1% further reduction each) -- both excluded here for simplicity.
See FIELD_ROTATION_REPORT.md (repo root) for the full analysis, including
the ruled-out alternatives (more frequent re-evaluation of the same
formula, a dynamic guider-informed correction) and the reasoning for why
this static recalibration was chosen as the recommended fix.

Sign convention: returns the same quantity as `hexapod['rot_rate']` in the
DESI exposure database -- i.e. already negated relative to desimeter's raw
`dfieldrotdt_empirical_model`, which returns the field-rotation derivative
itself before the sign flip `dfieldrotdt` applies (`rot_rate = -dfieldrotdt(...)`).
"""


def new_rot_rate(ha_deg: float, dec_deg: float) -> float:
    """Recalibrated field-rotation rate, in arcsec/min.

    Args:
        ha_deg: Mount hour angle, in degrees.
        dec_deg: Mount declination, in degrees.

    Returns:
        Predicted rotator rate in arcsec/min, same sign convention as
        `hexapod['rot_rate']`.
    """
    x = ha_deg / 60.0
    y = (dec_deg - 30.0) / 30.0
    return (
        0.44555
        + 0.03625 * x
        + 0.05556 * y
        - 0.43236 * x**2
        + 0.05576 * x * y
        + 0.07328 * y**2
        - 0.11390 * x**3
        - 0.12254 * x**2 * y
        - 0.15458 * x * y**2
        + 0.02106 * y**3
    )
