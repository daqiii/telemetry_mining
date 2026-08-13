# Measured-vs-Expected Flux from Standard Stars: `RCALIBFRAC`, Its Sky-Subtraction Bias, and Which Variable to Use

**Status:** for the Data Systems / calibration team (J. Guy). Part of the `telemetry_mining` / Exposure-module
documentation family; companion to `DAR_FIBER_LOSS_REPORT.md` (the DAR study that produced the sky-subtraction
finding), `FIBER_LOSS_METRICS.md` (the artifact-free `L_see`/`L_field` metrics), `API.md`, and `FIELDS.md`.

K. Honscheid (OSU) with Claude (Anthropic) · rewritten 2026-08-13 (supersedes the 2026-07-24 draft, which
predated the sky-subtraction finding and the geometric metrics).

> **Purpose.** For telemetry / observing-conditions studies we want a per-exposure variable that says *"this is
> what we measured, this is what we should have measured"* — a flux-loss / throughput diagnostic — so we can
> correlate it against wind, seeing, transparency, mirror temperature, positioning, and so on. Standard stars are
> the only clean on-sky "known truth." This note pins down how the candidate variables are built (from the
> `desispec` source), what each one does and does not measure, and — the main addition since the first draft —
> **why the obvious choice, `RCALIBFRAC`, is not a bias-free flux-loss estimator**: beyond two construction
> quirks, it carries a **zenith-tied dipole injected at the sky-subtraction step**, which we tracked down but did
> not fully pin. It closes with what to use for which study, and two concrete items for `desispec`.

---

## Executive summary

- **The truth reference is the standard star:** measured r-band flux / model r-band flux = end-to-end
  throughput (atmosphere × telescope × instrument × fiber-aperture loss). `RCALIBFRAC` (the `calibstars` QA
  product) is the pipeline's normalized version of this ratio.
