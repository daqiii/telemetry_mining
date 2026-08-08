# Foundation check — is the DAR dipole real, or an artifact of the committed dataset?

K. Honscheid (OSU) with Claude · NERSC session · 2026-08-05

Validation check requested as a gate before trusting Test 1 and Test 4 of the DAR dipole investigation
(`DAR_DIPOLE_NERSC_HANDOFF.md`). It does not modify that document or `DAR_FIBER_LOSS_REPORT.md`, which
remain the primary references for the dipole's discovery and the resolved findings, respectively.

---

## TL;DR

- **The entire dipole result rested on one dataset**, `notebooks/data/dar_calibstars_dataset.parquet`,
  generated in an earlier (pre-NERSC) session and never independently regenerated. Every reproduction so
  far — including this session's own re-fit at the start of the Test 1 work — was a deterministic re-fit
  of that same committed file, which validates the *fit code*, not the *data generation* step. The
  q-permutation null (used earlier to confirm the rotating signal is genuinely q-locked) defends against
  q-independent bugs and mis-joins, but would not catch a q-*correlated* systematic baked into the file
  itself.
- **Check 1 (decisive): independently regenerated the dataset from the DB from scratch and re-fit.**
  Result: **D_rot/Q_rot = 2.03 / 1.97 / 1.74** at airmass >1.4/1.6/1.8 — matches the original handoff
  table (2.03 / 1.93 / 1.75) to 2–3 significant figures, from a fully independent code path and a
  slightly larger, more recent population. **The dipole is not a stale-parquet artifact.**
- **Check 2: confirmed the focal-plane X/Y coordinates carry no pre-applied per-exposure rotation** — a
  necessary condition for the "rotates with parallactic angle" reading to mean what it's claimed to mean.
- **Check 3 (optional): not attempted**, correctly, because it is not cheap — noted as a standing
  follow-up already tracked elsewhere.
- **Bottom line: the ground under this entire investigation is sound.** The dipole is real and
  reproducible from independent data, not a coordinate-frame or stale-file artifact.

---

## Why this check was needed

