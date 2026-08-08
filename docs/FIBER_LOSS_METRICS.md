# Recommended DESI Fiber-Loss Metrics and Their Scope

K. Honscheid (OSU) with Claude (Anthropic) · 2026-08-06 (Exposure API added 2026-08-07)

Companion note to `DAR_FIBER_LOSS_REPORT.md`. That report established
that `RCALIBFRAC` — the standard-star measured/model flux ratio — is
**not** a clean fiber-loss estimator: its sky-subtraction step imprints
a spurious, zenith-tied dipole that is general to point-source
spectrophotometry, not specific to the metric. This note records the
practical consequence: **which quantities *are* clean, what each can and
cannot see, and how to build a normalized per-exposure metric from the
guide cameras that behaves conceptually like** `RCALIBFRAC` **without
inheriting the artifact.**

## 0. Primer — what these metrics are, in plain terms

*(A plain-language on-ramp; the detailed construction and scope follow
in §1–§3.)*

**The principle: measure the guide-camera images, not the flux.** The
sky-subtraction artifact lives in the sky-subtracted spectroscopic
*flux*, so any flux ratio inherits it. The escape is to use what the
guide cameras (GFAs) photograph — guide-star *images* — which never
touch sky-subtracted spectra. The GFAs give two kinds of imaging
measurement, and both are artifact-free: **how big** the star images are
(the PSF width, i.e. seeing) and **where** they are (centroids, and how
they drift across the field). “Geometry” is shorthand for “guide-camera
imaging” — and image *size* counts just as much as image *position*.

**Two physical ways a fiber loses light.** A star’s light misses the
fiber for two independent reasons, both captured by the `desimodel`
fiber-acceptance function `A(σ, δ)` — the fraction of a point source’s
light that couples into the fiber given PSF size σ and star-to-fiber
offset δ:

- **Fat PSF** (σ, seeing): even a perfectly centred star spills light
  past the fiber edge if the seeing disk is larger than the fiber. This
  is a whole-array effect (seeing is ~uniform across the field) →
  **Metric A =** `L_see`.
- **Off-centre star** (δ, offset): a displaced star loses more light.
  The offset is *not* uniform — DAR bends the field, so the edge sees a
  different offset than the centre. This is a spatial pattern → **Metric
  B =** `L_field`.

The two are named for use as `L_see` (the whole-array loss *level* set
by seeing) and `L_field` (the loss that *varies across the focal-plane
field*). Both are losses (`L_`); the suffix names what drives them.
`L_field` is left deliberately general — it is sensitive to any
low-order field distortion, DAR being the dominant one but not the only
possible one (e.g. a rotator or hexapod anomaly).

**Why Metric B is “scale + shear.”** The field-varying offset is written
`δ(r) = G·r`, with `G` a small 2×2 map measured from how the guide stars
drift across the field during the exposure. Any such map splits into
translation + rotation + scale + shear. Translation is removed by the
guide loop and rotation by the hexapod, so neither reaches the fibers;
what remains is **scale** (isotropic expand/shrink) and **shear**
(stretch one axis, squeeze the perpendicular). DAR compresses the field
along the zenith — a 1-D squeeze — which is exactly scale + shear
together. Both are needed: shear alone yields a perfectly circular
(radial) loss, and only the scale×shear cross-term produces the
zenith-tied two-lobed (quadrupole) pattern that real DAR makes.

**What goes in, and from where** (data sources verified in the build
scripts):

| metric | what it captures | shape | GFA quantity | data source |
|----|----|----|----|----|
| **A —** `L_see` | seeing / aperture loss (the *level*) | scalar per exposure | PSF width (seeing FWHM) | **offline GFA reconstruction** (`FWHM_ASEC` from the GFA summary) — the gold-standard seeing |
| **B —** `L_field` (scale+shear) | DAR offset *pattern* | per-fiber map | guide-star drift across the field | **ETC** per-frame JSON (`thru/dx_gfa,dy_gfa`) |

