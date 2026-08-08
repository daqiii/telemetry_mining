# DAR fiber loss — the residual boresight "dipole": investigation state & NERSC plan

K. Honscheid (OSU) with Claude · handoff 2026-08-04, updated 2026-08-05 (NERSC: Tests 1 & 4 run, foundation check, Test 5 cross-term queued)

This is an **open follow-up** to `DAR_FIBER_LOSS_REPORT.md` (which covers the two resolved
findings: the mid-2025 calibration shift and residual DAR). It documents a deeper look at the
*directional* residual-DAR component of Finding 2 — a coherent focal-plane **dipole** in the
standard-star flux loss — and hands the open question to a NERSC session. The published report is
**not** modified for this; it concerns resolved results, this is unresolved research.

---

## TL;DR

- The per-exposure, mean-removed standard-star loss has a **dipole that rotates with the parallactic
  angle** (a genuine DAR signature) whose amplitude is **~2× the DAR quadrupole** and **grows with
  airmass**. Physically it is a **coherent ~10 μm (≈0.14″) offset of the whole star field relative to
  the fiber array**, in the zenith direction, growing with airmass — a *uniform boresight* offset, not
  a field distortion.
- **Ruled out offline as the source** (all by magnitude, despite tempting form-matches):
  1. Steve Kent's PlateMaker **DAR refraction model** (`distort.py`) — it is purely *differential* →
     governs the **quadrupole**, not the dipole; and production already uses the raytrace refraction
     constant (`refract 45`, not 47).
  2. The **GFA gravity/deformation model** (`gfadeform.dat`) — right functional form
     (`cosp/sinp·poly(tan z)`) but its net boresight, averaged over the **balanced** 6-GFA ring,
     is only ~0.02″ (~1.5 μm) — ~5–7× too small; the big per-GFA terms go into field distortion
     (quadrupole), not boresight.
  3. The **reqtime/exptime midpoint-estimate error** — real and systematic (`exptime < reqtime` for
     100% of exposures, median gap 838 s) but **D_rot does not scale with the gap** (flat/decreasing at
     controlled airmass); the guider reference and fiber placement share the same reqtime-midpoint, so
     the mismatch does not imprint a net science offset.
- **Surviving candidate:** a **refraction residual in the absolute-pointing chain** — the polar/pointing
  model that `distort.py` folds the absolute refraction into (lines 206–209, function of HA/Dec) and/or
  the **acquisition astrometric solution**. This is a calibration *residual*, best **measured on NERSC**
  rather than reproduced offline.

---

## The measured effect (D_rot)

**Method** (`analysis/dar_dipole/fit_dipole_quadrupole.py`): per star, derotate focal-plane (X,Y) by the
exposure parallactic angle `q` (zenith on a fixed axis), per-exposure demean the loss (removes the
Finding-1 monopole / transparency), then pool and fit **simultaneously**:

```
loss ~ radial(x'²+y'²)
     + fixed dipole (x', y')            # instrumental, focal-plane-fixed
     + rotating dipole (x'q, y'q)       # DAR, rotates with q  -> D_rot
     + fixed quadrupole (x'²−y'², 2x'y')
     + rotating quadrupole (2q)         # DAR compression      -> Q_rot
```

Amplitudes are edge values (normalized coords), same loss units, so ratios are dimensionless.

**Results** (complete population, bootstrap-over-exposures CIs):

| airmass cut | D_rot | Q_rot | **D_rot/Q_rot** | D_fix |
|---|---|---|---|---|
| > 1.4 | 0.035 | 0.017 | **2.03** [1.94, 2.12] | 0.028 |
| > 1.6 | 0.056 | 0.029 | **1.93** [1.82, 2.10] | 0.029 |
| > 1.8 | 0.080 | 0.046 | **1.75** [1.55, 2.04] | 0.029 |

- **D_rot grows steeply with airmass; the fixed instrumental tilt D_fix stays flat (~0.029)** — a fit
  artifact would not sort by airmass like that.