- **`RCALIBFRAC` carries three biases, in increasing order of subtlety:**
  1. **Median normalization** — each exposure's median is forced to 1, so `RCALIBFRAC` is blind to *absolute*
     throughput and reports only within-exposure, fiber-to-fiber variation.
  2. **A mid-2025 aperture-correction step** — a point-source (flat→psf) correction (PR #2484) was added in
     mid-2025; because `daily` is not reprocessed, this is a **step discontinuity** across the archive.
  3. **A sky-subtraction dipole** *(new)* — `RCALIBFRAC`'s spatial structure includes a zenith-tied,
     airmass-growing dipole that *looks like* DAR but is a **flux-processing bias entering at `subtract_sky`**,
     general to all point-source spectrophotometry — not a `RCALIBFRAC`-specific effect. We localized it and
     ruled out several mechanisms, but the exact algorithmic step is **not pinned**.
- **Which variable to use:**
  - **Level / loss-attribution** (seeing, wind, mirror-ΔT, …) → **`RATIO_RAW`** (raw absolute measured/model,
    aperture-correction off). The dipole is a *pattern* and averages out over the focal plane, so this is clean
    for level work — but note it does **not** escape the sky-subtraction bias for anything spatial.
  - **Absolute, science-grade throughput** → the **flux-cal scale**, derived from the per-exposure
    `fluxcalib-*.fits` vectors in the redux tree (a small accessor, not yet built).
  - **Spatial / DAR structure** → **no flux ratio is clean.** Use the artifact-free **geometric** GFA metrics
    `L_see` / `L_field` (see `FIBER_LOSS_METRICS.md`); the dither offset field is the only clean geometric probe.
  - **Depth / "good exposure?"** → `EFFTIME_SPEC` / `TSNR2` (convenient but conflates throughput, transparency,
    sky, and time).
- **For `desispec` (details in the last section):** one finding to hand over — the **`subtract_sky` point-source
  dipole** (a real, zenith-tied bias in a pipeline product; localized to that step, mechanism not yet
  identified). The known mid-2025 `RCALIBFRAC` discontinuity is *not* an ask on the team — for our purposes it is
  simply avoided by working from a uniformly-reprocessed release (e.g. Matterhorn or Nevis) instead of the
  `daily` archive.

---

## 1. The known truth: standard stars

A standard star has a **model SED** (`MODELRFLUX` etc.), obtained by fitting a stellar template to the star's
broadband photometry (imaging / Gaia). That model is "what we should have measured" above the atmosphere. The
**measured** flux is what actually reaches the detector through the fiber. Their ratio is the end-to-end system
throughput — atmosphere (extinction + transparency) × telescope × instrument × **fiber aperture loss**. Standard
stars are the only per-exposure, on-sky, absolute reference we have, so every measured-vs-expected variable below
is anchored on them. *(Caveat: the "truth" is only as good as the template/photometry calibration — the best
available reference, not a perfect absolute.)*

## 2. How `RCALIBFRAC` is built — two construction layers to know

From `desispec/scripts/select_calib_stars.py`, per exposure:

1. Read the r-camera frames, **apply fiberflat, subtract sky**.
2. **Apply a point-source (flat→psf) aperture correction** to the flux (line 131–132):
   `flux *= flat_to_psf_flux_correction(fibermap, exposure_seeing_fwhm=1.1, normalize=False)` — see §2.1.
3. `ratio = rflux / MODELRFLUX` per star (measured / model, summed 6000–7300 Å).
4. `medval = median(ratio)` over the exposure's stars (line 168) — **the absolute throughput** …
5. … then `RCALIBFRAC = ratio / medval` (line 173) — **`medval` is divided out and not saved.**
6. `VALID` flags 3σ `RCALIBFRAC` outliers and G−R color mismatches.

**Layer 0 — median normalization.** Step 5 forces each exposure's *median* `RCALIBFRAC` to 1, so `RCALIBFRAC`
carries only **within-exposure, fiber-to-fiber variation** — blind to the exposure's absolute throughput
(anything dimming all fibers together is normalized away). A per-exposure "mean loss = 1 − mean(`RCALIBFRAC`)"
therefore measures the *differential* loss, not the absolute one.

**Layer 1 — the aperture correction** (step 2, added mid-2025). `RCALIBFRAC` measures the residual *after* the
pipeline's modeled static aperture loss has been divided out.

### 2.1 The flat→psf aperture correction (`fiberfluxcorr.flat_to_psf_flux_correction`)

Per fiber it computes the captured point-source light fraction and divides the flux by it:

- inputs: **`FIBER_X/Y`** → radial plate scale; **`DELTA_X/DELTA_Y`** → the fiber-to-target positioning offset;
  and a **seeing FWHM** → PSF size σ.
- `fiber_frac = FastFiberAcceptance("POINT", σ, offset)`; correction `= 1 / fiber_frac / platescale²`.

So the corrected flux ≈ `F_true · fiber_frac_actual / fiber_frac_model`, and after the ratio/median step
`RCALIBFRAC` retains only the **residual** `fiber_frac_actual / fiber_frac_model` — i.e. what the model gets
*wrong* or can't see: seeing ≠ the assumed 1.1″; intra-exposure / dynamic effects (`DELTA_X/Y` is one online
snapshot, so wind jitter, tracking, and **DAR drift** survive); optics/coordinate-model error; and a purely
radial reshaping via `1/platescale²`.

### 2.2 The same correction lives in three products — with different seeing

| product | file | seeing used | notes |
|---|---|---|---|
| **`RCALIBFRAC`** (calibstars QA) | `select_calib_stars.py` | **hardcoded 1.1″** | `normalize=False`; then median-normalized |
| **flux-cal vector** (science flux) | `fluxcalibration.py` | **actual/estimated exposure seeing** | vector `= C_fiber / FLAT_TO_PSF_FLUX`; wavelength-resolved |
| **`TSNR2` → `EFFTIME`** | `tsnr.py` | (as used there) | folds the same correction |

The science flux calibration uses the **actual** seeing (a more correct aperture correction); the calibstars QA
uses a **fixed 1.1″** (a cruder version whose residual still carries a seeing-vs-1.1″ signal).

## 3. The mid-2025 discontinuity: `RCALIBFRAC` changed, and `daily` is not reprocessed

Data releases are reprocessed uniformly; **`daily` is not** — each night is processed once with the then-current
code. So the mid-2025 addition of the aperture correction (**PR #2484**, "add psf correction to RCALIBFRAC",
merged 2025-05-08, released 0.70.0) is a **step discontinuity** in `RCALIBFRAC` across the `daily` archive at the
deployment date, present at all airmass. This is the same shift the DAR fiber-loss study found independently as
its "Finding 1" level change. This is a *known* pipeline change, not a defect; the practical handling is on our side — **use a
uniformly-reprocessed data release (e.g. Matterhorn or Nevis) rather than the `daily` archive**, which removes
the step by construction. (Any cross-time comparison that *does* use `daily` `RCALIBFRAC` must respect this
boundary.)

