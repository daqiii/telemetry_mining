# Test 4 — per-frame affine decomposition of the guide-GFA offsets

K Honscheid (OSU) with Claude · NERSC session · 2026-08-05

Follow-up to `DAR_DIPOLE_NERSC_HANDOFF.md` (Test 4) and `FIELD_ROTATION_REPORT.md` (Part 5). This
document reports a completed, self-contained analysis; it does not modify either of those documents.

---

## TL;DR

- **Method validated on two single exposures** (one high-airmass, one near-zenith) before scaling up:
  the 6-parameter affine fit (translation + rotation + isotropic scale + shear) of the 6 guide-GFA
  offset vectors is well-conditioned (condition number 1.23, once positions are properly
  non-dimensionalized — the "co-radial GFA" degeneracy worry does not bite), and the ETC-per-GFA
  channel has genuinely **lower per-frame noise than the guider's own per-star `rotation` estimate**
  (~1.4–2.1× lower scatter, confirmed at both airmasses tested).
- **Scaled to the full D_rot am>1.4 sample (2968 exposures, 100% success, ~2 min runtime).**
- **Rotation channel** (the original motivation): the residual rotation rate (after the online
  `hexapod.rot_rate` model has already been applied) has a small, real, airmass-correlated mean
  (−0.06 → −0.10 arcsec/min from am>1.4 to am>1.8) — **consistent with, not a contradiction of**,
  `FIELD_ROTATION_REPORT.md`'s own airmass finding (real but judged too small to warrant a dynamic
  correction). This analysis does **not** by itself reopen that conclusion — see Caveats.
- **Translation/dipole channel** (Test 1 follow-up): the intra-exposure boresight drift, decomposed
  into a zenith-tied ("rotating") and instrument-tied ("fixed") component using the same convention as
  `fit_dipole_quadrupole.py`, comes out **small and flat with airmass** in its coherent (mean) part
  (~0.01–0.02″, not growing) — it does **not** show the clean D_rot-matching signature (~0.11–0.22″,
  growing with airmass) the surviving hypothesis predicted using the naive `rate×duration` metric. That
  metric was subsequently shown to be the wrong quantity (see the Cross-term follow-up section below,
  which supersedes this bullet's "not decisive" framing with an actual decisive-ish result: the correct
  quantity is real, grows with airmass, but explains only ~3-4% of D_rot — small, not dominant).

---

## Motivation

Two separate threads converge on the same underlying data:

1. **`FIELD_ROTATION_REPORT.md` Part 5** concluded no dynamic rotation correction because no driver
   survived testing against the guider's per-star, per-frame rotation fit — noisy, since GFAs carry
   1–5 stars each (GUIDE7 often just 1).
2. **The DAR dipole investigation** (`DAR_DIPOLE_NERSC_HANDOFF.md`) established a real, coherent,
   zenith-tied, airmass-growing boresight offset (D_rot ≈ 0.14″) in the standard-star flux loss. Test 1
   (the once-per-exposure acquisition offset) came back real but ~100–300× too large to resolve the
   anomaly — dominated by the legitimate bulk pointing/refraction correction, not a small residual.
   Per the "correct placement" reasoning already in memory (`dar-guider-bias-hypothesis`), the physically
   relevant quantity is not the one-time acquisition offset but the **intra-exposure guiding-loop
   residual** — the boresight drift the guider fails to null *during* the science exposure.

The ETC json's per-frame, per-GFA offset vectors (`thru/dx_gfa`, `thru/dy_gfa`) let both questions be
addressed from lower-noise data than either previous approach used: a 6-parameter affine fit per frame
(12 measurements: 6 GFAs × 2 coordinates) separates translation, rotation, scale, and shear jointly,
rather than relying on a single combined per-star centroid estimate.

---

## Method

**GFA geometry, units, ordering** — confirmed directly against `desietc` source (user-uploaded to trunk
root, `desietc-master/desietc/desietc/`), not assumed:
- `thru.dx_gfa`/`thru.dy_gfa` are **pixels** (not arcsec/degrees), one 6-element list per ETC frame.
- Camera order is `desietc.gfa.GFACamera.guide_names = ['GUIDE0','GUIDE2','GUIDE3','GUIDE5','GUIDE7','GUIDE8']`
  — confirmed to match `exposure.exposure.guide_cameras` and the ETC json's `guide_stars` dict key order.