- **q-permutation null is decisive**: shuffling parallactic angle across exposures collapses D_rot
  0.044 → 0.002 — the rotating signal is genuinely q-locked (not collinearity/monopole leakage).
- Robust to loss-clip (D/Q ≈ 1.85–1.94 for clips 0.30 → 0.08).
- Dipole direction in the derotated frame ≈ −105°, stable across airmass and gap bins.

**Physical scale** (`analysis/dar_dipole/calibrate_sigma_eff.py`, real desimodel `FastFiberAcceptance`):
σ_eff ≈ **52 μm** (fiber-size dominated, ~insensitive to seeing/radius), giving
**δ₀ ≈ 8–12 μm (central ~10 μm ≈ 0.14″)**. The uniform offset alone implies an order **~2%** flux loss
(δ₀²/2σ²), though that monopole is confounded with the calibration shift.

Interpretation: `loss ≈ |δ₀ + G·r|²/2σ²`. The **dipole is the cross term δ₀·G** and exists only if the
*uniform* offset δ₀ ≠ 0; the **quadrupole is |G·r|²** (the field-differential compression). So a dominant
rotating dipole ⟹ a real, coherent, zenith-tied uniform boresight offset that the once-per-exposure
placement + guiding does not remove.

### Cross-check: our quadrupole matches Weiner and Kirkby — the difference is only the dipole

Converting the measured rotating quadrupole to a physical edge offset (`ΔG = σ_eff·√(2 Q_rot)`,
σ_eff = 52 μm, plate ~71 μm/arcsec):

| our airmass bin | Q_rot | ΔG (edge) | reference (airmass ~2) |
|---|---|---|---|
| 1.48 | 0.012 | 8.0 μm (0.11″) | |
| 1.69 | 0.025 | 11.6 μm (0.16″) | |
| **1.86** | **0.045** | **15.5 μm (0.22″)** | Kirkby DESI-8586: ~15 μm (0.21″) sky motion at X=2 |
| → 2.0 (extrap.) | | ~18–20 μm (~0.25″) | Weiner DESI-9817: ~0.25″ (~18 μm) edge motion at X=2 |

Three independent analyses — our loss-based quadrupole, Weiner's astropy geometry, Kirkby's guider
sky-motion — **converge on ~15–20 μm intra-exposure edge motion at high airmass.** On top of that agreed
quadrupole we measure a rotating **dipole ~2× larger** (D_rot/Q_rot ≈ 1.9) — the ~10 μm boresight offset —
which Weiner (referenced to the tracked field center) and Kirkby ("ideal guiding removes any dipole") both
set to zero by construction. So the discrepancy is exactly, and only, the dipole. (The μm conversion
carries ~factor-2 uncertainty from σ_eff + a √3 time-averaging factor; the robust conversion-free
statement is D_rot/Q_rot ≈ 1.9.)

**Steve's DAR model reproduces the standard compression.** For a field-edge star (1.6° in the zenith
direction), `distort.py`'s first-order refraction gives δ = −θ·R·sec²z with R = 45″ (see
`analysis/dar_dipole/steve_dar_shifts.py`): ~5.0″ at z=60° (X=2), ~1.7″ at z=30° — matching the textbook
DAR compression and Weiner's quoted 4.8″/1.6″ to a few percent. This is the **static** compression, which
fiber placement removes; our measured quadrupole (ΔG ~0.2″) is the ~5% **intra-exposure residual** of it,
consistent with Weiner/Kirkby. So the DAR model is correct standard physics and the quadrupole is
accounted for end-to-end — leaving the dipole as the sole anomaly.

---

## Ruled out (see memory `dar-guider-bias-hypothesis` for full detail)

- **`distort.py`**: 1st order (`f1`–`f4`, linear in field position) and 2nd order (`dv`, quadratic,
  the 2026-03 PlateMaker change) are both **zero at field center → differential → quadrupole**. Absolute
  refraction explicitly zeroed (line 209) and folded into the polar/pointing term. `desi.par` line 361
  `refract 45` (production). Refraction-constant knob touches the **quadrupole** (~0.2″ center-to-edge at
  airmass 2), not the dipole.