## 4. The deeper bias: a sky-subtraction dipole in the measured flux

This is the finding that motivated the rewrite, and the reason `RCALIBFRAC` is **not** a clean flux-loss
estimator for *spatial* (DAR) studies. Full evidence, figures, and DAR context are in `DAR_FIBER_LOSS_REPORT.md`
(Parts IV–V); summarized here because it is fundamentally a *measured-flux* property.

**What it is.** Decomposing `RCALIBFRAC`'s per-fiber loss map into multipoles in a zenith-aligned (derotated)
frame yields, besides the real radial and quadrupole terms, a **rotating dipole** `D_rot` — a coherent,
zenith-tied, airmass-growing whole-field gradient, ~2× the quadrupole. It *looks* like a DAR boresight offset.
It is not.

**It is not geometric.** DESI's **dither sequences** (Schlafly et al. 2024, arXiv:2403.05688) measure the
*actual* fiber-to-light offset field by a completely different technique (a geometric centroid fit, not a flux
ratio). Fit with the same decomposition (night-clustered over 12 nights), the real offset field shows **no
rotating dipole** (flat ~0.04″, ~5× below the loss-implied amplitude, slope vs tan z straddling zero) while its
**quadrupole grows and tracks `Q_rot`** on the same data — a built-in positive control. There is no coherent
geometric offset; starlight is not centroiding off the fiber in a zenith-tied way.

**It is in the measured flux, not the model or the aperture correction.** Reconstructing `RCALIBFRAC` from its
ingredients and fitting the dipole separately to the measured-flux and model-flux terms puts **essentially all
of it in the measured flux** (data-term `D_rot` 0.041→0.094 with airmass vs model-term 0.013–0.019, flat). The
aperture correction is excluded twice: the dipole is at full strength in an epoch *before* the correction existed
(0.0341 at am>1.4), and a direct fit to the correction factor is 50–100× too small.

**It enters at `subtract_sky`.** Snapshotting the measured flux at each construction stage (raw extraction →
+fiberflat → +sky subtraction → +aperture correction) and refitting: fiberflat removes the *fixed*
instrument-frame dipole; the **rotating dipole roughly doubles, and gains its airmass growth, specifically at
sky subtraction**; the aperture correction changes nothing after. *(A smaller rotating dipole is already present
in the raw extracted counts — see Limitations — but sky subtraction is where most of the amplitude appears.)*

**Its character — three discriminators** (all on the sky-subtraction-stage flux):
- **Star brightness:** `D_rot` *increases* with brightness, faster than flux — the **opposite** of the ∝1/flux
  scaling a simple additive sky-background residual would give. Rules out the naive additive-residual picture.
- **Sky level:** `D_rot` scales strongly with the pipeline's per-exposure sky brightness (dark sky → consistent
  with zero; bright sky → full amplitude). The effect needs a **real sky background** to act on.
- **Sky-fiber residual:** (data − sky model) measured directly at `OBJTYPE=='SKY'` fibers is **null**
  (~350–800× below `D_rot`, flat). The sky *model* is not spatially wrong; the effect requires the **star's own
  signal** to be present.

