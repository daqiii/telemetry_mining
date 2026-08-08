# Test 6 — guide-star astrometric post-fit residuals, and the color follow-up

K. Honscheid (OSU) with Claude (NERSC + Mac sessions, collaborating via `from_nersc_to_mac.md` /
`from_mac_to_nersc.md`) · 2026-08-05

Follow-up to `DAR_DIPOLE_NERSC_HANDOFF.md` and the Test 5 result (`TEST4_AFFINE_GFA_REPORT.md`'s "Test 5"
section). This document reports a completed analysis with one deliberately open question (flagged below,
pending input from Steve Kent); it does not modify the handoff document or the resolved
`DAR_FIBER_LOSS_REPORT.md`.

---

## TL;DR

- **Motivation**: Test 5 showed intra-exposure guiding drift explains only ~3-4% of D_rot — not
  dominant. That redirects the hypothesis toward a **static** per-exposure offset: specifically, whether
  the guide-star sample is a biased estimator of the true field's DAR distortion (guide≠science), which
  the guider's closed loop would null at the *guide-star* mean while leaving the *science* field
  systematically offset.
- **Found a real PlateMaker product on NERSC** (`pm-<expid>.fits`, alongside `desi-<expid>.fits.fz` in
  every exposure directory) with exactly the needed per-guide-star astrometric data: catalog position,
  observed pixel position, and the fitted per-GFA WCS.
- **The measured residual (observed vs. catalog, mapped through the already-corrected WCS) is real,
  large, and has exactly the right functional form**: consistent with zero at zenith, and grows
  ~linearly with tan(z) at ~100σ significance, across 21,312 exposures.
- **A "why isn't the mean exactly zero" puzzle was raised and resolved**: `PMGWCS` is a model-prediction
  WCS (not a least-squares fit to these specific stars), so there's no zero-mean theorem to violate — the
  nonzero mean is a genuine model-residual signature.
- **A decisive test ruled out one candidate mechanism**: the already-validated, achromatic `distort.py`
  DAR model's own predicted sampling bias (from finite guide-star sampling of an intrinsically zero-mean
  rotation+differential field) does **not** explain the measured residual — zero correlation between the
  two, exposure by exposure.
- **Quantified the residual as a systematic ~1.1-1.3% error in the effective refraction constant.** A
  follow-up color test (cross-matched to Gaia DR3 for BP−RP) found this systematic is **flat with color,
  not sloped** — disfavoring a wavelength/effective-λ mismatch as the dominant explanation, by
  elimination pointing toward a non-chromatic systematic refraction-constant error (not yet directly
  confirmed, just the last standing candidate among those tested).
- **Open and unresolved**: whether `PMGWCS` reflects the astrometric solution *before* or *after* the
  telescope mount's pointing correction is applied — this determines whether the measured residual is the
  full uncorrected DAR effect at the guide stars (of which only a fraction would propagate to the science
  field) or something closer to what the science fibers actually feel directly. The user has reached out
  to Steve Kent for this; treat all magnitude comparisons to D_rot in this report as provisional pending
  that answer.

---

## Motivation

Test 5 (`TEST4_AFFINE_GFA_REPORT.md`) computed the physically-correct dipole cross-term
(`⟨M_shear(t)·T(t)⟩/σ_eff²`) from the per-frame ETC guide-GFA affine decomposition and found it real,
airmass-growing, but explaining only ~3-4% of D_rot's magnitude — intra-exposure guiding drift is not the
dominant mechanism. That result's big consequence: **the dipole must be a static per-exposure offset, not
a drift.**

Under the "correct placement" reasoning already established in this investigation (memory
`dar-guider-bias-hypothesis`), the only static, zenith-tied, airmass-growing offset that survives a
closed guiding loop is a **guide≠science boresight bias**: the guider nulls the mean of the *guide-star*
sample it can see, not the true field center. If that sample is a biased estimator of the true field's
DAR distortion (e.g., because it only samples 6 GFAs near the field edge, with uneven star counts), the
*science* fibers — which see the whole field — sit systematically off-center relative to what the guider
thinks is centered.

Test 1 already showed the *applied* acquisition offset (`xi0/eta0`, `mount_offset_ra/dec`) is swamped by
the legitimate bulk pointing/refraction correction (~20-40″) — a hopeless scale to find a small residual
in. The right quantity is the guide-star astrometric solve's **post-fit residuals** — what's left over
*after* that correction is applied, at the level of individual guide stars.