Both are guide-camera imaging; neither uses sky-subtracted flux — which
is what carries the artifact. The two draw on different reductions of
the same guide data, chosen fit-for-purpose rather than as a quality
compromise. Seeing exists in three reductions of increasing quality —
real-time GFA, processed ETC, and the **offline reconstruction (the gold
standard)** — and Metric A, which needs only one seeing value per
exposure, uses the offline reconstruction (`FWHM_ASEC`). Metric B
instead needs the *per-frame* guide-star-offset time series to measure
intra-exposure drift; the ETC per-frame JSON (`thru/dx_gfa,dy_gfa`)
provides that directly, whereas the offline reconstruction we have is a
per-exposure summary and carries no intra-exposure information.

## 1. The principle: measure the geometry, not a flux ratio

The sky-subtraction artifact lives in the sky-subtracted spectroscopic
flux, so *any* flux-ratio built on it (RCALIBFRAC,
counts/s-vs-photometry, self-calibration) inherits it. The escape is to
use **geometric / imaging** measurements — positions and PSF sizes from
the guide cameras (GFAs) and the dither technique — which never touch
sky-subtracted spectroscopic flux. A guide-star centroid or a PSF FWHM
is immune to a bias that scales the *flux level*; that is why the dither
offset field and the guide-star residuals both showed the real DAR
quadrupole and **no** dipole, while every flux metric showed the dipole.

## 2. The three clean probes and their scope

| probe | what it measures | cadence | scope | good for | blind to |
|----|----|----|----|----|----|
| **Dither offset field** | true per-fiber fiber-to-light offset (peak of flux-vs-commanded-position) | sparse (special sequences, ~12 nights in our sample) | **complete** per-fiber field | ground truth; calibrating the others; any pattern search | routine per-exposure monitoring |
| **GFA guide-star residuals** (position) | affine offset field from ≤2 stars × 6 edge GFAs | every exposure | **field-differential affine** (rotation/scale/shear → through the quadrupole; the raw translation `t` is guide-loop-corrected, *not* delivered — see §3.1) | the low-order DAR pattern (`G·r`) | per-fiber / high-order structure; whole-array *shift* (needs delivered-offset telemetry, not raw `t`) |
| **GFA transparency /** `FRACFLUX` **/ seeing** (throughput/PSF) | atmospheric transparency and the point-source fiber fraction from the GFA PSF | every exposure | global (edge-sampled seeing ≈ field seeing) | whole-array *throughput* influences (dome seeing, transparency) | field-dependent structure |

Two mechanism classes to keep straight: **position/shift** effects
(temperature, wind, pointing) move the centroid and register on the
*residual* channel; **size/throughput** effects (dome seeing,
transparency) change coupling *without* moving the centroid and register
on the *FRACFLUX/seeing* channel. A pure offset metric is largely blind
to a symmetric PSF broadening, so the two channels are complementary,
not redundant.

**The scope wall is at *affine*, not at “global.”** Six edge GFAs pin
down a translation plus rotation/scale/shear — the shear *is* the
low-order field-differential term, which is exactly why the guide-star
residuals reproduced `Q_rot`. What the edge sampling cannot resolve is
anything beyond affine: per-fiber positioner error, per-petal patterns,
high-order multipoles. **Field-dependent pattern searches therefore
remain dither-limited** until the `subtract_sky` coupling is fixed
(which would make a clean *per-fiber* flux metric possible).

## 3. A GFA fiber-loss metric — the `RCALIBFRAC` analog

Both `RCALIBFRAC` and this metric estimate the same physical quantity:
the aperture-coupling loss, the fraction of a point source’s light that
misses the fiber, a deterministic function of the PSF size σ and the
star-to-fiber offset δ through the fiber-acceptance function `A(σ, δ)`
(`desimodel` `FastFiberAcceptance`, “POINT”). `RCALIBFRAC` estimates it
empirically from the spectra (and inherits the artifact); this metric
**predicts** it from imaging-measured σ and δ (artifact-free). It has
two pieces with different inputs and scopes.