- `desietc/gfa.py` ships a `CS5` dict (from `desimeter.transform.gfa2fp`): each camera's nominal
  CS5 (focal-plane, mm) position, plus the exact pixel→CS5-mm linear (rotation+scale) conversion. Used
  directly rather than re-deriving GFA geometry from `gfadata-*.par`/`gfaoffset-desi.dat` (used for the
  earlier, separate, already-ruled-out gravity-deformation check).

**Per-frame affine model** — for GFA *i* at CS5 position (X_i, Y_i):

```
dX_i = tx + s·X_i − θ·Y_i + e1·X_i + e2·Y_i
dY_i = ty + s·Y_i + θ·X_i + e2·X_i − e1·Y_i
```

6 unknowns (tx, ty, s, θ, e1, e2) from 12 measurements. Per the Kirkby zero-sum caveat, rotation and
shear are **always fit jointly** (never rotation alone) — satisfied by construction, since both are part
of the same 6-parameter solve. Positions are non-dimensionalized by the GFA-ring radius (all 6 GFAs sit
within 407.3–407.6mm of the focal-plane center, in 3 exact antipodal pairs) before checking conditioning
— an earlier attempt without this gave a condition number of ~1e16 (later traced to a sign bug in the
shear columns, not a real degeneracy); the corrected, properly-scaled design matrix gives **1.23**,
essentially perfectly conditioned. The design matrix is identical for every frame (fixed geometry), so
all frames of an exposure are solved in one matrix multiply via a precomputed pseudo-inverse.

