# Measuring Flux Loss with Standard Stars: Which "Measured-vs-Expected" Variable to Use, and Why

**Status:** draft for review by the Data Systems / calibration team (J. Guy). Part of the
`telemetry_mining` / Exposure-module documentation family (companion to `API.md`, `FIELDS.md`).

K. Honscheid (OSU) with Claude (Anthropic) · 2026-07-24

> Purpose: for telemetry / observing-conditions studies we want a variable that says
> **"this is what we measured, this is what we should have measured"** — a flux-loss / throughput
> diagnostic — so we can correlate it against wind, seeing, transparency, mirror temperature,
> positioning, etc. Standard stars are the only clean "known truth" for this. This note pins down
> exactly how the candidate variables are built (from reading the `desispec` source: `select_calib_stars.py`,
> `fiberfluxcorr.py`, `fluxcalibration.py`, `tsnr.py`), what correction each one carries, and which to
> use for what. It also records a pipeline change that quietly altered `RCALIBFRAC` in mid-2025.

---

## 1. The known truth: standard stars

A standard star has a **model SED** (`MODELRFLUX` etc.), obtained by fitting a stellar template to
the star's broadband photometry (imaging / Gaia). That model is "what we should have measured" (above
the atmosphere). The **measured** flux is what actually reaches the detector through the fiber. Their
ratio is the end-to-end system throughput — atmosphere (extinction + transparency) × telescope ×
instrument × **fiber aperture loss**. Standard stars are the only per-exposure, on-sky, absolute
reference we have, so every "measured-vs-expected" variable below is anchored on them. (Caveat: the
"truth" is only as good as the template/photometry calibration — it is the best available reference,
not a perfect absolute.)

## 2. How `RCALIBFRAC` is built — two layers to know

From `desispec/scripts/select_calib_stars.py`, per exposure:

1. Read the r-camera frames, apply fiberflat, subtract sky.
2. **Apply a point-source (flat→psf) aperture correction** to the flux (line 131–132):
   `flux *= flat_to_psf_flux_correction(fibermap, exposure_seeing_fwhm=1.1, normalize=False)` — see §3.
3. `ratio = rflux / MODELRFLUX` per star (measured / model, summed over 6000–7300 Å).
4. `medval = median(ratio)` over the exposure's stars (line 168) — **the absolute throughput** …
5. … then `RCALIBFRAC = ratio / medval` (line 173) — **`medval` is divided out and not saved.**
6. `VALID` flags 3σ `RCALIBFRAC` outliers and G−R color mismatches.

**Layer 0 — median normalization.** Because step 5 forces each exposure's *median* `RCALIBFRAC` to 1,
`RCALIBFRAC` carries only **within-exposure, fiber-to-fiber variation** — it is blind to the exposure's
absolute throughput (anything that dims all fibers together is normalized away). A per-exposure "mean
loss = 1 − mean(RCALIBFRAC)" therefore measures the *downward skew* of the distribution, i.e. the
*differential* loss, not the absolute one.

**Layer 1 — the aperture correction** (step 2, added mid-2025). `RCALIBFRAC` now measures the residual
*after* the pipeline's modeled static aperture loss has been divided out (§3–4).

## 3. The flat→psf aperture correction (`fiberfluxcorr.flat_to_psf_flux_correction`)

Per fiber it computes the captured point-source light fraction and divides the flux by it:

- inputs: **`FIBER_X/FIBER_Y`** → radial plate scale; **`DELTA_X/DELTA_Y`** → the fiber-to-target
  positioning offset; and a **seeing FWHM** → PSF size `σ`.
- `fiber_frac = FastFiberAcceptance("POINT", σ, offset)` — captured fraction (drops with seeing and
  with offset).
- correction `= 1 / fiber_frac / platescale²` (sky fibers set to 1).

So the corrected flux ≈ `F_true · fiber_frac_actual / fiber_frac_model`, and after the ratio/median
step `RCALIBFRAC` retains the **residual** `fiber_frac_actual / fiber_frac_model` — i.e. only what the
model gets *wrong* or can't see:

- **seeing ≠ the assumed value** (see §4 — calibstars assumes a fixed 1.1″);
- **intra-exposure / dynamic effects** — `DELTA_X/Y` is a single online-system snapshot, so wind
  jitter *during* the exposure, tracking, and **DAR drift** are not in it and survive;
- **optics / coordinate-model error** — `DELTA_X/Y` equals the true offset only if the transform is
  right; where it is wrong, the mismatch survives (so `RCALIBFRAC` is partly a probe of *where the
  optics model is wrong*);
- a purely **radial** reshaping via the `1/platescale²` term.

What it *removes* is the aperture loss that is well-modeled by (position, static offset, assumed seeing).

## 4. The same correction lives in three products — with different seeing

`flat_to_psf_flux_correction` is applied in **three** places, so the mid-2025 change touched all the
throughput products, not just calibstars:

| product | file | seeing used | notes |
|---|---|---|---|
| **`RCALIBFRAC`** (calibstars QA) | `select_calib_stars.py` | **hardcoded 1.1″** | `normalize=False`; then median-normalized |
| **flux-cal vector** (science flux) | `fluxcalibration.py` | **actual/estimated exposure seeing** (parameter) | docstring: calibration vector `= C_fiber / FLAT_TO_PSF_FLUX`; wavelength-resolved, template-fit |
| **`TSNR2` → `EFFTIME`** | `tsnr.py` | (as used there) | folds the same correction |

The distinction matters: the science flux calibration uses the **actual** seeing (a more correct
aperture correction), while the calibstars QA uses a **fixed 1.1″** (a cruder version whose residual
still carries a seeing-vs-1.1″ signal).

## 5. The candidate "truth" variables

| variable | construction | what it folds | best for | availability |
|---|---|---|---|---|
| **`RCALIBFRAC`** | measured/model, **median-normalized**, aperture-corrected (fixed 1.1″) | within-exposure *differential* loss (residual after static aperture model) | spatial patterns across the focal plane (DAR dipoles, per-petal, positioner comparisons) | now (calibstars) |
| **`RATIO_RAW`** *(proposed)* | measured/model, **no** aperture correction, **un-normalized** | *everything* — the true absolute measured-vs-expected, aperture loss included | **loss-attribution studies** (keeps the seeing/positioning signal) | needs reprocessing |
| **`medval`** | per-exposure median of the (corrected) ratio | absolute throughput at std-star positions, r-band scalar | absolute throughput per exposure; renormalizing `RCALIBFRAC` | computed but **not saved** → reprocessing |
| **flux-cal scale** | normalization of the `calib-*.fits` vector | absolute throughput **after** aperture correction (actual seeing) | absolute, science-grade, wavelength-resolved | **on disk now** (redux tree) |
| **`EFFTIME_SPEC` / `TSNR2`** | achieved depth | throughput × transparency × sky × time (**conflated**) | exposure quality / depth flag — *not* a clean measured/expected | now (`redux_row`, `petalqa`, `fiberqa_table`) |

## 6. What to use when

- **Absolute throughput *including* aperture loss (for loss attribution)** → `RATIO_RAW` (aperture
  loss is the signal you want; the pipeline's correction removes it — right for science flux, wrong
  for this program). **No current product provides this**; it requires reprocessing with the
  correction disabled.
- **Absolute throughput *after* aperture correction (science-grade)** → the **flux-cal scale**,
  available now, actual-seeing correction, wavelength-resolved. Better than `medval` for this.
- **Within-exposure spatial structure** (DAR, petals, linphi vs regular) → `RCALIBFRAC` as-is — but
  respect the mid-2025 discontinuity for any cross-time comparison.
- **Depth / "was this a good exposure"** → `EFFTIME_SPEC` / `TSNR2` (convenient but conflated).

**Reconstruction note.** With `RCALIBFRAC` and `medval` you recover the absolute per-fiber ratio
(`RCALIBFRAC × medval`), but it is still the *aperture-corrected* (fixed-1.1″) value. The *raw*
per-fiber map additionally needs dividing out `psf_correction_i` (recomputable from `FIBER_X/Y`,
`DELTA_X/Y`) — i.e. the reprocessing path, which produces `RATIO_RAW` directly.