**What we ruled out inside `subtract_sky`.** Three named mechanisms each came back null — `_model_variance` ivar
inflation (uses the mean sky, not the fiber's own flux, so cannot couple to star brightness), the sky-line
throughput correction (diluted in the broad band), and — decisively — a **bisector test** that kills the entire
class of inverse-variance-weighting artifacts in one shot (recomputing the flux as an unweighted mean leaves
`D_rot` unchanged). So it is in the flux values themselves, not the weighting.

**It is general to point-source spectrophotometry, not `RCALIBFRAC`-specific.** The strongest generality check
builds the metric a calibration expert would use — **spectrograph counts/s vs external Legacy photometry, over
*all* point sources** (`MORPHTYPE=='PSF'`) — which shares *nothing* with `RCALIBFRAC` except the sky-subtracted
flux (no stellar model, no flux calibration, no standard-star selection; ~470–600k stars). The same dipole (and
quadrupole) survive and grow with airmass, `D_rot/Q_rot ≈ 1.5–1.7`:

| am cut | n point sources | `D_rot` | `Q_rot` | `D_rot/Q_rot` |
|---|---|---|---|---|
| > 1.2 | 596,155 | 0.0515 | 0.0341 | 1.51 |
| > 1.4 | 470,451 | 0.0661 | 0.0396 | 1.67 |
| > 1.8 | 158,170 | 0.1019 | 0.0589 | 1.73 |

So there is **no clean counts-based DAR metric** until the coupling is understood; the geometry (dither, and the
GFA-based metrics) is the only artifact-free route.

**What we did *not* pin (stated plainly).** This is a **strong lead, not a confirmed diagnosis**:
- The stage attribution ("`subtract_sky` specifically" vs an adjacent step such as extraction) rests on an
  external reimplementation validated against production only at the *final* `RCALIBFRAC` value, not at each
  intermediate stage (desispec does not save those). *"It is in the sky-subtracted flux"* is production-validated
  (the point-source metric runs on production flux); *"it enters at `subtract_sky`"* is the lead to verify in the
  real code path.
- **Elimination is not identification.** We ruled out several mechanisms and the ivar-weighting class; the true
  cause could be one we did not test, or in an adjacent step.
- A real (non-bug) alternative — a field-scale sky-brightness gradient the mean-sky model misses — is
  *disfavored* by the sky-fiber null but not formally excluded. Differential atmospheric extinction is a
  legitimate physical candidate but ~10× too small and should appear already in the raw counts.

**Bottom line for this note:** the bias is a real, zenith-tied, airmass-growing property of the sky-subtracted
point-source flux; it contaminates `RCALIBFRAC`'s dipole *entirely* (there is no real DAR dipole) and its
quadrupole *partially* (a real DAR quadrupole, ~11 μm at high airmass, survives at dark sky). No choice of flux
*variable* removes it — it is upstream of the ratio, the normalization, and the aperture correction.

## 5. The candidate variables, and which to use

| variable | construction | what it folds | best for | availability |
|---|---|---|---|---|
| **`RCALIBFRAC`** | measured/model, aperture-corrected (fixed 1.1″), median-normalized | within-exposure *differential* loss; **spatial structure carries the sky-sub dipole** | *instrument-fixed* spatial patterns (per-petal, positioner); **not** DAR/zenith-tied structure | now (calibstars) |
| **`RATIO_RAW`** *(proposed)* | measured/model, **no** aperture correction, **un-normalized** | the true absolute measured-vs-expected, aperture loss included | **level loss-attribution** (dipole averages out); **not** spatial | needs reprocessing |
| **`medval` / `MEDVAL_RAW`** | per-exposure median of the ratio | absolute r-band throughput scalar | absolute throughput per exposure | `medval` computed but **not saved** → reprocessing |
| **flux-cal scale** | r-band normalization of the per-exposure `fluxcalib-*.fits` vector | absolute throughput **after** aperture correction (actual seeing), wavelength-resolved | absolute, science-grade throughput | vector on disk (redux tree); scale **derived — accessor not built** |
| **`EFFTIME_SPEC` / `TSNR2`** | achieved depth | throughput × transparency × sky × time (**conflated**) | exposure quality / depth flag | now (`redux_row`, `petalqa`, `fiberqa`) |
| **`L_see` / `L_field`** | GFA imaging (seeing / intra-exposure guide drift) → acceptance model | seeing loss *level* / DAR field-distortion loss — **artifact-free, dipole-free by construction** | **spatial / DAR structure**; the clean replacement for `RCALIBFRAC`'s spatial use | now (`Exposure`); see `FIBER_LOSS_METRICS.md` |

**What to use when:**

- **Level / loss-attribution** (correlate against seeing, wind, mirror-ΔT, transparency) → **`RATIO_RAW`** *is
  the right variable* — it keeps the aperture-loss signal you want to attribute, and the sky-sub dipole averages
  out over the focal plane (a pattern, monopole-null; *clean for level by averaging, not by being
  artifact-free*). But **it does not exist yet** (§6). Until it is built, the practical options are the
  **flux-cal scale** (absolute, science-grade — derived from the `fluxcalib-*.fits` vectors, accessor not yet
  built) or **focal-plane-averaged `RCALIBFRAC`** (the *differential* level only — median-normalized — and mind
  the §3 epoch step for any cross-time work).
- **Absolute, science-grade throughput** → the **flux-cal scale** — the r-band normalization of the per-exposure
  flux-calibration vector, `$DESI_SPECTRO_REDUX/<release>/exposures/<night>/<expid:08d>/fluxcalib-<cam>-<expid:08d>.fits`
  (actual-seeing correction, wavelength-resolved). The product is on disk in the redux tree, but extracting the
  scalar scale needs a small accessor we have **not built yet** (the `Exposure` module has
  `cframe`/`exposure_qa`/`calibstars` path helpers, no `fluxcalib`).
- **Spatial / DAR structure** → **do not use a flux ratio.** Use **`L_see`** (loss level) and **`L_field`**
  (field-distortion), which are built from GFA imaging and never touch sky-subtracted flux. The dither offset
  field is the only clean flux-independent geometric probe. See `FIBER_LOSS_METRICS.md` and
  `DAR_FIBER_LOSS_REPORT.md`.
- **Depth** → `EFFTIME_SPEC` / `TSNR2` (convenient but conflated — not a clean measured/expected).

**Reconstruction note.** With `RCALIBFRAC` and `medval` you recover the absolute per-fiber ratio
(`RCALIBFRAC × medval`), but still the *aperture-corrected* (fixed-1.1″) value. The *raw* per-fiber map
additionally needs dividing out `psf_correction_i` (recomputable from `FIBER_X/Y`, `DELTA_X/Y`) — i.e. the
reprocessing path, which produces `RATIO_RAW` directly. None of these operations removes the sky-sub dipole
(§4).

## 6. The clean fix for the level-attribution variable: enriched reprocessing

The *discontinuity* is best sidestepped simply by working from a **uniformly-reprocessed release** (e.g.
Matterhorn or Nevis) rather than the `daily` archive (§3) — no reprocessing needed. What a release still does
*not* provide is an **absolute, un-normalized** variable (its `RCALIBFRAC` is still median-normalized and
aperture-corrected). If that becomes necessary for the telemetry work, the option is to **reprocess `calibstars`
ourselves against a frozen release and save more information**. Proposed enriched table:

| column | meaning |
|---|---|
| `RATIO_RAW` | measured/model, no aperture correction, un-normalized — the raw absolute per-fiber "truth" |
| `RCALIBFRAC` | current definition — continuity |
| `MEDVAL_RAW`, `MEDVAL_CORR` | per-exposure medians — `MEDVAL_RAW` is the absolute throughput; `MEDVAL_CORR` is the normalization constant (the two differ because the correction shifts the median) |
| `N_STARS`, `MEDVAL_RMS` | stars entering each median and its scatter — weight/quality-cut without reopening per-fiber data |
| `PSF_CORRECTION` | per-fiber correction factor — move freely between raw ↔ corrected |
| `FIBER_X/Y`, `DELTA_X/Y` | correction inputs, and the positioning offset (a regressor in its own right) |
| `SEEING`, `MODELRFLUX`, `EBV`, colors, `VALID` | context |

Save both `MEDVAL`s explicitly (not recomputed): `medval` is the median over the pipeline's `RCALIBFRAC > 0` set
*before* the `VALID` cut, so a later `RATIO_RAW.median()` over a differently-filtered set would not reproduce the
exact normalization constant. Saving the scalar pins it and hands you the absolute per-exposure throughput with
no per-fiber groupby.

> **Status:** this enriched table **has not been built** — it remains a recommendation. The one-off reprocessing
> done for the sky-subtraction investigation (the stage-by-stage flux-chain decomposition and the
> point-source-photometry metric on production flux; see `DAR_FIBER_LOSS_REPORT.md`, Appendix B) established the
> *finding* but did not produce a reusable `RATIO_RAW`/`MEDVAL` `calibstars` product. So there is currently **no
> clean, time-consistent, absolute measured-vs-expected variable in hand** for level-attribution studies —
> building it is the concrete Data-Systems ask (§7, item 2).

## 7. For the `desispec` team

**The one thing to hand over — the sky-subtraction point-source dipole.** A zenith-tied, airmass-growing bias
enters point-source spectrophotometry at sky subtraction — inherited by `RCALIBFRAC`, by a direct
counts-vs-photometry metric, and by anything built on sky-subtracted point-source flux (the standard
photometry-comparison metric is **not** an escape from it). It is a real bias in a pipeline product, and
identifying the mechanism is a `desispec` question we cannot settle from outside. The concrete facts as a
starting point:
- Real, zenith-tied, airmass-growing bias in the r-band flux, scaling **super-linearly** with star brightness
  (neither simple additive nor simple multiplicative), entering at `subtract_sky` (present after, absent/smaller
  before, unchanged by the aperture correction after).
- Requires the **star's own flux** to be present (null at pure sky fibers) and scales with **both** star
  brightness and overall sky brightness.
- **Not** produced by `_model_variance` ivar inflation, the sky-line throughput correction, or ivar-weighting of
  the reduction in general.
- The **exact algorithmic step is the open piece**; the `subtract_sky`-vs-adjacent-step attribution should be
  verified in the real code path (it rests on our external reimplementation). Bright-vs-faint and sky-level
  splits are the signature to reproduce internally.

**Not a request — a note on `RCALIBFRAC` continuity.** For completeness, and explicitly *not* an ask on the
team: the mid-2025 flat→psf aperture correction (PR #2484) is a **well-known** step in `RCALIBFRAC` across the
`daily` archive, and the median normalization discards absolute throughput. Both are handled on *our* side — for
telemetry / level work we work from a **uniformly-reprocessed release** (e.g. Matterhorn or Nevis) rather than
the `daily` archive, which removes the discontinuity by construction, and if a truly absolute variable is ever
needed we can reprocess `calibstars` against a frozen release ourselves to save the enriched table (§6). No
pipeline change is being requested for this.

## 8. This is the research program, not a caveat

Flux loss is a **sum of correlated terms** — wind, seeing, transparency, mirror temperature, positioning, and
more — and the goal is to find the dominant ones. That drives the variable design: the **raw** absolute
throughput (`RATIO_RAW`) is the right dependent variable for level attribution *because* it keeps the
seeing/positioning aperture-loss terms; **airmass extinction** is the one cleanly-modelable term (keep as a known
regressor or divide out); the rest become candidate predictors, most already surfaced by the Exposure module
(telemetry fields, `gfa_row` seeing/transparency, the mirror-temperature and windshake analyses). For the
*spatial* face of the loss, the flux ratios are contaminated by the sky-subtraction bias, and the GFA-based
`L_see`/`L_field` are the artifact-free instruments.

---

## Appendix — source references

**Pipeline construction:**
- `desispec/scripts/select_calib_stars.py` — `RCALIBFRAC` (aperture correction line 131–132; `medval` line 168;
  normalization line 173; `VALID` cut).
- `desispec/fiberfluxcorr.py` — `flat_to_psf_flux_correction` / `psf_to_fiber_flux_correction`.
- `desispec/fluxcalibration.py` — flux-cal vector `= C_fiber / FLAT_TO_PSF_FLUX` (actual-seeing correction).
- `desispec/tsnr.py` — `TSNR2`/`EFFTIME` also apply the correction.
- desispec **PR #2484** "add psf correction to RCALIBFRAC" (merged 2025-05-08, released 0.70.0).

**Sky-subtraction investigation** (full detail, figures, and DAR framing in `DAR_FIBER_LOSS_REPORT.md`, Parts
IV–V and Appendix B):
- `analysis/dar_dipole/fit_dipole_quadrupole.py`, `affine_fit_lib.py` — the multipole decomposition.
- `dither_offset_field_test.py` — the geometric (dither) null; `rebuild_rcalibfrac.py` — model-vs-data split;
  `flat_to_psf_dipole_test.py` — aperture-correction exclusion; `flux_chain_decomposition.py` — the stage
  localization; `sky_residual_test.py`, `variance_inflation_test.py`, `throughput_correction_test.py`,
  `unweighted_reduction_test.py` — the §4 discriminators and `subtract_sky` mechanism tests; the point-source
  metric is the same decomposition on `log(counts/s) − log(FLUX_R)` for all `MORPHTYPE=='PSF'` fibers.