**Per-exposure drift** = the linear-in-time slope of tx(t), ty(t), θ(t) across all frames of the
exposure (same precedent as `fieldrotationcorrection.ipynb`'s `rotation_rate_slope`) — kept simple/linear
per agreement, not a robust or higher-order fit.

**Script:** `analysis/dar_dipole/affine_gfa_drift_test.py`. **Data:** `data/dar_test4_drift.parquet`
(2968 rows, one per am>1.4 exposure: `tx_slope_mmpermin`, `ty_slope_mmpermin`,
`theta_slope_arcsecpermin`, `duration_min`, `nframe`, merged with `airmass`/`parallactic`).

---

## Validation (single-exposure checks, before scaling up)

Two exposures tested: EXPID 360097 (airmass 1.98, high) and EXPID 355421 (airmass 1.00, near zenith).

| check | high airmass (360097) | low airmass (355421) |
|---|---|---|
| design matrix condition number | 1.23 | 1.23 (geometry-only, airmass-independent) |
| θ(t) mean ± std | −4.58″ ± 2.38″ | −1.08″ ± 0.77″ |
| correlation(θ_ETC, guider `rotation`) | r=0.91, R²=0.82 | r=0.57, R²=0.32 |
| noise ratio (guider/ETC, detrended) | 1.44× | 2.11× |

The ETC-per-GFA channel is the lower-noise channel at **both** airmasses, and the noise premise the test
was built on holds. The correlation with the guider's own estimate drops at low airmass — plausibly
because the true rotation signal itself is smaller there (~1″ vs ~4.6″), so two independently-noisy
estimates of a smaller true signal naturally correlate less even if neither is biased; this explanation
is plausible but **not independently confirmed**.

---

## Results — rotation channel (the `FIELD_ROTATION_REPORT.md` question)

θ_slope is measured *after* the online `hexapod.rot_rate` model has already been applied — it is the
**residual** rate, directly comparable to what `FIELD_ROTATION_REPORT.md` Part 5 was hunting a driver
for.

| airmass bin | n | mean residual (arcsec/min) | std (arcsec/min) |
|---|---|---|---|
| >1.4 | 2968 | −0.060 | 0.167 |
| >1.6 | 1035 | −0.070 | 0.173 |
| >1.8 | 179 | −0.100 | 0.231 |

- correlation(residual, airmass) = −0.062 — weak, matching `FIELD_ROTATION_REPORT.md`'s own conclusion
  that airmass has real but marginal explanatory power (the report deliberately excluded it from the
  deployed static model on exactly these grounds).
- correlation(residual, the `rot_rate` model value itself) = −0.14 — a real, nonzero correlation,
  meaning the current model's predictions aren't fully independent of its own leftover residual; mild,
  not dramatic.
- The mean residual grows somewhat with airmass (−0.06 → −0.10 arcsec/min) — **the same shape and
  roughly the same size** as the marginal airmass effect `FIELD_ROTATION_REPORT.md` already found and
  chose not to deploy.

**Read: this does not, on its own, reopen the static-vs-dynamic decision.** It reproduces (at improved
per-frame precision) essentially the same small airmass-correlated residual the report already
characterized and dismissed as too small to act on — it neither strengthens nor overturns that call. A
genuine reopening would need the comparison this analysis did **not** do: re-testing the *same* candidate
drivers (weather, TCS-correction magnitude) `FIELD_ROTATION_REPORT.md` Part 5 tested, using this
lower-noise channel, to see if any driver that previously failed to survive full-scale testing now does.

---

## Results — translation/dipole channel (Test 1 follow-up)

Per-exposure translation drift rate × exposure duration = a total drift magnitude (arcsec, via an
approximate 0.070 mm/arcsec focal-plane platescale near the GFA radius), decomposed into a zenith-tied
("rotating") and instrument-tied ("fixed") component using the identical q-rotation convention
`fit_dipole_quadrupole.py` uses for per-star focal-plane X/Y (appropriate here since CS5 is the same
focal-plane-fixed coordinate family, not the RA/Dec frame Test 1's `mount_offset_ra/dec` used).

| airmass bin | n | mean(rotating) [16,84] | RMS(rotating) | mean(fixed) [16,84] | RMS(fixed) |
|---|---|---|---|---|---|
| >1.4 | 2968 | −0.017″ [−0.018,−0.015] | 0.103″ | +0.012″ [0.010,0.014] | 0.096″ |
| >1.6 | 1035 | −0.017″ [−0.020,−0.014] | 0.105″ | +0.015″ [0.012,0.018] | 0.107″ |
| >1.8 | 179 | −0.011″ [−0.019,−0.003] | 0.105″ | −0.000″ [−0.010,0.010] | 0.132″ |

**Target for comparison:** D_rot (physical) ≈ 0.11″/0.16″/0.22″ at these same three airmass bins,
clearly growing with airmass; D_fix roughly flat at about half that scale.

**Read:**
- The coherent (mean) part of the rotating component is small (~0.01–0.02″), statistically distinguishable
  from zero (huge n), but **flat-to-slightly-decreasing with airmass** — not the clear tan(z) growth
  D_rot shows, and only 10–15% of D_rot's magnitude at the corresponding airmass.
- The rotating and fixed components have **similar RMS** (exposure-to-exposure scatter) at every airmass
  bin, and that RMS *is* comparable in scale to D_rot (~0.10–0.13″) — but a scatter of similar size in
  both the zenith-tied and instrument-tied directions is the signature of **exposure-to-exposure guiding
  noise of a given overall scale**, not a coherent, directional, zenith-tied bias. A real dipole needs a
  *persistent* mean in the rotating direction across many exposures (which is exactly what the original
  D_rot fit demonstrated via its q-permutation null) — this small mean does not have that character.
- **This does not confirm the intra-exposure-drift hypothesis at the expected scale**, but it is not a
  clean rule-out either — the naive `rate×duration` metric used here turned out to be the wrong quantity
  entirely. See the follow-up below, which resolves this.

---

## Test 5 — the cross-term follow-up (resolves the #1 open item above) — 2026-08-05, same day

(Named "Test 5" in `DAR_DIPOLE_NERSC_HANDOFF.md`'s prioritized plan; reported here since it's a direct
follow-up to this report's own open item and reuses this report's method/geometry.)

**Why the rate×duration metric was wrong.** Under midpoint fiber placement, a *symmetric* linear drift
about the exposure midpoint contributes **zero** net mean offset by construction — so `resid(t)`'s own
rate, multiplied by duration, cannot be the loss-dipole mechanism. The actual cross-term is

```
dipole-gradient = < M_shear(t) . T(t) >_t / sigma_eff^2
```

where, per ETC frame, `T(t)` = the affine translation (`tx,ty` — the boresight residual `resid(t)`) and
`M_shear = [[e1,e2],[e2,-e1]]` is the affine shear — the field's own differential-DAR term `G(t)`. This
is the **time-average of a product of two correlated series**, not the mean of either series alone — it
is nonzero even for a perfectly symmetric `T(t)` drift, exactly the case the naive metric missed.

**Method.** Re-ran the per-frame affine fit (`analysis/dar_dipole/affine_gfa_crossterm_test.py`),
computing the cross-term directly from the per-frame `(tx, ty, e1, e2)` series for every frame of every
am>1.4 exposure — no linearity assumed, so any curvature in either series is captured, not just a linear
trend. Converted to a quantity **directly comparable to `fit_dipole_quadrupole.py`'s own D_rot** (its
edge value in normalized coordinates u=X/Rn): since the physical cross-term is `(δ0·G·r)/σ²` for a
physical position `r`, and D_rot is the coefficient of `r/Rn`, `D_rot_predicted = Rn · C_zenith / σ_eff²`
— computed entirely in physical mm (`Rn=410mm`, `σ_eff=52μm=0.052mm`), so no arcsec/platescale conversion
is needed for this core comparison (the earlier ~0.070 mm/arcsec approximation is now avoided
altogether, not merely replaced — the real desimodel platescale, confirmed installed and working
directly on NERSC without the manual install the Mac session needed, was pulled and used only for the
secondary arcsec-equivalent reporting below).

**Result.**

| airmass bin | n | D_rot_predicted [16,84] | D_fix_predicted [16,84] | empirical D_rot | empirical D_fix | fraction of D_rot explained |
|---|---|---|---|---|---|---|
| >1.4 | 2968 | 0.00108 [0.00082, 0.00131] | −0.00258 [−0.00292,−0.00226] | 0.0353 | 0.0287 | 3.1% |
| >1.6 | 1035 | 0.00156 [0.00105, 0.00205] | −0.00657 [−0.00727,−0.00589] | 0.0560 | 0.0289 | 2.8% |
| >1.8 | 179 | 0.00344 [0.00175, 0.00524] | −0.01312 [−0.01601,−0.01045] | 0.0810 | 0.0288 | 4.2% |

(`empirical D_rot`/`D_fix` here are from the Foundation-check's fresh, independently-regenerated refit —
see `docs/FOUNDATION_CHECK_REPORT.md` — not the original committed-parquet numbers, though they agree to
2-3 significant figures.) In arcsec-equivalent terms (via the same `δ0 = D_rot·σ_eff/√(2·Q_rot)`
conversion used throughout this investigation, plugging in the measured, empirical Q_rot per bin): the
predicted δ0 is **0.30 / 0.34 / 0.59 μm**, against a measured/target δ0 of **9.8 / 12.2 / 13.8 μm**.

**Read.** This is a real, non-null result, and it is informative — but it is not the win condition.
- The zenith component `D_rot_predicted` **is** statistically distinguishable from zero at every airmass
  bin (bootstrap CI never crosses zero) and **does grow with airmass** — in fact its *fractional* share
  of D_rot grows too (3.1% → 2.8% → 4.2%), meaning it grows somewhat faster than D_rot itself.
- But it accounts for only **~3–4% of D_rot's actual magnitude** — nowhere near matching D_rot's scale,
  which was the explicit win condition. The intra-exposure guiding-residual-drift-times-differential-DAR
  mechanism, as measured through this specific channel, is real but small, not dominant.
- **Unexpected wrinkle**: the "fixed" (instrument-tied) component `D_fix_predicted` is larger than the
  zenith component at every bin and grows *faster* with airmass (roughly 5× from am>1.4 to am>1.8) — the
  opposite of what a purely zenith/DAR-tied mechanism would predict, and also inconsistent with the
  empirical D_fix's flat behavior. This suggests whatever this cross-term is picking up isn't cleanly
  aligned with the zenith direction the way the hypothesis predicted — an open, unexplained feature of
  this result, not just a subdominant-but-otherwise-clean signal.
- **Internal consistency check, for confidence in the pipeline**: the mean shear magnitude measured here
  (~1×10⁻⁵, dimensionless) is the right order of magnitude for the independently-known ΔG (edge-motion
  amplitude, ~8–16 μm across this airmass range, from `quad_compare_weiner_kirkby.py`'s Q_rot-based
  conversion, i.e. ΔG/Rn ≈ 2–4×10⁻⁵) — so the shear channel is measuring something physically sensible.
  The *smallness of the cross-term* is therefore a genuine finding (T(t) and shear(t) are not strongly
  time-correlated at this exposure-averaged level), not an artifact of either channel being broken.

**Per the user's own decision framework for this test**: this is the "flat/small → it isn't (or isn't
dominant)" outcome, not the "matches D_rot's scale and sign" win. **The remaining candidates are the
guide≠science boresight bias or the absolute-pointing residual** (per the original Test 4 spec) — this
specific mechanism, at least as measured through the ETC-per-GFA channel over full-exposure time
averages, is not the dominant source of D_rot.

**Caveats specific to this cross-term result** (in addition to the general ones below):
- **`gfadeform.dat`'s intra-exposure change was checked quantitatively this time, not hand-waved.** For a
  representative high-airmass exposure (HA 1.26°→7.15° over 23.5 min, airmass 1.985→2.007), the
  PlateMaker/Dervish-world gravity-deformation model's net boresight prediction changes by only **~0.44
  μm** over the exposure — small compared to the ~6–9 μm measured T(t) scatter for the same exposure, and
  its absolute value (~2 μm) matches the already-established, already-ruled-out gravity-deformation
  finding almost exactly (confirms the original `net_boresight_gfadeform.py` computation reproduces
  correctly on NERSC). **However**: `gfadeform.dat` is PlateMaker/Dervish-world, while this test's CS5
  geometry and per-frame measurement is desimeter/desietc-world — two independently-developed codebases
  answering related but not identical questions about the same physical GFAs. This check assumes the
  gravity-deformation effect is comparable across both pipelines; that cross-pipeline correspondence is
  physically reasonable but not independently proven here.
- The cross-term's sign/rotation convention reuses `fit_dipole_quadrupole.py`'s exact q-convention
  (appropriate since CS5 is the same focal-plane-fixed frame family) — not re-verified independently for
  this specific derived quantity.

---

## Caveats (read before trusting either result)

- **`gfadeform.dat`'s intra-exposure change**: checked quantitatively for the cross-term follow-up above
  (found small); not separately re-checked for the rotation channel's residual-rate result.
- **Platescale (0.0700 mm/arcsec) was an approximation** in the original translation-channel calculation
  above — superseded in the cross-term follow-up, which avoids needing a platescale conversion for its
  core result entirely (working in physical mm throughout) and uses the real desimodel platescale for
  its secondary arcsec-equivalent reporting.
- **Only a linear-in-time drift model was fit** for the rotation channel and the original (now-superseded)
  translation-channel metric, by agreement — the cross-term follow-up avoids this by computing directly
  from the per-frame series, not a linear fit.
- The low-airmass exposure's weaker ETC-vs-guider correlation (r=0.57 vs 0.91) has a plausible but
  unconfirmed explanation (lower true-signal amplitude near zenith) — not independently checked with a
  third exposure or an SNR-based argument.
- The rotation-channel comparison to `FIELD_ROTATION_REPORT.md` is **not a controlled, apples-to-apples
  re-test** of that report's own recalibrated model or its specific candidate drivers (weather, TCS
  correction magnitude) — it's a first-look comparison of raw residual statistics, not a rerun of Part 5's
  methodology on the new channel.