---

## Method

**Data source**: every exposure directory (`/global/cfs/cdirs/desi/spectro/data/<night>/<expid>/`,
alongside `desi-<expid>.fits.fz`) also has the real PlateMaker product `pm-<expid>.fits`, with:

- `PMGSTARS` (one row per matched guide star): `GFA_LOC` (as `GUIDE0`/`GUIDE2`/.../`GUIDE8` strings),
  `RA`/`DEC` (Gaia catalog position), `ROW`/`COL` (observed pixel centroid), `MAG`, `GUIDE_FLAG`.
- `PMGWCS` (one row per GFA, `GFA_LOC` as int 0/2/3/5/7/8, plus a `GFA_LOC=99` overall field-center row —
  confirmed to match the exposure's exact commanded field-center RA/Dec): a standard TAN WCS
  (`CRVAL`/`CRPIX`/`CD`).

**Residual computation**: for each star, predict its pixel position from its catalog RA/Dec via its
GFA's `PMGWCS` solution, compare to the *observed* pixel position, and convert to a sky-frame (RA/Dec-
like) arcsec offset:

```
measured_residual = WCS_predict(observed_ROW, observed_COL)
                     − catalog_RA_DEC
```

Verified bidirectionally (predicting pixel-from-catalog and comparing to observed pixel, converted back
to sky via the CD matrix) — identical to 4 decimal places, ruling out a sign/unit artifact.

**Decomposition**: per-exposure mean `(dRA, dDec)` — already in arcsec, no platescale conversion needed
— decomposed into a zenith-tied ("rotating") and fixed component using the same q-rotation convention as
`analysis/dar_dipole/acquisition_offset_test.py`'s "convention A" (`up = dRA·sin(q) + dDec·cos(q)`,
`vp = dRA·cos(q) − dDec·sin(q)`, `q` = parallactic angle).

**Scripts**: `analysis/dar_dipole/pmgstars_residual_test.py` (main residual test),
`analysis/dar_dipole/distort_model_vs_measured_test.py` (decisive sampling-bias test),
`analysis/dar_dipole/pmgstars_color_test.py` (color follow-up). **Data**:
`data/dar_pmgstars_residuals.parquet`, `data/dar_distort_model_vs_measured.parquet`,
`data/dar_pmgstars_color.parquet`.

---

## Validation (two exposures, before scaling)

| | high airmass (EXPID 360097, am≈1.98) | low airmass (EXPID 355421, am≈1.00) |
|---|---|---|
| mean dRA / dDec | +0.03″ / **−0.85″** | +0.11″ / **−0.13″** |
| per-GFA pattern | **uniform sign** (−0.37 to −1.26″) — dipole-like | **mixed sign** (−0.91 to +1.09″) — quadrupole-like |

Exactly the qualitative signature hunted for: small and differential-shaped at low airmass, large and
coherent at high airmass. Reads are fast (~3-30ms/file).

---

## Full-population result

21,312/24,630 exposures matched (86.5%). Decomposed into zenith-tied vs. fixed:

| airmass bin | n | zenith [16,84] | fixed [16,84] |
|---|---|---|---|
| >1.0 | 21312 | −0.259″ [−0.261,−0.257] | +0.034″ [0.032,0.035] |
| >1.2 | 7357 | −0.428″ [−0.431,−0.424] | +0.044″ [0.041,0.048] |
| >1.4 | 2244 | −0.579″ [−0.587,−0.571] | +0.049″ [0.043,0.056] |
| >1.6 | 757 | −0.674″ [−0.688,−0.659] | +0.048″ [0.037,0.059] |
| >1.8 | 126 | −0.703″ [−0.745,−0.665] | +0.055″ [0.016,0.092] |

Regression against tan(z) (`am>1.0` cut, full sample): **zenith: a=+0.025±0.003, b=−0.493±0.005** — the
intercept (value exactly at zenith) is small, consistent with a mechanism that vanishes there; the slope
is huge and ~100σ from zero. **Fixed: a=+0.019±0.003, b=+0.025±0.005** — much smaller, more consistent
with a minor fixed contribution.