### What the metric produces, per exposure — three things kept separate

It outputs **two** artifact-free quantities; a **third** item that keeps
getting folded in is a *validation*, not an output. Keep them distinct:

| \# | name | what it is | shape | driven by | use |
|----|----|----|----|----|----|
| **A** | `L_see` — seeing level, `1 − A(σ,0)/A_ref` | acceptance loss at perfect centering (δ=0) | **scalar** per exposure | GFA seeing σ only | the `RCALIBFRAC`-*level* replacement — **the y-axis for external-influence studies** (mirror ΔT, wind, …) |
| **B** | `L_field` — DAR field pattern, `1 − A(σ,\|G·r\|)/A_ref` | acceptance loss across the field from the delivered offset | **per-fiber map** (radial gradient + quadrupole; dipole ≡ 0) | field-differential drift `G` = scale+shear | the DAR distortion pattern; field pattern searches |
| — | **Drift/shear check** | drift amplitude (arcsec) vs DAR edge offset ΔG; B’s quadrupole vs dark-sky `Q_rot` | *validation*, not an output | — | confirms A and B; does **not** feed examples |

The two “radial” things are **not** the same: **A** is a whole-array
*constant* (a monopole level), while **B** has a radial *gradient* that
grows toward the field edge. External-influence examples use **A** (the
scalar); they do **not** average B’s grid, and they do **not** use
`RCALIBFRAC`. `dar_gfa_fiber_loss_metric_v2` is **B** (radial-only until
the scale+shear fix); it is not A.

> **Design correction (from a first prototype that failed the validation
> gate).** The two lessons below are baked into the construction: (1)
> use only the *field-differential* offset `G·r`, never the raw
> translation `t`; (2) validate in *offset/arcsec* space, not by
> round-tripping through the acceptance model.

### 3.1 The DAR spatial pattern — the field-differential offset, in arcsec

- **Input:** the field-differential offset field δ(r) = `G·r`, where `G`
  is the **intra-exposure shear *drift*** — the shear accumulated over
  the exposure (from the ETC per-frame guide-star offsets), **not** a
  single-epoch snapshot. The loss is an intra-exposure-accumulated
  effect (fibers placed once, star drifts over the exposure), so the
  drift is the physically-apt quantity; a static `PMGSTARS`/`PMGWCS`
  shear snapshot is a *different, smaller* quantity (in the first
  prototype the static shear gave ~7 μm at am~2 vs the loss-based ~11–15
  μm — the static-vs-drift gap). *\[Validated at am ≲ 1.6 — see §3.3. At
  am \> 1.8 metric B’s predicted quadrupole runs ~40% above the dark-sky
  flux for reasons not yet established (§3.3); treat it as approximate
  there.\]*
- `G` **must be the full** `scale + shear` **compression, not shear
  alone.** The DAR field-differential is a 1-D zenith compression
  `δ(r)=c·(r·ẑ)ẑ`, which decomposes into equal parts isotropic scale and
  shear (`G = (c/2)I + (c/2)·shear`). A *pure-shear* offset gives
  `|δ|² = (e1²+e2²)(u²+v²)` — perfectly radial, so its loss carries
  **zero quadrupole** (NERSC, 2026-08-06, verified algebraically); the
  loss quadrupole is the **scale×shear cross-term**, which needs both.
  So feed the scale drift `s(t)` (already in Test 4’s 6-param affine
  fit) alongside the shear drift. Note this does *not* affect the
  offset-space validation below: for a 1-D compression scale=shear, so
  the shear *amplitude* remains a valid proxy for ΔG.
- **Use only** `G·r`**; do NOT include the raw translation** `t`**.**
  The uniform (boresight) part of the guide-model residual is
  guide-loop-corrected before the science exposure begins (Part IV of
  the report; the dither shows no *delivered* uniform offset), so
  feeding raw `t` in reintroduces an offset the fibers never feel — in
  the first prototype it produced a large spurious dipole (D_rot/Q_rot
  up to 5.3). Only the field-differential term is delivered, and with it
  D_rot = 0 by construction, correctly.