---

## Conclusion

- **Field rotation**: the improved-precision residual reproduces the same small airmass-correlated trend
  `FIELD_ROTATION_REPORT.md` already found and dismissed — consistent with, not a challenge to, the
  existing "static model, no dynamic correction" recommendation, on the evidence gathered here. Not
  decisive (no controlled re-test of Part 5's specific candidate drivers was done).
- **DAR dipole — now decisive, resolving the original open item.** The naive translation-drift proxy
  (rate×duration) was the wrong quantity; the correct cross-term
  (`⟨M_shear(t)·T(t)⟩/σ_eff²`, computed directly from the per-frame series) is real, statistically
  significant, and grows with airmass — but explains only **~3–4% of D_rot's magnitude**, with an
  unexplained wrinkle (its "fixed"-direction component is larger and grows faster than its zenith
  component, which the pure hypothesis didn't predict). **This intra-exposure guiding-residual-drift
  mechanism, as measured through the ETC-per-GFA channel, is real but not the dominant source of D_rot.**

**Credible next steps:** (1) the DAR dipole thread's remaining candidates, per the original Test 4 spec,
are the guide≠science boresight bias or the absolute-pointing/acquisition-astrometry residual (Test 1's
original target, still not resolved at the needed precision — see that test's status in
`DAR_DIPOLE_NERSC_HANDOFF.md`); the unexplained "fixed exceeds rotating" wrinkle in the cross-term result
is itself worth understanding before moving on, since it suggests this channel is picking up something
real that isn't cleanly the zenith-tied mechanism hypothesized. (2) re-test `FIELD_ROTATION_REPORT.md`
Part 5's specific candidate drivers using this lower-noise channel before concluding anything new about
the static-vs-dynamic rotation question.

## Related
- `docs/DAR_DIPOLE_NERSC_HANDOFF.md` (Test 1/Test 4 definitions; this report is Test 4's writeup).
- `docs/FIELD_ROTATION_REPORT.md` (Part 5, the static-vs-dynamic rotation question this partially revisits).
- Memory: `dar-guider-bias-hypothesis` (full evolving record, including the correct-placement cross-term
  reasoning behind the caveat above), `field-rotation-report`.
