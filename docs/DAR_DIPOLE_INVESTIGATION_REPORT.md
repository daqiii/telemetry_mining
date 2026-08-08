# The DAR Fiber-Loss Dipole: From a Positioning Hypothesis to a Sky-Subtraction Localization

K. Honscheid (OSU) with Claude (NERSC + Mac sessions, collaborating via `from_nersc_to_mac.md` /
`from_mac_to_nersc.md`) · 2026-08-06

> **⛔ SUPERSEDED (2026-08-06) — this investigation has been merged into `DAR_FIBER_LOSS_REPORT.md`**, which is
> now the single standalone document (data-based DAR study: the quadrupole is real DAR → meridian scheduling;
> the dipole is a sky-subtraction artifact → handed to `desispec`). This file is retained for its detailed
> narrative and its circulation history; cite `DAR_FIBER_LOSS_REPORT.md` going forward.

This report tells the full story of a follow-up investigation to Finding 2 of `DAR_FIBER_LOSS_REPORT.md`
(the standard-star flux loss that grows with airmass). It supersedes `DAR_DIPOLE_NERSC_HANDOFF.md` as the
narrative record of that investigation and reaches a conclusion the original report did not have: **the
loss dipole is not caused by targets physically drifting off their fibers. It is a flux-processing
effect, localized to the sky-subtraction step of the spectroscopic pipeline.** This document does not
edit `DAR_FIBER_LOSS_REPORT.md` directly — that is a recommended follow-up, discussed at the end.

---

## Motivation: an independent, data-based probe of DAR fiber loss

Differential atmospheric refraction (DAR) at high airmass moves star images relative to their once-placed
fibers and is expected to cause flux loss — an effect that matters for the more-southern, higher-airmass
fields much of the upcoming DESI program will use. The effect had been characterized before, but from
**models and telemetry rather than survey flux data**: **Weiner (DESI-9817)** from an astrometric/geometric
simulation of the displacement field, and **Kirkby (DESI-8586)** from the guider's own guide-star-motion
telemetry at high airmass. The atmospheric-dispersion-corrector (ADC) behavior had likewise been analyzed
from first principles (**Lampton, DESI-0309**; **Joyce, DESI-9097**). What was missing was an **independent,
on-sky, flux-based** measurement — a way to see the effect directly in the survey's own standard-star
throughput and compare it against those studies.

This study set out to provide exactly that. We identified **`RCALIBFRAC`** — the per-exposure standard-star
r-band measured-over-model flux ratio produced by the pipeline — as a readily available, data-based flux-loss
metric, and decomposed its airmass- and parallactic-angle dependence into the multipole pattern DAR predicts
(a derotated, zenith-aligned fit; see §1). The result had two parts:

- a **quadrupole** (`Q_rot`, field-differential DAR compression) that we could check against the other work —
  and it **agrees well**: converted to an edge-of-field offset it matches Kirkby and Weiner to 10–20%, and a
  second, independent astrometric measurement (guide-star residuals) reproduces it (§2, §4);
- and a **rotating dipole** (`D_rot`, roughly twice the quadrupole) that **none of the other studies shows** —
  Weiner and Kirkby both predict or measure only a quadrupole and set the dipole to zero.

![Per-exposure-demeaned standard-star loss in the derotated, zenith-aligned focal plane (airmass > 1.4). Loss is systematically lower toward the zenith and higher away from it — a coherent, zenith-tied **dipole** — on top of the expected quadrupole. This is the pattern that motivated the investigation.](../notebooks/figures/dipole_rpt_pattern.png)

![The quadrupole, converted to an edge-of-field DAR offset (`ΔG = σ_eff·√(2·Q_rot)`), agrees with the independent Kirkby (DESI-8586) and Weiner (DESI-9817) estimates to 10–20%. The dipole, at roughly twice this amplitude, has no counterpart in either study.](../notebooks/figures/dipole_rpt_quadrupole_vs_studies.png)

That unexplained dipole — real, reproducible, zenith-tied, airmass-growing, and absent from every independent
treatment — became the subject of the investigation that follows. As the executive summary states and the
rest of the report establishes, its resolution turned out to be about the **metric**, not the atmosphere.

---

## Executive summary

`DAR_FIBER_LOSS_REPORT.md` found that standard-star flux loss grows with airmass in a pattern with two
components: a **quadrupole** (field-differential compression) and a **dipole** (a coherent, uniform,
zenith-tied offset of the whole loss pattern). The report interpreted both as **differential atmospheric
refraction (DAR) acting on fixed, once-placed fibers** — targets drift under DAR during the ~20-minute
exposure while the fiber stays put, so the star image walks off the fiber aperture.

This investigation set out to test that mechanism directly, and specifically to explain the dipole (`D_rot`),
which is roughly twice the amplitude of the quadrupole (`Q_rot`) and does not have an obvious counterpart in
any independently known telescope/atmosphere model. Two years of DESI operations and roughly a dozen
independent tests later, the picture has inverted:

- **The quadrupole (`Q_rot`) is fully explained and independently cross-validated.** It matches published
  DAR-drift estimates (Weiner, Kirkby) to 10–20%, and a second, independent astrometric measurement (guide-star
  residuals from the real PlateMaker product) reproduces it almost exactly. This part of Finding 2 stands.
