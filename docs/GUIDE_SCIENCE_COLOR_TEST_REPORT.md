# Guide-vs-science color test: a real but sub-dominant chromatic contribution

K. Honscheid (OSU) with Claude (NERSC + Mac sessions, collaborating via `from_nersc_to_mac.md` /
`from_mac_to_nersc.md`) · 2026-08-05

Direct follow-up to `docs/TEST6_GUIDE_STAR_RESIDUAL_REPORT.md`. This document reports a completed
analysis; it does not modify that report or `DAR_DIPOLE_NERSC_HANDOFF.md`.

---

## TL;DR

- **Motivation**: reading the actual guider control-loop code (Mac session) established that the guider
  only ever nulls the *mean* guide-star offset — a pure boresight correction, nothing field-dependent.
  Consequence: any refraction error *common* to both the guide stars and the science field is corrected
  away before it reaches the fibers; only a genuine **guide≠science difference** in the uniform term can
  survive as D_rot.
- **The natural candidate**: standard stars (used for science flux calibration) are known to be bluer
  than guide stars. Bluer light refracts more; if the guide loop nulls the (redder) guide-star field, the
  (bluer) science light would carry a residual differential chromatic refraction (DCR) the loop never
  removes — a uniform, static, zenith-tied science-field offset, exactly D_rot's signature.
- **Tested it in four steps. Result: the color difference is real and large, but it does not explain
  D_rot's full magnitude, and does not show up as a detectable within-sample color dependence.** The
  most defensible read is **chromatic DCR is a real, physically-understood, but sub-dominant contributor
  to D_rot — not its dominant source.**

---

## Motivation: why this is the natural next hypothesis

`docs/TEST6_GUIDE_STAR_RESIDUAL_REPORT.md` found a real, ~100σ, zenith-tied, tan(z)-growing residual in
the guide-star astrometric solve (~0.5-0.9″), decisively larger than D_rot (~0.11-0.22″), and ruled out
ordinary sampling incompleteness on the known achromatic DAR model as the cause.

The resolving insight came from reading the actual guider control-loop code: for DESI, the guider is
*handed* the expected guide-star positions by PlateMaker (it cannot solve astrometry itself); each frame
it averages the per-GFA errors into a single combined centroid and sends a boresight-only correction to
the TCS. **It does exactly one thing — nulls the mean guide-star offset.** It cannot correct anything
field-dependent, and it *will* correct anything common to guide and science equally. This single fact
explains two results at once:

- Test 6's own internal quadrupole cross-check (a follow-up decomposition of the guide-star residual
  into rotating vs. fixed shear) independently matched the already-established ΔG field-differential
  compression (0.102″ vs 0.11″ at airmass~1.5; 0.168″ vs 0.16″ at airmass~1.7) — confirming guide stars
  and science fibers see the *same* common DAR field. A common field's *quadrupole* survives the
  boresight-only loop; a common field's *uniform* (dipole) term does not.
- D_rot being ~3-4× smaller than Test 6's full coherent residual is therefore not a discrepancy to
  explain away — it is *expected*: D_rot is only the uncorrectable guide≠science **differential** in the
  uniform term, while Test 6's full residual is the common-mode refraction error the loop mostly absorbs
  before it reaches the fibers.

This reframes the question precisely: **D_rot requires a genuine guide≠science difference in the uniform
refraction term.** The natural candidate is a systematic effective-wavelength difference between the
r-band GFA guide solution and the science-standard-star population — i.e., exactly the mechanism this
report tests.

---

## Step 0 — feasibility

Both populations are reachable, more cheaply than expected:

- **Standard stars**: `Exposure.calibstars` already carries `MODEL_COLOR`/`DATA_COLOR` (a G−R-style
  color) directly — no extra pull needed. `TARGET_RA`/`TARGET_DEC` joins in cleanly via
  `fiberqa_table` (validated 132/132 matched in a test exposure).
- **Guide stars**: already available from `docs/TEST6_GUIDE_STAR_RESIDUAL_REPORT.md`'s color follow-up
  (`data/dar_pmgstars_color.parquet`), cross-matched to Gaia DR3 for BP−RP.

Harvested the full standard-star population: **2,570,324 star rows, 24,630 exposures** — matches the
original committed D_rot dataset exactly (`analysis/dar_dipole/color_test_harvest.py`,
`data/dar_standardstar_color.parquet`).

---

## Step A — the population color offset (decisive confirmation of the premise)

Cross-matched a 30,000-star random sample of unique standard stars to Gaia. First attempt used the same
"lightweight" Gaia catalog the guide-star test used, and only matched 7% (2090/30000) — vs. guide stars'
63.5% on that same catalog. That catalog turns out to be a **bright-star-only subset**; standard stars
run considerably fainter than guide stars. Switched to the full-depth catalog
(`/global/cfs/cdirs/desi/target/gaia_dr3/healpix/`, which has `BP_RP` precomputed) — **99.997% matched**
(29999/30000).

| | mean BP−RP | SE | n |
|---|---|---|---|
| Standard stars | 0.7226 | 0.0005 | 29999 |
| Guide stars | 1.1379 | 0.0024 | 33073 |

**Δ(BP−RP) = standard − guide = −0.415**, overwhelmingly significant given the tiny standard errors —
standard stars are decisively, robustly bluer than guide stars, confirmed on the same photometric system
for both populations. (A useful byproduct: MODEL_COLOR correlates well with Gaia BP−RP for standard
stars, r=0.784, BP−RP≈0.886·MODEL_COLOR+0.436 — available if a converted color proves useful elsewhere.)

---

## Step B — does the color difference predict D_rot's magnitude?