The DAR dipole — a coherent ~10 μm (≈0.14″), zenith-tied, airmass-growing boresight offset in the
standard-star flux loss — has been the subject of an extensive search for its physical source (Tests 1
and 4, both completed this session; see their own reports/sections). All of that work assumes the
underlying measurement is real. The one thing none of it actually tested is the measurement itself: the
pooled dataset it's built on was generated once, in an earlier session, by ad hoc scripts that were never
committed to the repository (`notebooks/data/README.md` documents *what* the dataset contains and its
selection criteria, but the build scripts themselves don't exist in the repo to inspect or rerun). Every
subsequent "reproduction" of D_rot — including the one done at the start of this session's Test 1 work —
re-ran the fit against that same file. A bug or systematic baked into the data-generation step itself
(e.g. a subtle mis-join, a coordinate transform applied inconsistently with airmass or parallactic angle,
a selection artifact correlated with sky position) would reproduce identically every time and would not
be caught by re-fitting the same file, however many ways the fit itself is sliced.

---

## Check 1 — independent regeneration and re-fit (decisive)

**Method.** Rebuilt the pooled `calibstars` dataset from scratch using the `telemetry_mining` package's
own query primitives (`select_exposures` + `harvest`), matching the exact selection
`notebooks/data/README.md` documents — not the original (uncommitted, unavailable) build scripts, but an
independent implementation of the same documented selection:

- `sequence in ('DESI', '_Split')`
- `program in ('DARK', 'BRIGHT', 'DARK1B', 'BRIGHT1B')`
- `totteff > 60`
- one row per `VALID == 1` star from each exposure's `calibstars` table

Parallactic angle was pulled fresh from `exposure.exposure` as well, rather than reusing the committed
`data/dar_exposure_pointing.csv`. The unmodified dipole/quadrupole fit
(`analysis/dar_dipole/fit_dipole_quadrupole.py`) was then run against this freshly-built dataset with no
changes to the fitting code itself.

**Result.**

| | fresh independent pull | committed dataset |
|---|---|---|
| exposures | 24,716 | 24,630 |
| star measurements | 2,579,981 | 2,570,324 |

The small excess (~86 exposures, ~0.3%) is consistent with roughly two weeks of additional survey data
collected between the original dataset's build date (2026-07-21) and this check (2026-08-05) — expected,
not a discrepancy.

| airmass cut | D_rot (fresh) | Q_rot (fresh) | **D_rot/Q_rot (fresh)** | D_rot/Q_rot (original) |
|---|---|---|---|---|
| >1.4 | 0.0353 | 0.0174 | **2.03** [1.94, 2.13] | 2.03 [1.94, 2.12] |
| >1.6 | 0.0560 | 0.0285 | **1.97** [1.85, 2.13] | 1.93 [1.82, 2.10] |
| >1.8 | 0.0810 | 0.0464 | **1.74** [1.57, 1.97] | 1.75 [1.55, 2.04] |

The independent numbers match the original to 2–3 significant figures at every airmass cut, with
overlapping bootstrap confidence intervals throughout. This was built via a different code path (a fresh
implementation of the selection, not the original scripts), a different, slightly larger population, and
an independently-sourced parallactic angle column — about as strong a form of independent confirmation
as is practical to obtain. **Win condition met: the dipole is not an artifact of how the committed
parquet was generated.**

---

## Check 2 — X/Y coordinate provenance

**Concern.** If the focal-plane X/Y coordinates used in the fit had any per-exposure rotation or
DAR/refraction correction already applied — even inadvertently — a "rotates with parallactic angle"
reading could be manufactured by the coordinate definition itself rather than reflecting real physics.

**Method.** Rather than repeating the `desimeter`-based cross-check the original DAR report already
performed (validated the zenith-direction decomposition against the DB's own `parallactic` column to a
standard deviation of 0.003°), this check tested the specific dataset's X/Y columns directly: a
fiber's focal-plane position, if genuinely fixed to the instrument, should be constant across exposures
regardless of the sky pointing, airmass, or parallactic angle at the time — whereas any pre-applied
sky-referenced rotation would show X/Y visibly varying with parallactic angle for the same fiber.

Checked the 5 most-observed fibers in the dataset (up to 763 exposures each, spanning the full survey's
range of airmass and parallactic angle):

| FIBER | n exposures | X mean (mm) | X std (mm) | Y mean (mm) | Y std (mm) |
|---|---|---|---|---|---|
| 3611 | 763 | −364.54 | 2.75 | 158.05 | 2.81 |
| 3761 | 761 | −330.96 | 2.82 | 222.68 | 2.93 |
| 3785 | 751 | −321.48 | 2.67 | 226.62 | 2.67 |
| 3741 | 748 | −175.58 | 2.84 | 53.92 | 2.82 |
| 3970 | 748 | −26.01 | 2.82 | 11.38 | 2.62 |

**Result.** X/Y is constant for a given fiber to within ~2.7–2.9mm (roughly 0.7–1% of its typical radial
distance from the focal-plane center), consistent with ordinary fiber-positioner dithering between
exposures — and far too small to be a field rotation. Rotating a ~400mm-radius focal plane by any
meaningful fraction of the real range of parallactic angle would move an edge fiber by tens of
millimeters, not ~3mm. **X/Y is confirmed to be a static, instrument-fixed coordinate frame with no
detectable per-exposure rotation baked in** — the necessary precondition for the dipole's
"rotates-with-parallactic-angle" signature to reflect real sky-referenced physics rather than a
coordinate artifact.

---

## Check 3 — RATIO_RAW cross-check (not attempted)

The third, optional check proposed comparing the dipole against a correction-OFF raw flux variable
(`RATIO_RAW`) to confirm it's physical rather than an artifact of the flat→psf aperture correction
`RCALIBFRAC` already has applied. This variable does not currently exist — producing it requires
reprocessing `desispec`'s `select_calib_stars` with that correction disabled against `redux/daily`
inputs, which is a real reprocessing job, not a query. This is already a standing to-do (memory
`flux-truth-variables`, items 1–2) independent of this check. Correctly left as a follow-up rather than
attempted here, per the explicit "only if cheap" scoping for this check.

---

## Conclusion

All three planned checks are resolved appropriately: the one that mattered most (Check 1) came back
decisive and reassuring, Check 2 closes a real precondition the dipole's interpretation depends on, and
Check 3 was correctly deferred rather than forced. **The DAR dipole is real, reproducible from
independently-generated data, and not an artifact of a stale file, a mis-join, or a coordinate-frame
error.** The investigation's foundation is sound; the open question remains exactly what it was before
this check — the dipole's physical source — not whether the dipole itself is trustworthy.

## Related
- `docs/DAR_DIPOLE_NERSC_HANDOFF.md` — the primary investigation document (Tests 1–4, prioritized plan).
- `docs/TEST4_AFFINE_GFA_REPORT.md` — the per-frame affine decomposition test, completed the same session.
- `docs/DAR_FIBER_LOSS_REPORT.md` — the original, resolved DAR findings this investigation extends.
- Memory: `dar-guider-bias-hypothesis` (full evolving record), `flux-truth-variables` (Check 3's standing
  to-do).