- **Validate in offset (arcsec) space, not loss space.** Compare `G`
  directly to the DAR edge offset ΔG (0.11 / 0.16 / 0.22″ at am 1.48 /
  1.69 / 1.86) — the comparison the guide-star cross-check already
  passed (0.102″ / 0.168″ vs 0.11″ / 0.16″). Do **not** round-trip
  `G → A(σ,δ) → refit a loss-quadrupole → σ_eff·√(2Q)` to reproduce a
  quantity you can check geometrically; that round-trip introduced a ~2×
  normalization and an airmass-shape distortion in the first prototype
  (an σ-consistency issue between the FF and the ΔG conversion).
- **Convert to a loss only if a loss number is wanted:** apply the
  acceptance model once, `loss(r) = 1 − A(σ, |G·r|)/A(σ, 0)`, keeping σ
  consistent throughout.

### 3.2 The whole-array level — the σ / seeing channel (the genuinely new, `t`-free part)

For external-influence studies (dome seeing, temperature, wind) the
whole-array loss *level* is what you want, and the cleanest channel
avoids the offset entirely: - **Dome seeing / PSF size:**
`A(σ_seeing, 0)` directly captures the seeing-driven whole-array fiber
loss — no offset needed. Normalize to a nominal `A(σ_nom, 0)` for a
fraction; regress against seeing / temperature telemetry. This is the
clean, `t`-free metric for the dome-seeing / transparency use case. -
**Wind / thermal *shift*:** needs the real *delivered* whole-array
offset — from guiding telemetry / the applied mount corrections —
**not** the raw guide-model `t` (which is guide-corrected). If a
validated delivered-boresight quantity isn’t available, this channel
stays open; the σ channel above covers the dome-seeing case regardless.

**Scope:** whole-array level (σ channel) + low-order field pattern
through the quadrupole (`G·r`). By design it carries **no delivered
uniform dipole**, and it is blind to per-fiber / high-order structure
(§2).

### 3.3 Offset space vs loss space, and the high-airmass discrepancy

**Two spaces.** A field distortion can be expressed either as a physical
*displacement* — *offset space*, in μm, how far a target sits from its
fiber — or as the *fractional light loss* that displacement causes —
*loss space*, obtained by pushing the displacement through the
fiber-acceptance function `A(σ, δ)`. The acceptance function is what
links the two, and the metric can be built or checked in either. The
measurement chain is indirect, and worth stating precisely: **guide
stars have no fibers.** They drift from their *nominal positions*; from
the ≤ 6 edge GFAs we fit a field distortion `G`; we then *infer* that a
science fiber at position r has its target offset by `G·r`; and only
then does the (fiber) acceptance function apply. So a loss-space number
stacks an acceptance-inversion on top of an already edge-extrapolated,
*inferred* fiber offset — several steps removed from a direct
measurement, which is why it is treated with caution.

**Validation.** `L_field` (the scale+shear DAR quadrupole) was compared
to the dark-sky `RCALIBFRAC` `Q_rot → ΔG` target (the artifact-minimized
flux measurement), using the **identical** `σ_eff·√(2Q)` conversion for
both:

| am cut | `L_field` *predicted* ΔG | dark-sky *measured* ΔG |  |
|----|----|----|----|
| \> 1.4 | 7.5 μm | 8.7 μm | agree |
| \> 1.6 | 10.9 μm | 9.9 μm | agree |
| \> 1.8 | 16.3 μm | 11.1 \[10.3, 12.1\] μm | **predicted ~40% high** |

Because the conversion is identical, this is **not** a conversion/route
artifact: at high airmass **the geometry predicts more quadrupole loss
than the flux measures.**

The overshoot was diagnosed exhaustively (both sessions; Mac reproduced
the numbers). Ruled out as the cause:

- **outlier tail** — only 2 of 176 exposures exceed am 2.05; excluding
  them gives 15.4 μm (barely moves);
- **high-leverage exposures** — jackknife shows a broad population
  effect, no single driver;
- **target measurement uncertainty** — the dark-sky target’s own
  bootstrap CI is tight, \[10.3, 12.1\] μm;
- **small-sample bias** — subsampling a *fixed* low-airmass population
  down to n = 90 does **not** inflate the median (only widens the
  scatter), so it is an airmass effect, not a sample-size effect;
- **magnitude / noise rectification** — `L_field`’s airmass growth
  matches the *coherent* (mean-first) drift statistic (ratio ≈ 4.2), not
  the magnitude-first (≈ 2.7) or RMS (≈ 2.3), so it is the genuine
  coherent quadrupole, not a rectified/noise-inflated one;
- **scale contamination** — the scale/shear drift ratio is flat at ~0.73
  across airmass.

**Physically real, and bracketed — the dither result.** The one
measurement that can adjudicate “geometry over-predicts” vs “flux
suppressed” is the **dither**, which directly measures the *delivered*
per-fiber offset (ground truth, artifact-immune). Its coherent
zenith-frame quadrupole **steepens with airmass ~as the physical** `am²`
**DAR law** — the delivered-offset shear grows ×2.5 and the cross-term
quadrupole ×11 over am 1.15 → 2.06, against the `am²` expectations of
×3.2 (offset) and ×10 (squared). So the high-airmass steepening is
**physically real, not a metric artifact.** Against that ground-truth
`am²` law, both estimates deviate — in *opposite* directions: over a
comparable span `am²` predicts a Q-ratio ≈ 2.3, the **flux grows
shallower** (×1.6 → it *under*-represents at high am) while `L_field`
**grows steeper** (×4.7 → it *over*-represents). So the true am \> 1.8
quadrupole most likely **sits between the flux’s 11 μm and**
`L_field`**’s 16 μm**, not cleanly on either. *(Caveats: the dither is a
static **total** offset vs* `L_field`*’s intra-exposure **drift**, and
thin at high airmass (n ≈ 91) — so it brackets the value rather than
pinning it.)*

Everything simpler was ruled out first: two mechanism guesses (small-n
rectification; RMS/undirected rectification) were explicitly **tested
and falsified** (recorded so they are not re-proposed), and the tempting
coincidences — the shear-drift *amplitude* (~11 μm) matching the flux,
the loss-space value (~16) matching the *undirected RMS drift* — are
most likely coincidental (the shear amplitude is a different quantity
from a quadrupole ΔG; the RMS match fails on airmass scaling).

**Practical guidance.** `L_field` validates against the clean flux at am
≲ 1.6. For **detecting** the field pattern, tracking its **relative**
variation, or **anomaly** searches, it is reliable at *all* airmass —
the dither confirms the airmass behaviour is physical. The only soft
spot is the **absolute magnitude at am \> 1.8**, which is bracketed
**11–16 μm (~±40%)** rather than a single number. This caveat is
specific to `L_field`’s field-pattern quadrupole; it does **not** affect
`L_see` or any whole-array-level use.

### 3.4 Both metrics are free of the rotating dipole — by construction *and* in data

Escaping the `RCALIBFRAC` rotating dipole (`D_rot`) is the whole reason
these metrics exist, so it is worth confirming they are free of it — not
just structurally but against data.

- **By construction.** `L_see` is a whole-array *scalar*; it has no
  spatial structure, so it cannot carry a dipole (or any rotating
  pattern) at all. `L_field` uses only the field-differential offset
  `G·r` and drops the uniform translation `t` — the one term of an
  affine field that produces a dipole — so its `D_rot` is identically
  zero (verified: `D_rot = 0.0000` at every airmass cut).