- **`gfadeform.dat` / `gravity.py`**: per-GFA `cosp/sinp·poly(tan z)` deformation ~0.1–0.26″ (right form,
  right per-GFA scale) BUT the 6 guide GFAs (petals {0,2,3,5,7,8}) form a **balanced ring** → the big
  terms cancel in the boresight average → net ~0.02″ (~1.5 μm), ~5–7× too small. Verified with real
  PlateMaker geometry from `pm363330/gfadata-363330.5.par`
  (`analysis/dar_dipole/net_boresight_gfadeform.py`).
- **reqtime/exptime midpoint error**: `analysis/dar_dipole/reqtime_exptime_test.py` — D_rot does not
  scale with (reqtime − exptime) at controlled airmass; ruled out.

---

## Foundation check (2026-08-05) — is D_rot real, or an artifact of the committed parquet?

Run after Test 1 and Test 4, per the user's request: the entire dipole result rested on
`notebooks/data/dar_calibstars_dataset.parquet`, generated in an earlier (pre-NERSC) session and never
independently regenerated — every "reproduction" so far was a deterministic re-fit of that same file,
which validates the fit code, not the data-generation step.

**Check 1 (decisive): independently regenerate the dataset from the DB and re-fit.** Rebuilt the pooled
`calibstars` pull from scratch via `telemetry_mining.query.select_exposures` + `harvest` (same WHERE
clause as `notebooks/data/README.md` documents: `sequence in ('DESI','_Split')`,
`program in ('DARK','BRIGHT','DARK1B','BRIGHT1B')`, `totteff > 60`, `VALID==1` calibstars rows) — not the
original ad hoc build scripts (never committed), a fresh implementation matching the documented
selection. Result: **24,716 exposures / 2,579,981 star rows** (vs. the committed parquet's 24,630 /
2,570,324 — the small excess is ~2 weeks of new survey data added since the original was built on
2026-07-21, expected, not a discrepancy). Independently pulled `parallactic` fresh from the DB (not
reusing the committed `data/dar_exposure_pointing.csv`) and ran the unmodified
`fit_dipole_quadrupole.py` logic:

| airmass cut | D_rot (fresh) | Q_rot (fresh) | D_rot/Q_rot (fresh) | D_rot/Q_rot (original handoff) |
|---|---|---|---|---|
| >1.4 | 0.0353 | 0.0174 | **2.03** [1.94,2.13] | 2.03 [1.94,2.12] |
| >1.6 | 0.0560 | 0.0285 | **1.97** [1.85,2.13] | 1.93 [1.82,2.10] |
| >1.8 | 0.0810 | 0.0464 | **1.74** [1.57,1.97] | 1.75 [1.55,2.04] |

Matches to 2-3 significant figures, well within bootstrap CI overlap, from a fully independent
code path and a slightly larger, more recent population. **The dipole is not an artifact of the
committed parquet's generation.**

**Check 2: X/Y provenance.** Rather than redoing the `desimeter` cross-check the main report already
did (validated to std 0.003° against the DB `parallactic` column), checked directly whether
`dar_calibstars_dataset.parquet`'s `X`/`Y` could contain any pre-applied per-exposure rotation: X,Y for
a given FIBER should be constant if it's a fixed mechanical focal-plane position, and should visibly
rotate with `parallactic` if a per-exposure sky-referenced transform were baked in. Checked the 5
most-observed fibers (up to 763 exposures each, spanning the full survey's range of airmass/parallactic
angle): X,Y std ~2.7-2.9mm around a mean of order 100s of mm (~0.7-1% relative) — consistent with
ordinary fiber-positioner dither precision between exposures, and far too small to be a field rotation
(rotating a ~400mm-radius focal plane by any real parallactic-angle range would move an edge fiber by
tens of mm, not ~3mm). **X,Y is confirmed a static, instrument-fixed CS5-like frame with no detectable
per-exposure rotation baked in.**