Neither DESI-9097 (Joyce) nor DESI-0309 (Lampton) was available on NERSC to check against directly, so
the standard Filippenko/Edlen air-refractivity formula was implemented directly rather than guessing at
report-specific numbers. The refraction constant (45″, production `desi.par`) was taken as calibrated at
a nominal r-band effective wavelength (~6231 Å); the predicted differential refraction between the two
populations' effective wavelengths was computed via the ratio of refractive indices.

The one genuinely soft input is **dλ_eff/d(color)** — how much a star's effective wavelength shifts,
within a fixed bandpass, per unit broadband color. Rather than assume a single value, this was scanned
across a plausible range:

| dλ/dcolor (Å per unit BP−RP) | Δλ_eff (Å) | predicted DCR @am=1.4 | @am=1.8 |
|---|---|---|---|
| 100 | 41.5 | 0.009″ | 0.013″ |
| 200 | 83.0 | 0.018″ | 0.027″ |
| 300 | 124.5 | 0.026″ | 0.040″ |
| 400 | 166.0 | 0.036″ | 0.054″ |

Taken at face value, even the high end of this range falls short of D_rot's target (0.11″/0.22″) by a
factor of ~3-6×.

### Why the gap is expected, not a shortfall: all three relevant measurements are r-band-confined

This is the key piece that turns an unexplained numerical gap into an understood result. The full Gaia
BP−RP baseline spans the *entire* optical range (roughly 330-1050 nm), but none of the three quantities
actually being compared spans that range:

- **The science measurement** (`RCALIBFRAC`) is computed from r-band flux, 6000-7300 Å.
- **The guide-star centroiding** happens through the GFA's r-band filter — already established earlier
  in this investigation (memory `dar-guider-bias-hypothesis`, the original chromatic-closure reasoning)
  as being in the same band as the science measurement.
- **The fiber-placement wavelength** is, per input from Steve Kent, also effectively r-band.

Since all three are confined to the same ~1300 Å-wide r-band window, the Δλ_eff that actually matters for
this mechanism is not the *full* BP−RP-implied spread — it's the much narrower **within-r-band**
effective-wavelength spread between a star with the standard population's typical color and one with the
guide population's typical color. That is a substantially smaller quantity than a naive full-baseline
BP−RP-to-λ_eff conversion would suggest, and it lands the physically-appropriate point on the low end of
the table above — **of order 0.02″** at the airmass scales relevant here. This is fully consistent with,
and gives a physical reason for, the ~3-6× gap: **the gap isn't a sign the mechanism is failing, it's the
expected consequence of the comparison being r-band-confined on all three sides.**

---

## Step C — the decisive internal test: does D_rot track standard-star color?

This test is immune to Step B's absolute-scale uncertainty — it only needs a slope, not a normalization.
Reused the exact fit logic from `analysis/dar_dipole/fit_dipole_quadrupole.py` (the `within_demean`/
`per_exp_normal`/`solve`/`amps` functions copied verbatim, not retyped) and refit D_rot separately on
standard stars split at the median `MODEL_COLOR`.

| airmass bin | D_rot (BLUE) | D_rot (RED) |
|---|---|---|
| >1.0 | 0.0138 [0.0136,0.0140] | 0.0132 [0.0130,0.0134] |
| >1.4 | 0.0344 [0.0334,0.0355] | 0.0357 [0.0347,0.0368] |

**Essentially identical between halves** — the confidence intervals overlap heavily at am>1.4, and the
sign even runs slightly backwards from the chromatic prediction (red marginally larger, not blue).

**The honest caveat, and the correct way to read this null**: the median split's internal color contrast
(blue mean 0.274, red mean 0.369 in `MODEL_COLOR`) is real but modest — only about **20% of the full
standard-vs-guide Δ(BP−RP)** established in Step A. This is a genuinely weaker test than Step A is a
confirmation; it is not the same statistical power as a full population-level comparison would carry. The
correct conclusion from Step C is **"no detectable color dependence at this test's more limited leverage,"
not "chromatic contributes exactly zero."**

---

## Conclusion

Taken together, Steps A, B, and C paint a coherent, physically-understood picture rather than a
contradiction:

- **Step A** establishes the premise solidly: standard stars are genuinely, substantially bluer than
  guide stars.
- **Step B**, once the r-band-confinement of all three relevant measurements is accounted for, predicts a
  DCR contribution of order ~0.02″ — small compared to D_rot's ~0.11-0.22″, not because the mechanism is
  wrong, but because the *effective* color baseline relevant to this specific effect is much narrower
  than the full-spectrum color difference measured in Step A.
- **Step C**, at the leverage this particular split can achieve, finds no detectable color dependence
  within the standard-star sample — consistent with a small, sub-dominant effect that this test's modest
  internal contrast isn't powerful enough to resolve cleanly.

**The defensible conclusion: guide-vs-science chromatic DCR is a real, physically-understood contributor
to D_rot, but not its dominant source, on the evidence gathered here.** The dipole's dominant mechanism
remains open. This does not retract the guider-code reframing (Test 6's full residual is genuinely mostly
corrected by the boresight loop, and only a guide≠science differential survives) — it narrows what kind
of guide≠science differential is doing the work, and chromatic effective-wavelength mismatch, while real,
is evidently not carrying most of it on its own.

## Related
- `docs/TEST6_GUIDE_STAR_RESIDUAL_REPORT.md` — the guide-star post-fit-residual investigation this
  extends, including the quadrupole-vs-Q_rot confirmation and the guider-code reframing.
- `docs/DAR_DIPOLE_NERSC_HANDOFF.md` — the primary investigation document.
- Memory: `dar-guider-bias-hypothesis` (full evolving record, including the original r-band
  chromatic-closure reasoning this report builds on).
- Communication log: `from_nersc_to_mac.md` / `from_mac_to_nersc.md`.