- **In data.** The rotating dipole is a large, highly significant
  feature *of the flux*: fitting `D_rot` to the `RCALIBFRAC` loss field
  gives a **≈ 77σ** detection (n = 24,630 exposures). It is *absent from
  the delivered geometry* — the dither offset field (the ground-truth
  delivered offset, measured independently of the flux) shows the real
  DAR quadrupole but **no** rotating dipole (the dipole-null established
  in `DAR_FIBER_LOSS_REPORT.md` using the artifact-free `xfiboff+xtel`
  quantity). So the dipole lives in the sky-subtracted flux, not in the
  geometry these metrics are built from. That is the empirical basis for
  dropping `t`, and the confirmation that neither `L_see` nor `L_field`
  inherits the artifact they were built to avoid.

## 4. Calibrating and bounding it with the dither

On dither-overlap nights the dither gives the *true* per-fiber offset
δ_true → true `FF_true = A(σ, δ_true)`. Comparing the GFA-predicted
(affine, edge-extrapolated) `FF` to it: - **validates** the affine
extrapolation from the edge GFAs to the science field; - **calibrates**
any bias/scale between predicted and true loss; - the **residual**
`FF_true − FF_GFA` quantifies the per-fiber part the GFA cannot see —
i.e. the metric *measures its own scope boundary* rather than asserting
it.

Bonus cross-check: differencing this artifact-free loss against
`RCALIBFRAC` on the same exposures isolates the **non-geometric** part —
a direct handle on the sky-subtraction artifact (and, in principle, a
way to de-artifact `RCALIBFRAC` for the low-order terms).

## 5. Implementation notes

- **Data (NERSC-side):** guide-star PSF/seeing per exposure (GFA
  reduction / ETC products); the affine offset field from the
  per-exposure PlateMaker product `pm-<expid>.fits` (`PMGSTARS`/`PMGWCS`
  residuals — the same source used for the `Q_rot` guide-star
  cross-check); the acceptance model from `desimodel`
  `FastFiberAcceptance` + `load_platescale` (σ, δ in μm via the
  platescale).
- **Reference scales:** σ_eff ≈ 52 μm was the effective acceptance scale
  found in the DAR study (fiber-size dominated at DESI seeing); use the
  real `FastFiberAcceptance` curve rather than a fixed σ_eff for the
  prediction.
- **Validation target:** the dither offset field
  (`analysis/dar_dipole/dither_offset_field_test.py` machinery) on
  overlap nights; and `Q_rot`/`ΔG` from `DAR_FIBER_LOSS_REPORT.md` as
  the known low-order pattern the demeaned-mode metric must reproduce.

## 6. Use cases — which metric for which study

The two outputs answer different physical questions. Pick by what the
study’s driver acts on.

`L_see` **— whole-array seeing level.** Use when the effect acts on the
PSF *size* / the whole focal plane at once and you want a single
per-exposure loss number to regress against an external variable. It is
artifact-free, uses no offset and no round-trip — the reliable choice
for external-influence studies. - Mirror–air ΔT → mirror seeing → PSF
broadening → loss (the immediate use case). - Dome seeing; ambient
temperature; humidity / condensation effects on image quality. - Wind
where the effect is image *degradation* (shake / turbulence broadening),
not a coherent pointing shift. - Time / seasonal trends in seeing-driven
throughput; sanity-checking the ETC’s delivered image quality. - *Not
for:* the DAR field pattern or any pointing/offset-driven structure —
that is `L_field`.

`L_field` **— scale+shear DAR field pattern.** Use when you care how the
loss varies *across the field* from a coherent offset distortion, not
the whole-array level. - Characterizing / monitoring the DAR compression
pattern; validating the DAR model or PlateMaker against the delivered
field. - Field-pattern anomaly searches — e.g. a rotator / hexapod /
mount issue imprinting an unexpected low-order pattern. - Reliable for
**detection / relative / anomaly** use at all airmass; the **absolute**
magnitude is validated at am ≲ 1.6 and bracketed 11–16 μm at am \> 1.8
(§3.3). Blind to per-fiber / high-order structure. - *Not for:*
whole-array-level studies — that is `L_see`.