**Check 3 (optional): RATIO_RAW cross-check — not attempted, correctly not cheap.** Per memory
`flux-truth-variables`, `RATIO_RAW` (the correction-OFF raw measured/expected ratio) does not exist yet
— it requires reprocessing `select_calib_stars` with the flat→psf correction disabled against
`redux/daily` inputs, already a standing NERSC-TODO in that memory (items 1-2), not a quick query. Left
as a follow-up, per the user's own "only if cheap" instruction — not blocking anything above.

**Conclusion: the ground under Test 1 and Test 4 (and everything upstream) is sound.** D_rot is real,
reproducible from an independent pull, and not a coordinate-frame artifact. This closes the one
unaudited gap in the investigation; work can proceed on the actual mechanism question without revisiting
this.

---

## NERSC plan (prioritized)

**Test 1 — the primary discriminator: decompose the applied acquisition/pointing offset.**
For a high-airmass sample of exposures, get the **applied boresight offset the astrometric acquisition
solution produced** (per exposure). Sources, in PlateMaker world first:
- Steve's per-exposure PlateMaker archive — the `gfadata-*.par` files carry `xi0`, `eta0` (field-center
  offset), `psi`, `zd`, and the polar/refract terms. Pull these for many high-airmass exposures.
- Cross-check with the exposure DB / TCS logs: the applied ΔRA/ΔDec acquisition offset, guider corrections.

Decompose each exposure's applied offset into a **zenith-projected component** (along the parallactic
direction) and a **fixed RA/Dec component**, versus airmass. Compare:
- zenith-projected, growing with `tan z`, ~0.14″  →  **matches D_rot** ⟹ the dipole is the
  acquisition/pointing refraction residual (the surviving candidate confirmed);
- fixed RA/Dec, airmass-flat  →  matches **D_fix** (the instrumental tilt);
- flat/random  →  the dipole is *downstream* of pointing (placement or something else) — re-open.

> **STATUS (2026-08-05, run on NERSC): done, INCONCLUSIVE by construction, not confirmed/refuted.**
> `analysis/dar_dipole/acquisition_offset_test.py` on `data/dar_acquisition_offset.parquet`
> (`tcs.mount_offset_ra/dec`, cross-checked against `telemetry.ocs_gfadata.xi0/eta0` — independently
> reproducible, real signal). The zenith-projected component grows monotonically with airmass (17″ at
> am>1.0 → 41″ at am>1.8) but at **~100-300× the D_rot≈0.14″ scale** — dominated by the legitimate bulk
> refraction/pointing correction, not a small residual, so a naive mean-vs-airmass regression can't
> resolve the anomaly either way. Needed refinement (not done): subtract the known modeled part
> (DervishTools `distort.py`'s own polar-axis formula, needs the real `a0,b0,z0,t0,b2,b4` constants) and
> look for a small excess in the residual, or find a quantity that isolates intra-exposure drift instead
> of the once-per-exposure acquisition value. Full detail in memory `dar-guider-bias-hypothesis`.

**Test 4 — affine (6-param) decomposition of the ETC per-frame per-GFA guide offsets, queued to run
right after Test 1 (shares its data pull with Test 2 — pull the ETC guide-offset data once, use for
both).** Motivation: `FIELD_ROTATION_REPORT.md` Part 5 concluded no dynamic rotation correction because no
driver survived testing against the **guider's per-star, per-frame rotation fit**, which is noisy (GFAs
carry 1–5 stars each; GUIDE7 often just 1 — see [[field-rotation-report]]). The ETC json's per-frame,
per-GFA offset vectors (`thru/dx_gfa`, `thru/dy_gfa`, 6 GFAs × 2 coords = 12 measurements per frame) let
us do a **6-parameter affine fit per frame instead**: translation (2) + rotation (1) + isotropic scale
(1) + anisotropic shear/quadrupole (2). One decomposition serves three questions at once:
- **translation → boresight** (the D_rot dipole; feeds Tests 1/2 directly, same physical quantity at
  finer time resolution — per-frame instead of once-per-exposure).
- **rotation → field rotation.** Track θ(t) over the exposure, subtract the static hexapod `rot_rate`
  model prediction, and check whether the residual is a smooth systematic drift (⟹ a dynamic correction
  would remove real rotation error — reopens the static-vs-dynamic decision in
  `FIELD_ROTATION_REPORT.md` Part 5) or flat noise (⟹ static model reconfirmed at higher precision).