- **The dipole (`D_rot`) is not caused by any geometric fiber-to-light offset.** A direct, independent
  measurement of the actual dither offset field — the real geometric fiber-vs-light residual, measured by
  DESI's own dither-sequence technique — shows **no rotating, zenith-tied, airmass-growing offset** at the
  location and scale `D_rot` requires, while the *same* dataset's quadrupole **does** reproduce `Q_rot`. So
  whatever produces `D_rot`, it does not move the fiber relative to the light.
- **The dipole is instead produced inside the flux-loss measurement itself**, and has now been localized to
  a specific pipeline step: reconstructing `RCALIBFRAC` (the quantity `D_rot` is measured in) from its raw
  ingredients and decomposing it stage-by-stage through the flux-reduction chain shows the rotating dipole
  appears — and roughly doubles in amplitude — specifically at **sky subtraction**. It is absent (or much
  smaller) before that step and unchanged after it. Two candidate explanations that looked plausible (a
  known aperture-correction term, and the stellar flux-calibration model itself) were tested directly and
  ruled out along the way.
- **Within sky subtraction, the mechanism has been narrowed to the flux values themselves, not any tested
  weighting or correction scheme.** Six further discriminating tests (§8) establish that the effect requires
  the star's own signal (null at pure sky fibers), scales with both star brightness and sky brightness in a
  way that rules out a simple additive sky residual, and survives unchanged when every concrete weighting-related
  candidate inside `subtract_sky` is tested directly and removed — including a bisector test that rules out
  ivar-weighting as a mechanism *class*, not just one named function. The exact algorithmic step is not
  identified; the investigation's recommendation is to hand this off to the `desispec` sky-subtraction authors
  with the localization above as a concrete starting point, rather than continue reverse-engineering the
  pipeline from outside.

This means Finding 2's framing needs a correction: the loss dipole is real, airmass-growing, and DAR-shaped
in its zenith-tied symmetry, but it is a **flux-processing effect that enters at the sky-subtraction step of
how the loss is measured** — not evidence that starlight is falling outside the fiber aperture. (Whether it is
a sky-*model* error or a real sky/extinction flux effect the star inherits at that step is the open mechanism
question of §8; the "not fiber mis-centering" conclusion holds either way.) The scheduling implications of Finding 2
that depend on the quadrupole (proximity-to-transit as the dominant lever, §10 of the original report) are
unaffected; the specific claim that fibers "lose their targets" under DAR drift is not supported by direct
measurement and should be revised.

**The practical takeaway.** We set out to measure DAR fiber loss directly from survey data using `RCALIBFRAC`,
to compare against the model/telemetry studies. The comparison succeeded for the physical part — the
**quadrupole** matches Kirkby and Weiner. But the headline is a caution about the metric: **`RCALIBFRAC` is not
a clean flux-loss estimator for this purpose.** Its sky-subtraction step imprints a spurious, zenith-tied
**dipole** on top of the genuine DAR signal — an effect that is real in the number but is a property of the
*measurement*, not of starlight leaving the fiber. We narrowed its origin considerably (to star-fiber
processing during `subtract_sky`; §8) but did not pin the exact algorithmic step. **What this coupling means
for DESI's flux calibration more broadly is beyond the scope of this study; we hand it to the `desispec`
maintainer, Julien Guy — see §9.**

---

## 1. Background: what Finding 2 claimed, and what was left open

`DAR_FIBER_LOSS_REPORT.md` (Part II) established that standard-star loss grows with airmass, forms a
dipole+quadrupole pattern in the derotated (parallactic-angle-aligned) focal-plane frame, and interpreted
this via the standard fiber-acceptance model:

```
loss ≈ |δ₀ + G·r|² / 2σ²
```

where `δ₀` is a uniform (whole-field) fiber-to-light offset, `G` is the field-differential DAR gradient, and
`σ` is the fiber's effective acceptance scale. In this model the **quadrupole** is the `|G·r|²` term (DAR
compressing/expanding the field) and the **dipole** is the cross-term `δ₀·G` — it exists only if there is a
genuine coherent offset `δ₀` between the fiber array and the star field.

The measurement (`analysis/dar_dipole/fit_dipole_quadrupole.py`, per-star loss regressed against a
6-term radial + fixed-dipole + rotating-dipole + fixed-quadrupole + rotating-quadrupole model, derotated by
each exposure's parallactic angle) is solid and was independently reproduced from a fresh database pull (the
"foundation check," §2 below). What was open was the *mechanism*: **is `δ₀` a real, physical fiber-to-light
offset, and if so, what produces it?**

**Measured amplitudes** (complete population, edge-normalized units, bootstrap CIs over exposures):

| airmass cut | D_rot | Q_rot | D_rot / Q_rot |
|---|---|---|---|
| > 1.4 | 0.035 | 0.017 | 2.03 [1.94, 2.12] |
| > 1.6 | 0.056 | 0.029 | 1.93 [1.82, 2.10] |
| > 1.8 | 0.080 | 0.046 | 1.75 [1.55, 2.04] |

![The measured rotating dipole (`D_rot`) and quadrupole (`Q_rot`) vs. airmass. Both grow with airmass, and the dipole is consistently ~2× the quadrupole — the feature with no counterpart in the model/telemetry studies.](../notebooks/figures/dipole_rpt_amplitudes.png)