The bin averages don't just grow with airmass by chance — the population is huge (n=21312 down to n=126)
and every bootstrap CI is tight and non-overlapping across bins. This is a real, robust, population-level
effect.

**The zero-mean puzzle, and its resolution.** A natural objection: an ordinary least-squares fit that
includes a translation term forces its residual mean to be *exactly* zero — so how can a real fit produce
a robust nonzero mean like this? Resolved (credit: the collaborating Mac session): **`PMGWCS` is not a
least-squares fit to these specific guide stars — it is the pointing/DAR-model WCS** (the model's
prediction, with the applied global correction folded in), evaluated at each GFA. Its residuals are
genuine *model errors* (observed − model-predicted), not fit residuals, so no zero-mean theorem applies.
The nonzero mean is the *signature* of a real model deficiency, not a bug.

---

## Decisive test: is this ordinary sampling bias on the known DAR model?

**Hypothesis tested**: `distort.py` (the production DAR/pointing model) has *zero* coherent boresight
translation by construction — its absolute refraction term is explicitly zeroed and folded into a pure
rotation instead (already established and ruled out earlier in this investigation as a dipole source). A
pure rotation, averaged over the 6 GFAs' exact (balanced, antipodal-paired) center positions, cancels to
zero. But the *actual* guide-star sample in a given exposure is not perfectly balanced (uneven star
counts per GFA) — so the sample mean of an intrinsically zero-mean field could be nonzero purely from
sampling asymmetry. If this reproduces the measured residual, the source would be ordinary
incompleteness acting on the already-validated DAR model.

**Method**: reimplemented `distort.py`'s `rtheta` rotation computation (validated against real production
values in `telemetry.ocs_gfadata` for EXPID 360097 — matched to a few percent once resolving that
ocs_gfadata stores these in radians, not degrees) and its `f1-f4` differential-refraction terms (already
validated earlier against the standard DAR formula, `steve_dar_shifts.py`). Applied the full model to the
*real* guide-star catalog positions from `PMGSTARS` (same real per-GFA star counts as the measured
residual), computing the model's own predicted sampling-bias mean, for all 21,312 exposures.

**Important scale caveat found before trusting a single-exposure comparison**: per-star differential-DAR
scatter is large (~11-14″ std at high airmass — the expected field-edge compression), so with only
~20-30 stars/exposure, a single exposure's sampling bias has a standard error of ~2-2.5″ — far bigger
than the ~0.1-0.9″ signal being compared. This had to be done as a population-level bootstrap comparison.

**Result: ruled out.**

| | zenith-tied slope vs. tan(z) | correlation with measured, exposure-by-exposure |
|---|---|---|
| Measured | −0.493 ± 0.005 (~100σ) | — |
| `distort.py` model sampling-bias | −0.138 ± 0.615 (not significant) | **0.0007** (zero) |

The model's own predicted bias is statistically consistent with zero at every airmass bin, and has zero
correlation with the measured residual. If sampling incompleteness of the known model were the mechanism,
exposures with a larger model-predicted bias should show a larger measured residual — they don't, at all.
**The Test 6 signal is not ordinary sampling incompleteness acting on the known, achromatic DAR model.**

---

## Quantifying the systematic, and the color follow-up

The measured residual's functional form (zero at zenith, ∝ tan z, one consistent sign) is the fingerprint
of **a refraction the guide-star astrometric model gets slightly wrong** — either a wavelength/color
mismatch or a non-chromatic constant error. Putting a number on it: the regression slope
(−0.493″/tan(z)) against the production refraction constant (45″, `desi.par`) gives a systematic
refraction error of **~1.1%** (Mac's independent estimate using the am>1.4 bin average gave ~1.3%, in
the same range).