- **shear → DAR compression** (our Q_rot, at finer time resolution than the once-per-exposure fit).

Caveats (respect all of these — this is exactly the kind of test that can look like a signal and not be
one):
- **Fit rotation and shear together, never rotation alone** — per Kirkby's "rotating a quadrupole is
  zero-sum": only a genuine rigid rotation is dynamically correctable, so the shear term must be present
  to absorb the DAR compression, or a real quadrupole will alias into a spurious rotation estimate.
- The 6 GFAs are **~co-radial** → isotropic scale and radial shear are partly degenerate. Check the
  fit's condition number / parameter covariance per frame before trusting the rotation–shear split;
  don't just report the point estimate.
- **`gfadeform.dat`'s `cosp/sinp·poly(tan z)` term aliases into rotation+shear.** Verify its
  intra-exposure change is negligible over a single exposure's duration, or apply `gravityComp` (see
  `~/DervishTools-python/python/desi/gravity.py`) first to remove it before fitting.
- **Verify the noise premise before trusting the result**: directly compare per-frame θ scatter from this
  ETC-per-GFA affine fit against the guider's existing per-star rotation value, for the same frames. If
  the ETC-based fit isn't actually lower-noise, the motivating premise fails and the rest doesn't matter.
- **Prior expectation is a null** (Kirkby's zero-sum argument, and `FIELD_ROTATION_REPORT.md`'s existing
  conclusion) — this is worth doing because it could genuinely go either way at this improved precision,
  but don't bet on finding a new dynamic-correction signal; a null (flat, static-model-consistent
  residual) is a fully successful outcome, not a failed test.

> **STATUS (2026-08-05): DONE — full report at `docs/TEST4_AFFINE_GFA_REPORT.md`.** Validated on two
> single exposures first (conditioning + noise-premise checks both passed, at high and low airmass),
> then scaled to the full am>1.4 sample (2968 exposures, 100% success). Rotation channel: residual rate
> is consistent with (not a challenge to) `FIELD_ROTATION_REPORT.md`'s existing static-model conclusion —
> does not reopen Part 5. Translation/dipole channel: the naive rate×duration proxy does NOT show the
> expected D_rot-matching signature, but the conversion used is very likely not the physically correct
> one (needs the differential-DAR drift rate G(t) folded in, per the correct-placement cross-term
> reasoning in memory `dar-guider-bias-hypothesis`) — **not decisive either way**, see the report's
> Caveats section before drawing any conclusion from it.