Converted to a physical fiber-acceptance offset (`σ_eff ≈ 52 μm` from the real `desimodel`
`FastFiberAcceptance` model), the implied dipole offset is **δ₀ ≈ 8–12 μm (central ~10 μm ≈ 0.14″)** — a
small but coherent shift of the whole star field relative to the fiber array, growing with airmass, aligned
with the zenith direction. A **q-permutation null test** (shuffling parallactic angle across exposures)
collapses this signal (0.044 → 0.002), confirming it is genuinely locked to the parallactic angle and not a
statistical artifact.

---

## 2. Establishing the effect is real

Two checks were run before investing in mechanism-hunting:

**Foundation check** (`docs/FOUNDATION_CHECK_REPORT.md`): the entire dipole result rested on a dataset built
in an earlier session and never independently regenerated. A fresh pull directly from the database (not
reusing any committed intermediate file), fit with the unmodified analysis code, reproduced the result to
2–3 significant figures:

| airmass cut | D_rot (fresh pull) | D_rot (original) |
|---|---|---|
| > 1.4 | 0.0353 | 0.035 |
| > 1.6 | 0.0560 | 0.056 |
| > 1.8 | 0.0810 | 0.080 |

Also confirmed the focal-plane `X`/`Y` coordinates are a static, instrument-fixed frame with no per-exposure
rotation baked in (ruling out a trivial coordinate-frame artifact).

**Quadrupole cross-check against independent published estimates**: converting `Q_rot` to a physical
edge-of-field DAR-compression offset (`ΔG = σ_eff·√(2·Q_rot)`) gives 8.0/11.6/15.5 μm (0.11″/0.16″/0.22″) at
airmass 1.48/1.69/1.86 — matching Kirkby's guider sky-motion estimate (~15 μm at airmass 2, DESI-8586) and
Weiner's astrometric-geometry estimate (~18 μm at airmass 2, DESI-9817) to 10–20%. **Three independent
methods converge on the quadrupole's physical scale.** The dipole, at roughly twice this amplitude, has no
such independent confirmation at this stage — which is exactly what motivated the rest of this investigation.

---

## 3. Ruling out known instrument/pointing models (by magnitude)

Several concrete, well-understood instrumental effects were tested directly against real DESI models and
data and ruled out — each has the right *qualitative* form to be tempting, but fails on *magnitude*:

| candidate | test | result |
|---|---|---|
| PlateMaker's DAR refraction model (`distort.py`) | Steve Kent's actual production code, real refraction constant | Purely *differential* (zero at field center) → governs the quadrupole, not the dipole, by construction |
| GFA gravity/deformation (`gfadeform.dat`) | Real PlateMaker geometry, net boresight averaged over the balanced 6-GFA guide ring | ~0.02″ (~1.5 μm) — 5–7× too small |
| `reqtime`/`exptime` midpoint mismatch | Direct regression against the (real, ubiquitous) reqtime−exptime gap at controlled airmass | D_rot does not scale with the gap |
| Applied acquisition/pointing offset (Test 1) | Zenith-projected component of the real applied boresight correction vs. airmass | Grows with airmass but at 100–300× `D_rot`'s scale — dominated by the legitimate bulk pointing correction, inconclusive by construction |
| Intra-exposure guiding-residual drift (Tests 4/5) | Per-frame affine decomposition of real ETC per-GFA guide offsets, correct cross-term (`⟨M_shear(t)·T(t)⟩`, not the naive rate×duration) | Real, statistically significant, grows with airmass — but only ~3–4% of `D_rot`'s magnitude |
| 2nd-order refraction (March 2026 PlateMaker deployment) | Pre/post split at the deployment date | D_rot unchanged (0.0227→0.0249 at am>1.2; 0.0354→0.0408 at am>1.4) |

None of these explains `D_rot`'s scale. Full detail for each is in `DAR_DIPOLE_NERSC_HANDOFF.md` and memory
`dar-guider-bias-hypothesis`.

---

## 4. The guide-star reframing, and a chromatic hypothesis (real, but sub-dominant)