**Neither — you need the dither.** Per-fiber offsets, per-petal
patterns, or any high-order (beyond affine) structure are below the
edge-GFA affine scope (§2). Those require the dither offset field
(sparse, special sequences), which is also the calibrator / ground truth
for `L_see` and `L_field` (§4).

**Rule of thumb:** whole-array *level* → `L_see`; low-order field
*pattern* → `L_field`; per-fiber / high-order → dither.

## 7. Using the metrics — the `Exposure` API

Both metrics are exposed as cached properties on `telemetry_mining.Exposure`, so the common case is a one-liner:

```python
from telemetry_mining import Exposure
exp = Exposure(255020)
exp.L_see      # -> float: whole-array seeing loss level, or None
exp.L_field    # -> float: DAR field-distortion loss, or None
```

**What you get.** Each returns a single `float` per exposure, or `None` when the metric can't be produced for
that exposure (see *Coverage* below) — the module's standard "None means unavailable" contract, so you can skip
`None`s rather than guard against exceptions.

**How the value is produced — compute-direct, then fall back.** Each property first tries to compute the metric
*directly* from the offline inputs; if those aren't available at this site (or `desimodel` isn't installed) it
falls back to a precomputed `fiber_loss_metrics` table *if one is registered*; otherwise it returns `None`:

> **direct compute → registered `fiber_loss_metrics` table → `None`**

This is what lets the *same attribute* work at NERSC (direct) and at KPNO (table). You don't choose the path —
the property does. The two paths return identical values (the precompute script and the live attribute share
one implementation, `telemetry_mining.fiber_loss`).

**What each needs (direct path):**

| metric | inputs | needs `desimodel` |
|---|---|---|
| `L_see` | offline GFA seeing (`FWHM_ASEC`) | yes (FastFiberAcceptance + platescale) |
| `L_field` | offline GFA seeing + ETC per-frame guide drift + `exp.parallactic` | yes |

At **KPNO** the offline GFA reduction isn't available, so the direct path can't run — register the precomputed
table (below) to serve both metrics there. `exp.parallactic` (degrees) is exposed for `L_field`'s zenith-frame
rotation and is useful on its own.

**Coverage — when you get `None`:**

- `L_see`: available for any exposure with a valid GFA seeing measurement.
- `L_field`: needs a *multi-frame* exposure (there must be an intra-exposure drift to measure) — `None` for
  too-short / calibration exposures. It is reliable for detection / relative use at all airmass; its *absolute*
  magnitude is approximate above am ≈ 1.8 (§3.3).

**Bulk use** (e.g. the mirror-ΔT `L_see` study, or the `|Δairmass|` `L_field` study):

```python
import pandas as pd
from telemetry_mining import Exposure

rows = [(e, Exposure(e).L_see, Exposure(e).L_field) for e in expids]
df = pd.DataFrame(rows, columns=["EXPID", "L_see", "L_field"]).dropna(subset=["L_see"])
```

**Registering the precomputed table** (for KPNO, or just to avoid recomputing): build it once with
`scripts/build_fiber_loss_metrics.py`, then register it process-wide so every `Exposure()` sees it:

```python
from telemetry_mining.tables import TableSource, DEFAULT_TABLE_SOURCES
DEFAULT_TABLE_SOURCES.append(
    TableSource("fiber_loss_metrics", path="data/fiber_loss_metrics.parquet", index_column="EXPID")
)
# exp.L_see / exp.L_field now fall back to this table wherever direct compute can't run
```

**Lower-level access.** The metric math itself lives in `telemetry_mining.fiber_loss` — `l_see_from_fwhm`,
`sheardrift_from_thru`, `l_field_from_drift` — if you want to compute the metrics outside of an `Exposure`
(e.g. in a batch job over precomputed inputs). That is exactly what `build_fiber_loss_metrics.py` does.