**Test 5 — the physically-correct dipole cross-term (Test 4's #1 open item; the decisive intra-exposure-drift test; NOT yet run).**
The Test 4 translation channel used drift-rate × duration, which is the wrong quantity — under midpoint
placement a symmetric drift gives zero net offset. The loss-dipole is the **cross-term**

  dipole-gradient = ⟨ M_shear(t)ᵀ · T(t) ⟩_t / σ² ,

where, per ETC frame, **T(t) = the affine translation** (the boresight residual `resid(t)`) and the
affine **shear (e1,e2) = the field's own differential-DAR term `G(t)`**. It is **nonzero even for a
symmetric linear drift** (the product of two *correlated* drifts, not one drift's mean) — exactly why
the naive metric missed it. `affine_gfa_drift_test.py` already fits both per frame; only the slopes were
saved. Recipe:
1. Re-run the affine fit **retaining the per-frame time series** of translation (tx,ty) and shear (e1,e2).
2. Per exposure form `C = ⟨ M_shear(t)·T(t) ⟩_t`, with `M_shear = [[e1,e2],[e2,−e1]]` → per frame
   `M_shear·T = (e1·tx + e2·ty, e2·tx − e1·ty)`, time-averaged **directly from the series** (no linearity
   assumption). `C` is the dipole-gradient contribution from intra-exposure drift.
3. Convert to physical loss-dipole units (real desimodel platescale, **not** 0.070 mm/arcsec; σ_eff=52μm).
4. Decompose `C` into zenith-tied vs fixed (same q-convention as `fit_dipole_quadrupole.py`), bin by
   airmass (>1.4/1.6/1.8), bootstrap CI.
5. Compare to D_rot (~0.11/0.16/0.22″, growing with airmass).

Win: zenith component of `C` grows with airmass and matches D_rot ⟹ intra-exposure guiding-residual
drift beating against the differential-DAR field **is** the dipole source. Flat/small ⟹ it isn't, and
the remaining candidates are the guide≠science boresight bias (Test 2) or the absolute-pointing residual.
Caveats: verify `gfadeform.dat`'s intra-exposure change is negligible (or apply `gravityComp` per frame
first — it aliases into both T and shear); keep rotation/scale out of the DAR term (shear is G, not full
M); hypothesis-soft — decisive version of the test, but it can genuinely go either way.

> **STATUS (2026-08-05): DONE — full writeup in `docs/TEST4_AFFINE_GFA_REPORT.md`'s "Test 5" section.**
> `analysis/dar_dipole/affine_gfa_crossterm_test.py`; data `data/dar_test4_crossterm.parquet`. Computed
> `C = ⟨M_shear(t)·T(t)⟩` directly from the per-frame series (no linearity assumed) for all 2968 am>1.4
> exposures; converted to `D_rot_predicted = Rn·C_zenith/σ_eff²` — directly comparable to
> `fit_dipole_quadrupole.py`'s own D_rot, no arcsec/platescale conversion needed for the core comparison
> (real desimodel platescale, confirmed working on NERSC without the Mac session's manual install, used
> for the secondary arcsec-equivalent reporting). **Result: real, statistically significant (bootstrap CI
> never crosses zero), and grows with airmass — but explains only ~3-4% of D_rot's magnitude** (0.00108
> vs 0.0353 at am>1.4; 0.00344 vs 0.0810 at am>1.8). `gfadeform.dat`'s intra-exposure change checked
> quantitatively this time (not hand-waved): ~0.44μm over a representative 23.5min high-airmass exposure,
> small vs ~6-9μm measured T(t) scatter — its absolute value (~2μm) also reproduces the already-ruled-out
> gravity-deformation finding almost exactly, confirming `net_boresight_gfadeform.py` still works
> correctly on NERSC. Unexplained wrinkle: the "fixed"-direction component of `C` is larger and grows
> *faster* with airmass than the zenith component — opposite of the pure hypothesis's prediction, and an
> open question in its own right. **Per the win/lose framing above: this is the "flat/small" outcome, not
> the win** — real but not dominant. Remaining candidates: guide≠science boresight bias (Test 2) or the
> absolute-pointing residual (Test 1, itself still inconclusive).

**Test 6 — guide-star astrometric post-fit residuals (the guide≠science question, direct version).**