## 7. The problem: `RCALIBFRAC` changed, and `daily` is not reprocessed

Data releases are reprocessed uniformly; **`daily` is not** — each night is processed once with the
then-current code. So the mid-2025 addition of the aperture correction (PR #2484, released 0.70.0)
is a **step discontinuity** in `RCALIBFRAC` across the `daily` archive at the deployment date, present
at all airmass. (This is the same shift found independently in the DAR fiber-loss study; see
`DAR_FIBER_LOSS_REPORT.md`.) Any variable derived from the pipeline can carry such changes.

## 8. Conclusion and plan

The clean fix is to **reprocess calibstars ourselves with a frozen `desispec` version and save more
information**, giving both a time-consistent variable and every option above. Proposed enriched table:

| column | meaning |
|---|---|
| `RATIO_RAW` | measured/model, no aperture correction, un-normalized — the raw absolute per-fiber "truth" |
| `RCALIBFRAC` | current definition (aperture-corrected, median-normalized) — continuity |
| `MEDVAL_RAW`, `MEDVAL_CORR` | per-exposure median scalars — **`MEDVAL_RAW` is the absolute "measured vs. expected" throughput**; `MEDVAL_CORR` is the constant that normalized `RCALIBFRAC` (the two differ because the correction shifts the median) |
| `N_STARS`, `MEDVAL_RMS` | stars entering each median, and its scatter — to weight / quality-cut the per-exposure throughput without reopening the per-fiber data |
| `PSF_CORRECTION` | per-fiber correction factor — move freely between raw ↔ corrected |
| `FIBER_X/Y`, `DELTA_X/Y` | correction inputs, and the positioning offset (a regressor in its own right) |
| `SEEING`, `MODELRFLUX`, `EBV`, colors, `VALID` | context |

The two `MEDVAL`s are saved explicitly rather than recomputed on demand, for a subtle reason beyond
convenience: `medval` is the median over the pipeline's `RCALIBFRAC > 0` set **before** the `VALID`
cut (`select_calib_stars` lines 160–168), so a later `RATIO_RAW.median()` over a differently-filtered
set would *not* reproduce the exact normalization constant. Saving the scalar pins it unambiguously —
and hands you the absolute per-exposure throughput ready to use, with no per-fiber groupby.

Steps (NERSC-time): **(a)** a cheap **verification test** — reprocess an epoch-A and epoch-B sample
with the correction *off*; if the A→B jump vanishes, the aperture correction is the whole story and
our reprocessing cures it (if it persists, there is also an upstream extraction/PSF change that
reprocessing calibstars alone won't fix). **(b)** Full enriched reprocessing as above. **(c)** Add a
**flux-cal-scale accessor** to the Exposure module (deferred until NERSC access, so it can be tested
against real `calib-*.fits`).

## 9. This is the research program, not a caveat

Flux loss is a **sum of correlated terms** — wind, seeing, transparency, mirror temperature,
positioning, and more. The goal of the coming studies is to find the correlations and the **dominant
terms**. That decides the variable design: the **raw** absolute throughput (`RATIO_RAW`) is the right
dependent variable *because* it keeps the seeing/positioning aperture-loss terms we want to attribute;
**airmass extinction** is the one cleanly-modelable term (keep as a known regressor or divide out); and
the rest become candidate predictors, most already surfaced by the Exposure module (telemetry fields,
`gfa_row` seeing/transparency, the mirror-temperature and windshake analyses).

---

## Appendix — source references

- `desispec/scripts/select_calib_stars.py` — `RCALIBFRAC` construction (aperture correction line
  131–132; `medval` line 168; normalization line 173; `VALID` cut).
- `desispec/fiberfluxcorr.py` — `flat_to_psf_flux_correction` / `psf_to_fiber_flux_correction`.
- `desispec/fluxcalibration.py` — flux-cal vector `= C_fiber / FLAT_TO_PSF_FLUX` (actual-seeing
  correction).
- `desispec/tsnr.py` — `TSNR2`/`EFFTIME` also apply the correction.
- desispec **PR #2484** "add psf correction to RCALIBFRAC" (merged 2025-05-08, released 0.70.0).