A second astrometric measurement was found: **`pm-<expid>.fits`**, the real per-exposure PlateMaker product,
carries the guide stars' catalog positions (`PMGSTARS`) alongside the fitted guide WCS (`PMGWCS`). The
post-fit residual (observed − model) is real, ~100σ significant, vanishes at zenith, and grows ∝ tan(z) — the
right functional form, but a magnitude several times larger than `D_rot` (raising the question of what
reference frame it's measured against).

Reading the actual DESI guider code resolved this: the guide loop only ever nulls the **mean** guide-star
offset (a pure boresight correction). Any refraction error **common** to the guide stars and the science
fibers is therefore corrected away by the loop; only a genuine **guide-vs-science differential** would reach
the science fibers as a dipole. Consistent with this, the guide-star residual's **rotating quadrupole**
(its field-differential structure, which the boresight loop cannot remove) independently matches `Q_rot`:
0.102″/0.168″ measured vs. 0.11″/0.16″ established — **guide stars and science fibers demonstrably see the
same DAR field.** This explained why the guide-star residual's full magnitude is larger than `D_rot`: most of
it is common-mode and gets corrected; only the differential piece can survive to the dipole.

The natural next hypothesis was a **guide-vs-science wavelength differential**: standard stars are bluer than
guide stars, and the guide loop nulls the loop at the guide stars' (redder) effective wavelength, potentially
leaving a residual differential chromatic refraction (DCR) at the (bluer) science targets. This was tested
quantitatively:

- **Step A (premise check):** the color offset is real and large (Δ(BP−RP) = −0.415, >100σ).
- **Step B (magnitude):** the predicted DCR from that color offset is ~0.02″ — smaller than `D_rot`
  (0.11–0.22″ in the same units).
- **Step C (decisive internal test):** re-fitting `D_rot` separately on blue vs. red halves of the standard-star
  sample shows **no detectable color dependence** — flat, not the chromatic prediction.

Independently, reading Steve Kent's PlateMaker/Dervish source confirmed **why**: the refraction constant is a
single value, calibrated at r-band, applied identically to science placement and the GFA guide solve, and
placement uses no per-target color at all (a fixed radial polynomial, not a function of a star's own SED).
There is no guide-vs-science wavelength mismatch in PlateMaker to exploit. **Conclusion: chromatic DCR is a
real, measurable, sub-dominant contributor (~0.02″), not `D_rot`'s dominant source.**

At this point the geometric/astrometric/chromatic candidate space was exhausted without finding `D_rot`'s
source. The investigation turned to the most direct test available: **measure the actual fiber-to-light
offset independently, and see if a dipole is there at all.**

---

## 5. The decisive test: does the real geometric offset field have a dipole?

DESI runs regular **dither sequences** — deliberately stepping standard stars across their fibers in a known
pattern and fitting the resulting flux vs. position to recover, per star and per exposure, the actual
fitted fiber-to-light offset. This is a completely different measurement technique from `RCALIBFRAC` (a
geometric centroid fit, not a flux-ratio construction) and therefore an independent witness to whether `δ₀`
is physically real.

**A bug, found and fixed.** The first attempt at this test used the wrong quantity — a column that looked
like the fitted position residual (`fiber_ditherfit_ra − target_ra`) but, per the actual dither-fitting source
(`solvedither.py`, `github.com/desihub/desicmx`), is *defined* to include the deliberately-commanded dither
offset itself (`delta_x_arcsec`), not just the fitted residual. Fitting a dipole/quadrupole model to that
quantity measures the known, by-design dither pattern, not anything physical — which produced a spurious null
result that (correctly) did not match the independently-established quadrupole, flagging the bug. The fix
uses the file's own `xfiboff` (static per-fiber offset) + `xtel` (per-exposure boresight) columns directly —
already separate, clean, arcsec-valued quantities requiring no reconstruction.

**Result, corrected** (156 exposures, 12 nights, airmass 1.0–2.2; CIs are night-clustered, since airmass
barely varies within a single ~13-exposure dither sequence — only 12 independent airmass points, not 156):

| airmass cut | rotating (zenith-tied) dipole | rotating quadrupole |
|---|---|---|
| > 1.0 | −0.046″ [−0.058, −0.034] | 0.071″ [0.060, 0.082] |
| > 1.2 | −0.037″ [−0.049, −0.025] | 0.084″ [0.075, 0.093] |
| > 1.4 | −0.038″ [−0.051, −0.025] | 0.088″ [0.080, 0.097] |
| > 1.8 | −0.043″ [−0.057, −0.030] | 0.095″ [0.089, 0.101] |

Target for comparison: `D_rot` and `Q_rot` both imply ~0.11″ → 0.22″, growing with airmass, over this range.

**The dipole is flat, wrong-sign-of-growth, and ~5× too small** — a linear fit vs. tan(z) gives a slope whose
68% CI ([−0.010, +0.036]) straddles zero. **The quadrupole, measured from the exact same stars and
exposures, grows with airmass and lands at the right order of magnitude, tracking `Q_rot`.** Because both
quantities come from the same dataset with the same coverage, a "thin sample" or "diluted signal" explanation
that would flatten the dipole would flatten the quadrupole's growth too — it doesn't. This is a real positive
control: **the measurement is sensitive enough to see the quadrupole cleanly, and it sees no dipole.**

![The real, independently-measured fiber-to-light offset field from DESI's dither-sequence technique shows no rotating dipole (gray, flat at ~0.04″, well below the 0.11–0.22″ target band) while its rotating quadrupole (blue) grows with airmass and tracks toward the same target band that Q_rot independently establishes. Same stars, same exposures, same measurement — the quadrupole is resolved cleanly, and there is no dipole to resolve. Night-clustered bootstrap CIs (12 independent nights).](../notebooks/figures/dipole_rpt_dither_null.png)

**Conclusion: `D_rot` is not a physical, geometric fiber-to-light offset.** Whatever produces the dipole,
starlight is not centroiding off the fiber aperture by 0.14″–0.22″ in a coherent, zenith-tied way. This
directly contradicts Finding 2's original framing ("targets drift off their fixed fiber").

---

## 6. Pivoting to the measurement itself

If the dipole isn't in the geometry, it must be in how the loss (`RCALIBFRAC`) is *measured* or
*constructed*. `RCALIBFRAC` is built by `desispec`'s `select_calib_stars.py`:

```
ratio = (measured r-band flux, aperture-corrected) / (model r-band flux, from the stellar fit)
RCALIBFRAC = ratio / median(ratio)   [per exposure]
```

Two candidate mechanisms were identified and tested directly, both against the real production pipeline
code (not a re-derivation):

**Candidate 1 — the point-source aperture correction.** A step in `RCALIBFRAC`'s construction divides the
measured flux by a fiber-acceptance correction computed from each fiber's positioning offset
(`DELTA_X`/`DELTA_Y`) at a fixed assumed seeing. Since fiber acceptance falls off quadratically with offset,
this correction has algebraically the same dipole+quadrupole structure the fit is sensitive to — a plausible
way to *manufacture* a dipole from a positioning field that isn't really there. Tested two independent ways:

- **Deployment-date test:** this correction was only added to `RCALIBFRAC` in mid-2025 (desispec PR #2484).
  If it produced the dipole, `D_rot` should step at that date, the way the (unrelated) Finding-1 loss-level
  shift does. It doesn't — `D_rot` is at full strength before the correction existed (epoch A, pre-2025:
  0.0341 at am>1.4) and essentially unchanged after (epoch B/C: 0.0377/0.0408).
- **Direct fit:** fitting the same dipole/quadrupole decomposition directly to the correction factor itself
  (full population, 24,630 exposures) gives a rotating dipole of 0.0003–0.0008″ — 50–100× too small to be
  `D_rot`.

Two independent methods agree: **this correction is not the source.**

**Candidate 2 — the stellar flux-calibration model.** `select_calib_stars.py`'s construction was
reimplemented directly (the actual `desispec` functions: `read_stdstar_models`, `read_frame`,
`apply_fiberflat`, `subtract_sky`, `flat_to_psf_flux_correction`) so the model term (`MODELRFLUX`, the fitted
stellar template) and the data term (`RFLUX`, the measured flux) could be kept separately instead of only the
final ratio. Reproduction was validated against the on-disk production output (median residual ~0.002 in
`RCALIBFRAC` units for reductions built with the same pipeline version; a subset built with an older,
un-reprocessed pipeline version was excluded to keep the comparison apples-to-apples — 437 of 1177 sampled
exposures, spanning airmass 1.0–2.2, mostly 2025–2026).

Fitting the dipole decomposition separately to `−log(MODELRFLUX)` and `log(RFLUX)` (each demeaned per
exposure):

| airmass cut | rebuilt-loss D_rot | **model-term D_rot** | **data-term D_rot** |
|---|---|---|---|
| > 1.2 | 0.047 | 0.019 | 0.041 |
| > 1.4 | 0.063 | 0.013 | 0.060 |
| > 1.6 | 0.079 | 0.016 | 0.078 |
| > 1.8 | 0.095 | 0.019 | 0.094 |

**The data term carries essentially all of it; the model term stays small and flat.** The stellar
flux-calibration model is not the source. The dipole is in the measured r-band flux itself.

---

## 7. Localizing the mechanism: sky subtraction

With the model ruled out and the correction ruled out twice, the same reimplementation was extended to
snapshot the measured flux at each stage of its construction, in order:

```
raw extracted flux  →  + fiberflat  →  + sky subtraction  →  + aperture correction
```

(Flux, inverse-variance, and mask are re-evaluated at each stage, since `apply_fiberflat` and `subtract_sky`
both modify them in place — reusing a later stage's mask against an earlier stage's flux would be
inconsistent.) Fitting the dipole/quadrupole decomposition to each stage's flux, on the same
code-version-consistent 437-exposure subset (`D_rot`/`D_fix` in edge-normalized fit units, as in §1 and §6 —
note §5's dither figures are in arcsec, a different quantity):

| airmass cut | stage | D_rot | D_fix |
|---|---|---|---|
| > 1.4 | raw | 0.031 [0.025, 0.042] | 0.064 [0.055, 0.073] |
| > 1.4 | + fiberflat | 0.025 [0.018, 0.036] | 0.037 [0.030, 0.048] |
| > 1.4 | **+ sky subtraction** | **0.059 [0.046, 0.074]** | 0.052 [0.042, 0.066] |
| > 1.4 | + aperture correction | 0.060 [0.046, 0.074] | 0.051 [0.042, 0.066] |
| > 1.8 | raw | 0.042 [0.029, 0.061] | 0.070 [0.054, 0.087] |
| > 1.8 | + fiberflat | 0.037 [0.023, 0.056] | 0.046 [0.034, 0.065] |
| > 1.8 | **+ sky subtraction** | **0.094 [0.065, 0.125]** | 0.068 [0.053, 0.100] |
| > 1.8 | + aperture correction | 0.094 [0.065, 0.125] | 0.068 [0.053, 0.099] |

![D_rot fit to the standard-star flux at each stage of its construction (raw extraction → +fiberflat → +sky subtraction → +aperture correction), at four airmass cuts. The rotating dipole is small and airmass-flat through fiberflat, then jumps by roughly 2× specifically at sky subtraction, developing its characteristic airmass growth there — and is unchanged by the aperture correction afterward. Bootstrap CIs over exposures.](../notebooks/figures/dipole_rpt_stage_decomposition.png)

Reading it stage by stage:

- **Fiberflat application** does what it should: the *fixed* (instrument-frame) dipole drops sharply
  (0.064 → 0.037 at am>1.4), consistent with correcting a static, focal-plane-fixed pattern. The rotating
  dipole barely moves.
- **Sky subtraction roughly doubles the rotating dipole at every airmass cut** (0.025 → 0.059 at am>1.4;
  0.037 → 0.094 at am>1.8), and this is exactly where its characteristic airmass growth becomes pronounced.
  This is the step.
- **The aperture correction changes nothing**, to three decimal places — a third independent confirmation
  (alongside §6's two tests) that it is not the source.

A secondary, smaller rotating dipole is already present in the raw extracted flux (0.031 → 0.042), well
below the final amplitude and not the dominant effect — sky subtraction is not merely refining a signal that
was already there, it is where most of the amplitude appears.

One more thing worth noting: the post-sky-subtraction amplitude (0.059–0.094 across am 1.4–1.8, in this
2025–2026 subset) is now **at or above** `D_rot`'s established full-population value (0.035–0.080) — so
whatever mechanism inside sky subtraction is responsible, it is not too small in magnitude to matter, which
had been a real concern going in (a rough differential-extinction estimate had suggested an order-of-magnitude
shortfall).

---

## 8. Narrowing the mechanism inside sky subtraction, and the handoff

**What is established going into this section:**
1. The quadrupole (`Q_rot`) is real, physically understood DAR compression, cross-validated three independent
   ways (loss-based fit, Weiner's geometry, Kirkby's guider sky-motion) and reproduced by a second astrometric
   dataset (guide-star residuals). This part of Finding 2 stands as published.
2. The dipole (`D_rot`) is real, reproducible, and not a statistical or coordinate-frame artifact (foundation
   check, q-permutation null).
3. The dipole is **not** a physical, geometric fiber-to-light offset — a direct, independent measurement of
   the real dither offset field shows none, at a precision that clearly resolves the quadrupole from the same
   data.
4. The dipole **is** produced inside the flux-loss measurement pipeline, specifically at **sky subtraction** —
   localized by process-of-elimination against the aperture correction (ruled out twice) and the stellar
   model (ruled out once), then positively identified by a stage-by-stage reconstruction of the actual
   pipeline.

Six further tests, run in sequence, narrow *which part* of sky subtraction is responsible.

### 8.1 Discriminators: what kind of mechanism is it?

**Bright-vs-faint split (using `MODELRFLUX`, the pre-fit stellar template, for brightness bins — independent
of the effect under test).** An additive sky-subtraction residual predicts `D_rot ∝ 1/flux_star` (fainter
stars affected proportionally more). The opposite was found:

| airmass cut | faintest quartile | brightest quartile |
|---|---|---|
| > 1.2 | 0.038 [0.033, 0.043] | 0.059 [0.051, 0.071] |
| > 1.4 | 0.050 [0.043, 0.056] | 0.077 [0.063, 0.091] |

`D_rot` **increases** with star brightness, and scales up faster than flux itself — ruling out a simple
additive sky-background residual outright.

![D_rot (sky-subtraction-stage flux) fit separately in quartiles of standard-star brightness (`MODELRFLUX`, the pre-fit stellar template — independent of the effect under test). D_rot increases with star brightness at both airmass cuts shown — the opposite of the ∝1/flux scaling a simple additive sky-background residual would predict, ruling that mechanism out.](../notebooks/figures/dipole_rpt_brightness_split.png)

**Sky-brightness correlation.** Binning exposures by the pipeline's own sky-brightness measurement
(`skylevel`) into terciles and refitting `D_rot` on the sky-subtraction-stage flux:

| airmass cut | low sky | mid sky | high sky |
|---|---|---|---|
| > 1.4 | 0.006 (consistent with 0) | 0.081 | 0.107 [0.091, 0.131] |
| > 1.6 | 0.028 | 0.044 | 0.114 [0.086, 0.144] |

Dark sky gives a dipole consistent with zero; bright sky gives one at or above the established `D_rot` scale
— strong, mostly monotonic evidence that the mechanism needs a real sky background to act on. (A weaker,
noisier version of the same trend appears with lunar separation; the database's moon-phase field is entirely
unpopulated for this sample, so it is treated as corroborative only.)

![D_rot (sky-subtraction-stage flux, airmass > 1.4) fit separately in terciles of the pipeline's own per-exposure sky-brightness measurement (`skylevel`). Dark-sky exposures show a dipole consistent with zero; bright-sky exposures show one at or above the established D_rot scale — evidence the mechanism needs a real sky background to act on, without (per the sky-fiber null in the same section) the sky *model* itself being spatially wrong.](../notebooks/figures/dipole_rpt_skylevel_split.png)

**Sky-residual-in-band, measured directly at sky fibers.** If the assumed sky *model* were simply wrong in a
spatially/zenith-tied way, that error would show up directly by comparing measured flux to the model flux at
fibers with no star light to confound it (`OBJTYPE == 'SKY'`), using the sky model's own per-fiber prediction
(`SkyModel.flux`, already fiberflat-consistent — no re-derivation needed):

| airmass cut | fractional dipole in the sky residual itself |
|---|---|
| > 1.2 – > 1.8 | 0.0001, flat |

**Null**, ~350–800× smaller than `D_rot`. The sky *model* is not spatially wrong. Combined with the two
results above, the mechanism needs the star's own signal present (null with no star) and is modulated by sky
level (from the correlation) without being a defect in the sky estimate itself (from this null) — pointing at
something specific to how a **star's own fiber** is processed during `subtract_sky`, not a property of the
sky background or the sky model in isolation.

### 8.2 Testing concrete mechanisms inside `subtract_sky`

Three specific, code-verified candidates were tested directly, each by reconstructing the relevant part of
`desispec.sky.subtract_sky` and toggling one ingredient while holding everything else — including the real
production flux subtraction — fixed. All three came back null:

| candidate | what it is | test | result |
|---|---|---|---|
| `_model_variance` ivar inflation | A per-wavelength padding term added to the sky model's inverse variance, to force chi²/ndf = 1 against the sky fibers; this inflated ivar is combined into *every* fiber's ivar (`combine_ivar(frame.ivar, skymodel.ivar)`), star fibers included | Recomputed each star's reduced flux using the **pre-inflation** ("statistical only") ivar, saved separately by the pipeline as `stat_ivar` | `D_rot` identical to 4 decimal places with and without the inflation (e.g. 0.0593 vs. 0.0593 at am>1.4). Checking the source directly showed why: the padding term uses the *mean* sky spectrum across sky fibers, not each fiber's own flux — structurally unable to couple to star brightness. |
| Sky-line throughput correction | A per-fiber multiplicative correction, fit from bright sky emission lines, applied to the sky model before subtraction (`subtract_sky`'s `apply_throughput_correction_to_lines`, on by default) | Confirmed active and substantial (fiber-to-fiber std ~10–20%) in this data, then refit `D_rot` with the correction on vs. off | Null (e.g. 0.0593 vs. 0.0591 at am>1.4) — the correction only touches narrow windows around individual sky lines, diluted within the broad 6000–7300Å continuum band used for this measurement. |
| Ivar-weighting of the flux reduction itself | `RCALIBFRAC`'s flux is an inverse-variance-weighted mean across the band; the comparison stellar model (`MODELRFLUX`) is an unweighted sum — a mismatch flagged early in the investigation but not directly tested until this point | Recomputed the reduced flux as a plain, unweighted mean over unmasked pixels (matching how `MODELRFLUX` itself is built), same real sky-subtracted flux otherwise, and refit | Null (e.g. 0.0593 weighted vs. 0.0593 unweighted at am>1.4) — a **bisector** result: this rules out the entire class of ivar-weighting artifacts in one test, not just one named function. |

### 8.3 Where this leaves the mechanism, and the handoff

Put together, the six tests in this section say something quite specific: the rotating dipole is not caused
by an additive sky-model error (§8.1, the sky-fiber null), not by the flux measurement's weighting scheme in
any tested form (§8.2, all three null), and not by any of the previously ruled-out constructions (§6–§7).
What remains is that **the bias is in the sky-subtracted flux values themselves**, requires a star's own
signal to be present, and scales with both the star's brightness and the ambient sky level in a way a simple
additive contamination does not.

This is a well-characterized, handoff-ready localization rather than an open-ended puzzle: four increasingly
targeted, source-code-verified tests inside `subtract_sky` came back null, each for a structural reason
checked directly in the pipeline code rather than left as "we didn't find it." The investigation's
recommendation, consistent with the point where returns from further outside reverse-engineering diminish, is
to hand the following concrete facts to the `desispec` maintainer (**Julien Guy**) and the sky-subtraction
authors, who can identify the exact remaining ingredient far faster than continued external testing:

- The effect is a real, zenith-tied, airmass-growing bias in the r-band flux (scaling *super-linearly* with
  star brightness — §8.1 — so neither a simple additive nor a simple multiplicative term), injected at
  `subtract_sky` (present after that step, absent or much smaller before it, unchanged by the subsequent
  aperture correction).
- It requires the star's own flux to be present (null at pure sky fibers).
- It scales with the star's own brightness (opposite the sign of a simple additive sky residual) and with
  overall sky brightness.
- It is not produced by `_model_variance`'s ivar inflation, the sky-line throughput correction, or
  ivar-weighting of the reduction in general.

Two natural physical candidates from earlier in the investigation — a genuine sky-brightness gradient across
the field, and residual differential atmospheric extinction — remain plausible *contributors* to why the
effect correlates with sky level and airmass, but neither is established as the specific algorithmic
mechanism, and a rough magnitude estimate for differential extinction alone was an order of magnitude too
small; the measured effect's magnitude is not below what's needed, so the shortfall is in the estimate, not
necessarily in the physical picture.

---

## 9. Recommendation for `DAR_FIBER_LOSS_REPORT.md`

Finding 2's core empirical result — a coherent dipole+quadrupole loss pattern that rotates with parallactic
angle and grows with airmass — is unchanged and remains a genuine, useful diagnostic. Two things should be
revised:

1. **The mechanism.** The report currently frames the dipole as evidence that targets drift off their fixed
   fibers under DAR during the exposure. Direct measurement now shows this is not the case for the dipole
   specifically; it is a flux-processing effect localized to sky subtraction. The quadrupole's drift-based
   interpretation is unaffected and independently confirmed.
2. **Scheduling implications that cite the dipole specifically** should be checked against whether they
   actually depend on the quadrupole (which is physically confirmed) or the dipole (which is not a geometric
   effect and should not be used to reason about fiber positioning, dither validation, or physical throughput
   loss from mis-centering). The report's headline recommendation — proximity to transit as the dominant
   lever — is driven by the *rotation* of the DAR offset and its interaction with the field-differential
   term, which is the quadrupole's domain; it should survive, but the report's own wording should be checked
   against this distinction before being cited further.

This document does not make that edit; it is recommended as a deliberate, reviewed follow-up given the
report's existing circulation.

---

## 10. Handoff to `desispec` (Julien Guy)

The finding with the widest reach is not about `DAR_FIBER_LOSS_REPORT.md` at all. It is that **`RCALIBFRAC`'s
sky-subtraction step imprints a spurious, zenith-tied, airmass-growing dipole on the standard-star flux ratio**
(§7–§8) — meaning `RCALIBFRAC`, the metric we adopted, is not a clean flux-loss estimator for a DAR study. The
effect is a property of the calibration/measurement, exposed here only because this study happened to view
`RCALIBFRAC` in a derotated, parallactic-aligned frame where it becomes visible. Its consequences for
`RCALIBFRAC` as a throughput diagnostic — and whether any other pipeline quantity built through `subtract_sky`
inherits a similar zenith-tied bias — are a `desispec` question, not one this study is positioned to answer.

We therefore hand it to **Julien Guy**, who owns/maintains `desispec`, with the §8.3 facts as a concrete
starting point: the effect is localized to star-fiber processing inside `subtract_sky`, requires the star's
own signal, scales super-linearly with star brightness and with sky level, and is *not* produced by the
`_model_variance` ivar inflation, the sky-line throughput correction, or ivar-weighting of the reduction in
general. Identifying the exact algorithmic step is the one piece left, and the pipeline authors can do it far
faster than continued reverse-engineering from outside. **What the coupling implies for DESI flux calibration
more broadly is beyond the scope of this study.**

---

## Acknowledgments and methods note

Steve Kent (Data Systems, PlateMaker/Dervish) confirmed key facts about the pointing/placement pipeline
directly and via his source code: the refraction constant is a single, r-band-calibrated value used
identically for science placement and guide-star acquisition, and placement does not use per-target color.
This closed the guide-vs-science wavelength-mismatch hypothesis definitively (§4) and was essential to ruling
out several early candidates in §3.

This investigation was carried out collaboratively across two Claude sessions (NERSC, with direct access to
the DESI redux tree and database; and Mac, working from committed datasets and code reads), coordinating via
a shared file-based log. Notably, the Mac session's reading of the guider source code produced the reframing
in §4 (the guide loop nulls only the mean, so only guide≠science differentials survive), proposed the dither
offset-field test that produced §5's decisive result, ran the independent epoch-split test that disconfirmed
the aperture-correction candidate in §6 (cross-validated by a second, independent method on the NERSC side),
and designed the entire discriminator sequence in §8 — the bright-vs-faint/sky-level/sky-residual tests that
established the mechanism's *class*, the `_model_variance` and throughput-correction hypotheses (each
specific, falsifiable, and checked directly against the pipeline source before and after testing), and in
particular the unweighted-reduction bisector, which settled the weighting-vs-flux question in one test rather
than requiring further named-function guesses. The NERSC session ran the direct pipeline reconstructions in
§6–§8. Klaus Honscheid directed the investigation, supplied the standing-loss/positioning framing that opened
each new line of testing, and is the domain expert whose judgment calls throughout (which candidates to
prioritize, when a result was strong enough to act on, and when the mechanism-hunt had reached a sensible
handoff point rather than warranting a further round of testing) shaped the sequence above.

## Appendix — key scripts and data

- `analysis/dar_dipole/fit_dipole_quadrupole.py` — the core D_rot/Q_rot measurement.
- `analysis/dar_dipole/affine_fit_lib.py` — shared dipole/quadrupole affine-fit machinery (factored out for
  reuse across §6–§7's tests).
- `analysis/dar_dipole/dither_offset_field_test.py` — §5, the dither offset-field test (`xfiboff`+`xtel`).
- `analysis/dar_dipole/flat_to_psf_dipole_test.py` — §6, direct fit to the aperture-correction factor.
- `analysis/dar_dipole/rebuild_rcalibfrac.py` — §6, `select_calib_stars.py` reimplementation with
  `MODELRFLUX`/`RFLUX` retained (model-vs-data localization).
- `analysis/dar_dipole/flux_chain_decomposition.py` — §7, the 4-stage flux-chain decomposition.
- `analysis/dar_dipole/sky_residual_test.py` — §8.1, the sky-residual-in-band null at sky fibers.
- `analysis/dar_dipole/variance_inflation_test.py` — §8.2, the `_model_variance` pre/post-inflation ivar test.
- `analysis/dar_dipole/throughput_correction_test.py` — §8.2, the sky-line throughput-correction on/off test.
- `analysis/dar_dipole/unweighted_reduction_test.py` — §8.2, the ivar-weighted-vs-unweighted bisector.
- `docs/DAR_DIPOLE_NERSC_HANDOFF.md` — prior working record of §1–§4 (Tests 1, 4, 5, 6; ruled-out
  candidates); this report supersedes it as the narrative account.
- `docs/FOUNDATION_CHECK_REPORT.md`, `docs/TEST6_GUIDE_STAR_RESIDUAL_REPORT.md`,
  `docs/GUIDE_SCIENCE_COLOR_TEST_REPORT.md` — full detail behind §2 and §4.
- Memory `dar-guider-bias-hypothesis` — the complete evolving record, including candidates and reasoning not
  summarized here.