> **STATUS (2026-08-05): DONE — full report at `docs/TEST6_GUIDE_STAR_RESIDUAL_REPORT.md`.** Found
> `pm-<expid>.fits` (the real PlateMaker product, in every exposure directory alongside
> `desi-<expid>.fits.fz`) with per-guide-star catalog vs. observed positions (`PMGSTARS`) and the fitted
> per-GFA WCS (`PMGWCS`). Measured residual (observed vs. catalog, through the already-corrected WCS) is
> real, ~100σ significant, vanishes at zenith, grows ∝tan(z) — zenith-tied regression
> a=+0.025±0.003, b=−0.493±0.005 across 21312 exposures. Decisive test ruled out ordinary sampling
> incompleteness on the known achromatic `distort.py` DAR model (zero correlation with the measured
> residual). Quantified as a ~1.1-1.3% systematic refraction-constant error; a Gaia-color follow-up found
> this is flat with color, not sloped — disfavoring a wavelength/effective-λ mismatch, leaving a
> non-chromatic constant error as the surviving candidate by elimination. **Open, pending Steve Kent:**
> whether `PMGWCS` is pre- or post-mount-correction — gates any magnitude comparison to D_rot. Real,
> unresolved, most promising lead in the investigation — not yet confirmed as D_rot's source.
>
> **UPDATE (2026-08-05): guider-code reframing + color test, full report
> `docs/GUIDE_SCIENCE_COLOR_TEST_REPORT.md`.** Reading the actual guider code (Mac session) established
> it only ever nulls the mean guide-star offset (pure boresight) — so any refraction error *common* to
> guide+science is corrected away, and D_rot requires a genuine guide≠science *differential*. Test 6's
> quadrupole (rotating shear) independently matches Q_rot's ΔG (0.102″/0.168″ vs 0.11″/0.16″ at
> am~1.5/1.7) — confirms guide+science see the same common DAR field, explaining why D_rot is smaller
> than Test 6's full residual (only the differential survives). Tested the natural candidate (standard
> stars bluer than guide stars → residual DCR the loop doesn't correct): Step A confirms the color offset
> decisively (Δ(BP-RP)=−0.415, >100σ); Step B (DCR magnitude, r-band-confined on all 3 sides) predicts
> only ~0.02″, smaller than D_rot; Step C (D_rot refit on blue vs red standard-star halves) is flat, no
> detectable color dependence (though with modest ~20% leverage vs Step A's full contrast).
> **Conclusion: chromatic DCR is real but sub-dominant, not D_rot's dominant source — the dominant
> mechanism remains open.**

**Test 2 — guide vs science (the guide≠science question).** Compare the guider residual field
(ETC `thru/dx_gfa`, `thru/dy_gfa`, GFA px→CS5) boresight to the science-field δ₀. A boresight the
science fibers feel but the guide stars don't = the guide≠science signature. Kirkby (DESI-8586) sees a
small guide-star dipole because a closed loop nulls the guide-star mean by construction and his metric is
intra-exposure drift — so this is *not* evidence against a science-field δ₀.

**Test 3 — reproduce + enrich.** Re-pull the pooled `calibstars` loss dataset (RCALIBFRAC + focal-plane
X/Y) joined to per-exposure pointing **plus the applied boresight offset / acquisition residuals**;
reproduce D_rot to confirm continuity and extract the dipole PA per airmass to compare with the predicted
zenith direction.

**Data to pull:** applied acquisition boresight offset per exposure (live on NERSC as `exposure.exposure`
`tcs.mount_offset_ra/dec` and/or `telemetry.ocs_gfadata.xi0/eta0` — see Test 1 status note above; the
file-based PlateMaker `gfadata-*.par` archive on NERSC is a dead 2019 snapshot, don't use it); ETC
**per-frame, per-GFA** `thru/dx_gfa`/`dy_gfa` (in `etc-<expid>.json`, shared by Test 2 and Test 4 — pull
once); guide-star catalog (GFA/petal, mag, r-band); RCALIBFRAC + X/Y; pointing/timing (pattern in
`scripts/fetch_exposure_pointing.py`); for Test 4's rotation check, also the hexapod `rot_rate` value
per exposure (already in `exposure.exposure.hexapod`) and, if pursuing the `gfadeform.dat` caveat,
`~/DervishTools-python/python/desi/gravity.py`'s `gravityComp`.

**Also standing (separate) NERSC to-dos** — see memory `flux-truth-variables` and
`dar-before-after-platemaker-analysis`: reprocess a `RATIO_RAW` (correction-OFF) calibstars sample to
verify the Finding-1 flat→psf (desispec PR #2484) origin; build the enriched calibstars table.

---

## Files / scripts

- `analysis/dar_dipole/fit_dipole_quadrupole.py` — measures D_rot, Q_rot, D_fix, D_rot/Q_rot vs airmass.
- `analysis/dar_dipole/robustness_and_delta0.py` — outlier robustness, **q-permutation null**, δ₀ vs σ.
- `analysis/dar_dipole/calibrate_sigma_eff.py` — σ_eff from real `FastFiberAcceptance` → δ₀ (needs desimodel).
- `analysis/dar_dipole/quad_compare_weiner_kirkby.py` — Q_rot→ΔG(μm) vs Weiner/Kirkby (the quadrupole match).
- `analysis/dar_dipole/steve_dar_shifts.py` — Steve's `distort.py` DAR compression vs standard formula/Weiner.
- `analysis/dar_dipole/net_boresight_gfadeform.py` — GFA-deformation net boresight (ruled-out record).
- `analysis/dar_dipole/reqtime_exptime_test.py` — reqtime/exptime midpoint-error test (ruled-out record).
- `analysis/dar_dipole/acquisition_offset_test.py` — Test 1: zenith-vs-orthogonal decomposition of the
  applied acquisition offset (`tcs.mount_offset_ra/dec` / `ocs_gfadata.xi0/eta0`) vs airmass. Done,
  inconclusive (see Test 1 status note above) — needs the refinement described there before rerunning.
- `analysis/dar_dipole/affine_gfa_drift_test.py` — Test 4: per-frame affine decomposition of the ETC
  per-GFA offsets (translation/rotation/scale/shear). Done; report `docs/TEST4_AFFINE_GFA_REPORT.md`,
  data `data/dar_test4_drift.parquet` (slopes only — superseded for the dipole question by Test 5 below).
- `analysis/dar_dipole/affine_gfa_crossterm_test.py` — Test 5: the physically-correct dipole cross-term
  `⟨M_shear(t)·T(t)⟩`, computed directly per frame (no linearity assumed). Done; report in
  `docs/TEST4_AFFINE_GFA_REPORT.md`'s "Test 5" section, data `data/dar_test4_crossterm.parquet`. Real,
  grows with airmass, but only ~3-4% of D_rot's magnitude — not the dominant mechanism.
- `analysis/dar_dipole/pmgstars_residual_test.py`, `distort_model_vs_measured_test.py`,
  `pmgstars_color_test.py` — Test 6: guide-star post-fit astrometric residuals from the real PlateMaker
  `pm-<expid>.fits` product. Done; report `docs/TEST6_GUIDE_STAR_RESIDUAL_REPORT.md`, data
  `data/dar_pmgstars_residuals.parquet`, `dar_distort_model_vs_measured.parquet`, `dar_pmgstars_color.parquet`.
  Real, ~100σ signal, right functional form, ~1.1-1.3% systematic refraction error, not chromatic — most
  promising open lead; magnitude-vs-D_rot comparison pending whether PMGWCS is pre/post mount-correction.
- Foundation check: `docs/FOUNDATION_CHECK_REPORT.md` — D_rot independently reproduced from a fresh
  from-DB rebuild (2.03/1.97/1.74 vs 2.03/1.93/1.75) → not a data artifact; X/Y confirmed instrument-fixed.
- Inputs: `notebooks/data/dar_calibstars_dataset.parquet`, `data/dar_exposure_pointing.csv`,
  `data/dar_acquisition_offset.parquet` (Test 1's pull: `mount_offset_ra/dec`, `xi0/eta0`, airmass,
  parallactic, zd, per exposure — 24630 rows, live-DB sourced on NERSC 2026-08-05).
- PlateMaker reference (NERSC, current install): `~/DervishTools-python/python/desi/` (`distort.py`,
  `multiproc.py`, `wcs.py`, `target.py`, `gravity.py`) — supersedes the older Mac path
  `~/software/pyro5/DervishTools-python/...`. File-based archive `pm363330/` (one full exposure's PM
  files from the Mac working copy) plus `gfadeform.dat`, `gfaoffset-desi.dat`, `desi.par` are still
  useful as static references but are NOT present/synced on NERSC for current exposures (the NERSC
  `/global/cfs/cdirs/desi/engineering/platemaker/` archive is a dead 2019 snapshot) — use the live
  `telemetry.ocs_gfadata` DB table instead for current-era per-exposure PlateMaker output.

## Related
- `docs/DAR_FIBER_LOSS_REPORT.md` (resolved findings; Part II §4–§7 = the directional-DAR / dipole this extends).
- Memory: `dar-guider-bias-hypothesis` (full evolving record), `dar-before-after-platemaker-analysis`,
  `flux-truth-variables`, `field-rotation-report`.