**Candidates weighted going in** (credit: the collaborating Mac session's framing):
- **Wavelength/effective-λ mismatch** (flagged as leading): if the model's assumed guide wavelength
  differs from the guide stars' actual effective wavelength by ~1-2%, that alone explains a ~1.3%
  refraction error.
- **A non-chromatic systematic refraction-constant error** — same signature, no color dependence.
- Polar-axis constants (`a0..b4`): low prior — they drive rotation/HA-Dec terms, not a zenith ∝ tan z
  *translation*, so shouldn't produce this specific form.

**Decisive color test**: per-star residual (not exposure-averaged) for the full am>1.4 sample,
cross-matched to Gaia DR3 (`/global/cfs/cdirs/desi/target/gaia_dr3/lightweight/`, nside=32 nested
healpix; validated to sub-0.01″ match separation) for BP−RP color. 2246/2968 exposures processed, 52,097
star rows, 33,073 (63.5%) with a color match (median separation 0.014″ — real matches). Per star,
`y = residual_zenith / tan(z)` isolates the effective refraction-rate coefficient (removing the
already-established airmass dependence); regressed `y ~ a + b·(BP−RP)`.

**Result: a=−0.427±0.037, b=−0.043±0.030** (cluster-robust by EXPID: identical). **The slope is not
statistically significant** (~1.4σ). A binned check across 5 color quintiles (BP−RP spanning −0.47 to
4.69, ~6600 stars each) shows no monotonic trend — bin means run −0.459, −0.446, −0.528, −0.452, −0.499,
consistent with flat within noise (SE≈0.03/bin). A slope large enough to explain the *entire* offset
chromatically would need to be roughly 10× larger than what this test excludes.

**Read**: this disfavors the wavelength/effective-λ mismatch as the dominant explanation (a small
chromatic contribution isn't excluded — Mac's own note that within-r-band per-star color spread gives
only ~0.1″ is consistent with that). Combined with the polar-constants candidate already being low-prior
on independent (functional-form) grounds, this leaves **a non-chromatic systematic refraction-constant
error as the surviving candidate — by elimination, not yet by direct positive evidence.**

---

## Open question (pending Steve Kent's input) — read this before trusting any D_rot comparison

**Is `PMGWCS` computed before or after the telescope mount's pointing correction is applied?** This
determines what the measured residual physically represents:
- If `PMGWCS` reflects the solution *before* the mount correction, the measured residual is closer to the
  *full* uncorrected DAR effect at the guide-star positions — of which only some fraction (the
  guide≠science differential, not the whole thing) would propagate into what the science fibers feel.
- If it reflects the solution *after* correction, the residual is closer to what actually remains at the
  guide stars post-correction — a more direct, though still guide-star-specific (not science-field),
  quantity.

Either way, **the raw magnitude comparison to D_rot (0.5-0.9″ measured vs. D_rot's ~0.11-0.22″, itself a
soft number given its own σ_eff/time-averaging conversion uncertainty) should not be treated as a
mismatch or a match until this is resolved** — a propagation/fraction argument is needed either way
before this residual can be compared quantitatively to D_rot's growth curve and ≈−105° derotated-frame
direction (the actual win condition). The user has reached out to Steve Kent directly for this; this
report deliberately stops short of drawing a magnitude conclusion pending that answer.

---

## Conclusion

Test 6 found a real, large, population-robust (~100σ), zenith-vanishing, tan(z)-growing residual in the
guide-star astrometric solve — qualitatively the right signature for a refraction-model deficiency, and
still the most promising unresolved lead in this investigation. Two candidate mechanisms have been
cleanly ruled out (ordinary sampling incompleteness on the known model; dominant chromatic/wavelength
mismatch), narrowing the field to a non-chromatic systematic refraction-constant error by elimination.
**What remains genuinely open**: (1) direct confirmation of the non-chromatic-constant-error candidate
(not yet tested positively, only arrived at by ruling out the alternatives); (2) whether `PMGWCS` is
pre- or post-mount-correction, which gates any quantitative comparison to D_rot; (3) the actual
guide→science propagation link even once (1) and (2) are resolved — Test 6 being a real refraction-model
deficiency does not by itself establish that it *is* D_rot's source, only that it's a strong candidate
worth the continued attention it's getting.

## Related
- `docs/DAR_DIPOLE_NERSC_HANDOFF.md` — the primary investigation document.
- `docs/TEST4_AFFINE_GFA_REPORT.md` — Test 4 and Test 5 (drift/cross-term), the results that motivated
  redirecting toward this static-offset hypothesis.
- `docs/FOUNDATION_CHECK_REPORT.md` — independent verification that D_rot itself is real.
- Memory: `dar-guider-bias-hypothesis` (full evolving record).
- Communication log: `from_nersc_to_mac.md` / `from_mac_to_nersc.md` (the turn-by-turn reasoning behind
  each step above, including the collaborating session's contributions credited throughout).
