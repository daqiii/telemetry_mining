#!/usr/bin/env python3
"""Regenerate docs/FIELDS.md: a glossary of every field/column this project has touched.

Pulls live from the DB and real files for one reference exposure, so
example values are real, not invented. Descriptions come from a hardcoded
dict (DESC, below) built from everything discussed/verified across this
project's development; anything without a known description is left blank
rather than guessed.

Usage (from an environment with a working psycopg2/fitsio -- see README.md):
    python3 scripts/build_fields_glossary.py [expid] [night] > docs/FIELDS_body.md
Then splice docs/FIELDS_body.md under this file's existing intro (everything
above the "---" divider in docs/FIELDS.md is hand-written and should be kept).

Defaults to expid 359483 / night 20260702 -- pick a different, more recent
exposure that still has cframe/exposure-qa data (i.e. not too old -- see
the retention gotchas in docs/API.md) when refreshing this.
"""
import json
import sys

import fitsio
import pandas as pd

from telemetry_mining import Config, db

EXPID = int(sys.argv[1]) if len(sys.argv) > 1 else 359483
NIGHT = int(sys.argv[2]) if len(sys.argv) > 2 else 20260702
CFG = Config.default()

OUT = []


def section(title, anchor_note=""):
    OUT.append(f"\n## {title}\n")
    if anchor_note:
        OUT.append(anchor_note + "\n")


def table(rows, headers=("Field", "Type", "Description", "Example value", "Source")):
    OUT.append("| " + " | ".join(headers) + " |")
    OUT.append("|" + "---|" * len(headers))
    # sort rows alphabetically (case-insensitive) by field name -- a glossary is
    # for looking things up, so alphabetical beats DB/file definition order
    for row in sorted(rows, key=lambda r: str(r[0]).lower()):
        cells = [str(c).replace("\n", " ").replace("|", "\\|") if c is not None else "" for c in row]
        OUT.append("| " + " | ".join(cells) + " |")
    OUT.append("")


def truncate(v, n=60):
    s = str(v)
    return s if len(s) <= n else s[: n - 3] + "..."


# ---------------------------------------------------------------------------
# Source column: how to actually fetch each field via telemetry_mining's
# Exposure API / the resolve_spec mini-language (telemetry_mining.query).
# Mechanical per section (not hand-curated like DESC), with a few real
# exceptions verified against source code / the live DB -- see docs/FIELDS.md's
# own "Source column" note for the full explanation. Keep this in sync with
# exposure.py/query.py if either changes; a stale Source is worse than none.
# ---------------------------------------------------------------------------
HYPHENATED_HEADER_KEYS = {"DATE-OBS", "MJD-OBS", "TIME-OBS", "OBS-ELEV", "OBS-LAT", "OBS-LONG", "ALARM-ON"}
EXPOSURE_TABLE_FLAGS_KEYS = {"LASTSTEP", "CAMWORD", "BADCAMWORD", "BADAMPS", "EXPFLAG", "HEADERERR"}
GUIDER_CENTROIDS_EXPOSED_KEYS = {
    "frame", "time_recorded", "obstime", "seeing", "nstars", "ngfas",
    "combined_x", "combined_y", "tcs_correction_ra", "tcs_correction_dec",
    "rotation",
}
FIBERQA_HEADER_EXPOSED_KEYS = {"NGOODFIB", "NGOODPET", "WORSTRDN", "FPRMS2D", "EFFTIME"}

# Marker for a column that isn't surfaced individually. The *how-to-get-it* is stated once
# in that section's intro note (see the notes below), not repeated on every row -- keep these
# in sync with the matching section() note or the marker becomes meaningless.
DASH = "—"

NOTE_EXPOSURE_TABLE = (
    " The module surfaces a curated 6-field subset via `exp.exposure_table_flags` "
    "(`LASTSTEP`, `CAMWORD`, `BADCAMWORD`, `BADAMPS`, `EXPFLAG`, `HEADERERR`); every other "
    "column (shown as `—`) comes from `telemetry_mining.redux.exposure_table_row(expid, night, config)`."
)
NOTE_TILES_DAILY = (
    "One row per tile, **indexed by `TILEID` (not `EXPID`)**. Not surfaced by `Exposure` "
    "-- read `Config.redux_daily_dir/'tiles-daily.csv'` directly, or attach a custom "
    "`TableSource(index_column='TILEID')`. (Low priority -- see project memory.)"
)
NOTE_GUIDER = (
    "Per-frame table -- one row per guider frame. `exp.guider_centroids` selects a fixed column "
    "list (`frame`, `time_recorded`, `obstime`, `seeing`, `nstars`, `ngfas`, `combined_x`/`combined_y`, "
    "`tcs_correction_ra`/`tcs_correction_dec`, `rotation`); the other columns (shown as `—`) come from "
    "querying `telemetry.guider_centroids` directly via `telemetry_mining.db.fetch_df` or a custom `TableSource`."
)
NOTE_CFRAME = (
    " Per-fiber table: `exp.cframe_table(camera)` needs a `camera` argument, so in a resolve_spec "
    "use a callable, e.g. `lambda exp: exp.cframe_table('b0')['<col>']`."
)
NOTE_FIBERQA = (
    " `exp.fiberqa` exposes a curated 5-key dict (`NGOODFIB`, `NGOODPET`, `WORSTRDN`, `FPRMS2D`, `EFFTIME`); "
    "the other keys (shown as `—`) are read from the FIBERQA header directly via a callable."
)


def note_unexposed_db(schema_table):
    return (
        f"Not surfaced by an `Exposure` accessor -- query `{schema_table}` directly via "
        "`telemetry_mining.db.fetch_df`, or add a custom `TableSource`. (Source `—` throughout.)"
    )


def note_telemetry(table_name):
    return (
        f"Time-windowed telemetry -- reach any column with `exp.telemetry('{table_name}', columns=['<col>'])` "
        "(returns the rows within the exposure's time window). For a single nearest/window scalar usable in "
        f"`select_exposures`, register a `TelemetryField(name=..., table='{table_name}', columns=['<col>'])` "
        'and use the spec `"telemetry.<name>"`.'
    )


def source_header(field):
    if field in HYPHENATED_HEADER_KEYS:
        return (
            f"not expressible as `header.{field}` -- hyphen breaks resolve_spec's "
            f"identifier syntax; use a callable, e.g. `lambda exp: exp.header['{field}']`"
        )
    return f"`header.{field}`"


def source_simple(accessor, suffix=""):
    def fn(field):
        return f"`{accessor}['{field}']`{suffix}"

    return fn


def source_exposure_table_flags(field):
    if field in EXPOSURE_TABLE_FLAGS_KEYS:
        return f"`exposure_table_flags['{field}']`"
    return DASH


def source_tiles_daily(field):
    return DASH


def source_unexposed_db_table(schema_table):
    def fn(field):
        return DASH

    return fn


def source_guider_centroids(field):
    if field in GUIDER_CENTROIDS_EXPOSED_KEYS:
        return f"`guider_centroids['{field}']`"
    return DASH


def make_source_telemetry(table_name):
    def fn(field):
        return f"`exp.telemetry('{table_name}', columns=['{field}'])`"

    return fn


def source_cframe(field):
    return f"`exp.cframe_table(camera)['{field}']`"


def source_fiberqa(field):
    if field in FIBERQA_HEADER_EXPOSED_KEYS:
        return f"`fiberqa['{field}']`"
    return DASH


SOURCE_FN = {
    "header": source_header,
    "coords": source_simple("coords", " (per-fiber table)"),
    "etc_header": source_simple("etc_summary"),
    "exposures_daily": source_simple("redux_row"),
    "exposure_table": source_exposure_table_flags,
    "tiles_daily": source_tiles_daily,
    "db_row": source_simple("db_row"),
    "stars": source_simple("stars", " (per-star table)"),
    "comments": source_simple("comments", " (per-comment table)"),
    "positions": source_unexposed_db_table("exposure.positions"),
    "headers": source_unexposed_db_table("exposure.headers"),
    "guider_centroids": source_guider_centroids,
    "environmentmonitor_telescope": make_source_telemetry("environmentmonitor_telescope"),
    "environmentmonitor_tower": make_source_telemetry("environmentmonitor_tower"),
    "environmentmonitor_dust": make_source_telemetry("environmentmonitor_dust"),
    "cframe_fibermap": source_cframe,
    "cframe_scores": source_cframe,
    "gfa_row": source_simple("gfa_row"),
    "fiberqa": source_fiberqa,
    "fiberqa_table": source_simple("fiberqa_table", " (per-fiber table)"),
    "petalqa": source_simple("petalqa", " (per-petal table)"),
    "calibstars": source_simple("calibstars", " (per-star table, indexed by FIBER)"),
    "fiberassign_table": source_simple("fiberassign_table", " (per-fiber table)"),
}


def src(tag, field):
    return SOURCE_FN[tag](field)


# ---------------------------------------------------------------------------
# Descriptions we actually know, built from this project's development.
# Keyed by (source_key, field_name). Anything absent is left blank.
# ---------------------------------------------------------------------------
DESC = {}

def d(source, **kwargs):
    for k, v in kwargs.items():
        DESC[(source, k)] = v


d("header",
  SKYRA="Sky-pointing RA (deg)", SKYDEC="Sky-pointing Dec (deg)",
  MOUNTHA="Mount hour angle", MOUNTAZ="Mount azimuth", MOUNTEL="Mount elevation",
  **{"DATE-OBS": "Shutter-open timestamp, ISO 8601 (fractional seconds can exceed 6 digits)"},
  EXPTIME="Requested/nominal exposure time (s)",
  AIRMASS="Airmass at exposure",
  WINDSPD="Instantaneous wind speed at exposure time (header snapshot, not a telemetry average)",
  WINDDIR="Instantaneous wind direction",
  GUST="Instantaneous wind gust speed",
  SEQUENCE="Exposure sequence type, e.g. 'DESI' for science exposures",
  SPLITEXP="Whether this exposure was split (cosmic-ray splitting)",
  PMIRTEMP="Primary mirror temperature (platemaker/telemetry snapshot)",
  TAIRTEMP="Air temperature (snapshot)",
  SKYLEVEL="Sky brightness level",
  PMTRANS="Platemaker-measured transparency (often absent/None for some exposures)",
  PMSEEING="Platemaker-measured seeing",
  GFRAMES="Number of guider frames for this exposure -- matches count(*) from telemetry.guider_centroids for the same expid",
  GUIDECAM="Comma-separated list of active guide cameras, e.g. GUIDE0,GUIDE2,GUIDE3,GUIDE5,GUIDE7,GUIDE8",
  GUIDER="jsonb-like summary block embedded in the header: gframes, gseeing, gduration, mean pointing corrections",
  GUIDTIME="Guiding duration (s)",
  EXPFRAME="Guider frame index at exposure start (?)",
  )

d("coords",
  POS_X="Fiber X position, focal-plane coords", POS_Y="Fiber Y position, focal-plane coords",
  POS_Q="Fiber positioner theta arm angle", POS_S="Fiber positioner phi arm angle",
  POS_LINPHI="Whether this positioner's phi arm is in the 'linear' calibration regime",
  POS_FLAGS="Positioner status bitmask",
  FIBER_RA="Fiber pointing RA (deg)", FIBER_DEC="Fiber pointing Dec (deg)",
  FIBER_X="Fiber X (post-correction)", FIBER_Y="Fiber Y (post-correction)",
  TARGET_RA="Target RA from fiberassign", TARGET_DEC="Target Dec from fiberassign",
  )

d("etc_header",
  ETCTEFF="ETC-estimated effective exposure time (s) at the time reported", ETCREAL="ETC real (elapsed shutter-open) time (s)",
  ETCTRANS="ETC-estimated atmospheric transparency", ETCSKY="ETC-estimated sky brightness",
  ACQFWHM="Acquisition-image FWHM (seeing proxy)",
  ETCSPLIT="Number of cosmic-ray splits ETC has triggered so far",
  ETCPROF="ETC target-brightness profile used (e.g. BGS, ELG)",
  )

d("exposures_daily",
  EXPID="Exposure ID", NIGHT="Observing night (YYYYMMDD)", TILEID="Tile ID observed",
  EXPTIME="Requested exposure time (s)", EFFTIME_SPEC="Pipeline-measured effective spectroscopic time (s) -- what exposure_table/exposure-qa's EFFTIME should closely match",
  PROGRAM="Survey program (dark/bright/backup/other)", AIRMASS_GFA="Airmass from GFA analysis",
  SEEING_GFA="Seeing from (older/different) GFA analysis -- compare to gfa_row['FWHM_ASEC'] from the newer offline GFA pipeline",
  TSNR2_ELG="Per-exposure total (summed across petals/arms) ELG template S/N^2 -- same metric as PETALQA's TSNR2_ELG_{B,R,Z} but pre-aggregated",
  TSNR2_QSO="Per-exposure total QSO template S/N^2", TSNR2_LRG="Per-exposure total LRG template S/N^2",
  TSNR2_LYA="Per-exposure total LYA template S/N^2", TSNR2_BGS="Per-exposure total BGS template S/N^2",
  )

d("exposure_table",
  LASTSTEP="Closed vocabulary (desispec.workflow.exptable.get_last_step_options): ignore, skysub, stdstarfit, fluxcal, all -- how far the pipeline processed this exposure",
  CAMWORD="Which cameras exist, compact 'a'+spectrograph-number encoding (desispec.io.util.create_camword)",
  BADCAMWORD="Same encoding, cameras excluded from processing",
  BADAMPS="Comma-separated '{camera}{petal}{amp}' entries, e.g. 'b7D,z8A' (desispec.io.util.parse_badamps)",
  EXPFLAG="Closed vocabulary (get_exposure_flags): good, extra_cal, low_flux, short_exposure, low_sn, low_speed, aborted, metadata_missing, metadata_mismatch, misconfig_cal, misconfig_petal, off_target, no_stdstars, test, corrupted, junk, bad",
  HEADERERR="'key:->value' metadata corrections applied to this exposure's row, e.g. 'SEQTOT:->1'",
  COMMENTS="Free-form human notes -- confirmed NOT used by the pipeline itself, deliberately excluded from Exposure.exposure_table_flags",
  OBSTYPE="Observation type incl. calibration frames: zero, dark, arc, flat, science (not present in exposures-daily.csv, which is science-only)",
  )

d("db_row",
  id="Exposure ID (primary key)", night="Observing night", date_obs="Shutter-open timestamp (timestamptz) -- primary source for Exposure.time_window",
  exptime="Requested exposure time (s)", sequence="Exposure sequence type (e.g. DESI)", tileid="Tile ID",
  skyra="Sky-pointing RA", skydec="Sky-pointing Dec", mountaz="Mount azimuth", mountel="Mount elevation", mountha="Mount hour angle",
  airmass="Airmass", program="Survey program", obstype="Observation type",
  seeing="Seeing estimate (source/timing vs. pmseeing/etcseeing not fully disambiguated)",
  pmseeing="Platemaker-measured seeing", etcseeing="ETC-measured seeing",
  posrms="Fiber positioner RMS (real-time telemetry) -- confirmed distinct from fiberqa['FPRMS2D'] (post-hoc QA), different values for the same exposure",
  turbrms="Turbulence RMS component of positioning",
  totteff="Total accumulated effective time (ETC real-time estimate) -- confirmed distinct from redux_row['EFFTIME_SPEC'] (post-hoc pipeline measurement), different values for the same exposure",
  reqteff="Requested effective time (s)",
  winddir="Wind direction -- often None/unpopulated even when the FITS header has a value; prefer header for this field",
  windspd="Wind speed -- same caveat as winddir",
  gust="Wind gust -- same caveat",
  pmirtemp="Primary mirror temperature -- same caveat, often None in DB row even when header has it",
  guider="jsonb block: guider-related summary for this exposure",
  tcs="jsonb block: telescope control system state",
  etc="jsonb block: ETC summary for this exposure",
  )

# Confirmed live against the DB (2026-07-20) -- see docs/FIELDS.md's exposure.exposure
# section for the full write-up. Appended to DESC's own text for these two fields.
DESC[("db_row", "rotrate")] = (
    DESC.get(("db_row", "rotrate"), "")
    + " **Confirmed dead: only 1 non-null value across the entire exposure.exposure "
    "table's full history (2019-2026)** -- a known bug in the online ingestion code, "
    "not yet fixed. Use `db_row['hexapod']['rot_rate']` instead (same physical "
    "quantity, different key name -- confirmed matching the FITS header's ROTRATE "
    "for a spot-checked exposure); not universal either, since `hexapod` isn't "
    "populated for every exposure sequence."
).strip()
DESC[("db_row", "rotoffst")] = (
    DESC.get(("db_row", "rotoffst"), "")
    + " **Confirmed dead: 0 non-null values across the entire exposure.exposure "
    "table.** No known populated DB-resident substitute -- use `header.ROTOFFST` "
    "(requires opening the FITS file)."
).strip()
DESC[("db_row", "mountha")] = (
    (DESC.get(("db_row", "mountha"), "").rstrip(".") + ".") if DESC.get(("db_row", "mountha")) else ""
) + (
    " Confirmed to sometimes differ from `db_row['tcs']['mount_ha']` for the same "
    "exposure (e.g. 0.204 vs. 0.383) -- distinct measurement snapshots, not "
    "interchangeable."
)

d("guider_centroids",
  expid="Exposure ID", frame="Guider frame number within the exposure (1-indexed)",
  time_recorded="DB insert timestamp", obstime="Guider frame observation timestamp",
  seeing="Per-frame seeing estimate", nstars="Number of guide stars used this frame",
  ngfas="Number of GFA cameras contributing this frame",
  combined_x="Combined guiding correction, X (arcsec or similar)", combined_y="Combined guiding correction, Y",
  tcs_correction_ra="RA correction sent to TCS this frame", tcs_correction_dec="Dec correction sent to TCS this frame",
  rotation="Field rotation estimate", pixel_scale="Plate scale (arcsec/pixel)",
  guiding="Whether active guiding was engaged this frame", send_guide_corrections="Whether corrections were actually sent to the TCS",
  )

d("environmentmonitor_telescope",
  air_temp="Air temperature at telescope", mirror_temp="Primary mirror temperature",
  mirror_avg_temp="Average mirror temperature across sensors", mirror_desired_temp="Mirror thermal control setpoint",
  wind_shake="Wind-shake event flag/count", wind_gust="Wind-gust event flag/count",
  time_recorded="Telemetry timestamp (timestamptz) -- the time_column used by query_nearest/query_window",
  between_twilight="Whether this record falls between evening/morning twilight",
  )

d("environmentmonitor_tower",
  wind_speed="Wind speed at the tower anemometer", wind_direction="Wind direction",
  gust="Gust speed", tower_timestamp="Tower-side timestamp (text, distinct format from time_recorded)",
  time_recorded="Telemetry timestamp (timestamptz) -- used for nearest/window queries",
  )

d("environmentmonitor_dust",
  mayall_particle_1_micron_5="Mayall dust sensor 1, particle count >=5 micron. Table only has data from 2025-10-21 onward -- always pass max_delta_seconds when querying older exposures",
  mayall_particle_1_timestamp="Per-sensor text timestamp -- prefer time_recorded for consistency across telemetry tables",
  time_recorded="Telemetry timestamp (timestamptz)",
  )

d("cframe_fibermap",
  TARGETID="Unique target identifier", PETAL_LOC="Petal (spectrograph unit) number 0-9",
  DEVICE_LOC="Positioner device location within the petal", LOCATION="PETAL_LOC*1000+DEVICE_LOC (confirmed identity)",
  FIBER="Fiber number -- confirmed to be the actual row-order key (sorted ascending), not DEVICE_LOC",
  OBJTYPE="Object type classification", MORPHTYPE="Photometric morphology classification (e.g. PSF)",
  GAIA_PHOT_G_MEAN_MAG="Gaia G-band magnitude, used e.g. to select bright stars in linphi_splitflux.ipynb",
  DESI_TARGET="Targeting bitmask, main DARK/BRIGHT survey -- includes STD_FAINT/STD_WD/STD_BRIGHT standard-star bits; decode with desitarget.targetmask.desi_mask",
  BGS_TARGET="BGS-specific targeting bitmask; decode with desitarget.targetmask.bgs_mask",
  MWS_TARGET="MWS-specific targeting bitmask -- also where BACKUP-program exposures (program='BACKUP') flag their standard stars (GAIA_STD_FAINT/GAIA_STD_WD/GAIA_STD_BRIGHT) instead of DESI_TARGET -- confirmed real: a BACKUP exposure had 0/297 calibstars fibers match DESI_TARGET's STD bits, 297/297 match MWS_TARGET's GAIA_STD bits instead; decode with desitarget.targetmask.mws_mask",
  SCND_TARGET="Secondary-program targeting bitmask; decode with desitarget.targetmask.scnd_mask",
  )

d("cframe_scores",
  MEDIAN_CALIB_COUNT_Z="Median calibrated flux count, z camera (used by linphi_splitflux.ipynb)",
  MEDIAN_CALIB_SNR_Z="Median calibrated S/N, z camera",
  TSNR2_BGS_Z="BGS template S/N^2 contribution, this fiber, z arm",
  )

d("gfa_row",
  EXPID="Exposure ID", NIGHT="Observing night", EXPTIME="Guider's own per-frame exposure time (s) -- NOT the spectrograph EXPTIME, can differ substantially (e.g. 5s guider frame during a much longer science exposure)",
  FWHM_ASEC="Seeing FWHM (arcsec) -- confirmed NaN-free across all of EXPOSURE_SUMMARY_STRICT",
  TRANSPARENCY="Atmospheric transparency estimate",
  MOON_ILLUMINATION="Fraction of the Moon illuminated (0-1)", MOON_ZD_DEG="Moon zenith distance (deg)", MOON_SEP_DEG="Moon-target angular separation (deg)",
  FIBERFAC="Fiber acceptance fraction (point source)", FIBERFAC_ELG="Fiber acceptance fraction, ELG profile", FIBERFAC_BGS="Fiber acceptance fraction, BGS profile",
  FIBER_FRACFLUX="Fraction of flux captured within a fiber (point source)",
  SKY_MAG_AB="Sky brightness, AB mag/arcsec^2",
  KTERM="Extinction k-term used",
  )

d("fiberqa",
  NGOODFIB="Number of fibers passing QA", NGOODPET="Number of petals passing QA",
  WORSTRDN="Worst (highest) CCD read noise across all cameras for this exposure",
  FPRMS2D="Fiber positioning RMS (2D), post-hoc QA -- confirmed distinct from db_row['posrms']",
  EFFTIME="Pipeline effective time -- confirmed near-identical to redux_row['EFFTIME_SPEC'] for the same exposure",
  SKY_MAG_G_SPEC="Whole-exposure sky brightness, g band, AB mag/arcsec^2 (distinct from PETALQA's per-petal SKY_MAG_G_SPEC)",
  SKY_MAG_R_SPEC="Whole-exposure sky brightness, r band", SKY_MAG_Z_SPEC="Whole-exposure sky brightness, z band",
  )

d("fiberqa_table",
  TARGETID="Unique target identifier", PETAL_LOC="Petal (spectrograph unit) number 0-9",
  DEVICE_LOC="Positioner device location within the petal", LOCATION="PETAL_LOC*1000+DEVICE_LOC",
  FIBER="Fiber number, 0-4999 across the whole focal plane (not per-camera like cframe's FIBERMAP)",
  TARGET_RA="Target RA (deg)", TARGET_DEC="Target Dec (deg)",
  FIBER_X="Fiber X position (post-correction)", FIBER_Y="Fiber Y position (post-correction)",
  DELTA_X="Positioning residual, X", DELTA_Y="Positioning residual, Y",
  EBV="Galactic extinction E(B-V) at this target",
  QAFIBERSTATUS="Per-fiber QA status bitmask (0 = good) -- this is the per-fiber detail behind the exposure-level NGOODFIB/NGOODPET summary",
  EFFTIME_SPEC="Per-fiber effective spectroscopic time (s) -- finer-grained than the whole-exposure EFFTIME in the FIBERQA header",
  )

d("petalqa",
  PETAL_LOC="Petal (spectrograph unit) number 0-9",
  WORSTREADNOISE="Worst (highest) CCD read noise across this petal's cameras",
  NGOODPOS="Number of fiber positioners passing QA on this petal",
  NGOODFIB="Number of fibers passing QA on this petal -- per-petal detail behind the exposure-level FIBERQA NGOODFIB total",
  NSTDSTAR="Number of standard stars used for flux calibration on this petal",
  STARRMS="RMS scatter of standard-star flux calibration residuals on this petal",
  EFFTIME_SPEC="Effective spectroscopic time for this petal (s)",
  NCFRAME="Number of cframes (exposure sequence coadds) combined for this petal",
  BSKYTHRURMS="Sky-fiber throughput RMS, b camera", RSKYTHRURMS="Sky-fiber throughput RMS, r camera", ZSKYTHRURMS="Sky-fiber throughput RMS, z camera",
  BSKYCHI2PDF="Sky-subtraction chi^2/dof, b camera", RSKYCHI2PDF="Sky-subtraction chi^2/dof, r camera", ZSKYCHI2PDF="Sky-subtraction chi^2/dof, z camera",
  BTHRUFRAC="Median throughput fraction, b camera", RTHRUFRAC="Median throughput fraction, r camera", ZTHRUFRAC="Median throughput fraction, z camera",
  SKY_MAG_G_SPEC="Per-petal sky brightness, g band, AB mag/arcsec^2 (distinct from FIBERQA's whole-exposure SKY_MAG_G_SPEC)",
  SKY_MAG_R_SPEC="Per-petal sky brightness, r band", SKY_MAG_Z_SPEC="Per-petal sky brightness, z band",
  )
for _tracer in ("ELG", "QSO", "LRG", "LYA", "BGS", "GPBDARK", "GPBBRIGHT", "GPBBACKUP"):
    for _band in ("B", "R", "Z"):
        DESC[("petalqa", f"TSNR2_{_tracer}_{_band}")] = (
            f"Per-petal {_tracer} template S/N^2, {_band} camera -- same metric as the whole-exposure "
            f"TSNR2_{_tracer} total in redux_row/exposures-daily.csv, but per petal rather than summed"
        )

d("calibstars",
  FIBER="Whole-focal-plane fiber number, 0-4999 -- same numbering as cframe_table/fiberqa_table's FIBER column, "
        "but NOT the (PETAL_LOC, DEVICE_LOC) index used elsewhere in this project (FIBER // 500 == PETAL_LOC "
        "always holds; DEVICE_LOC has no formula and needs a join against fiberqa_table/cframe_table)",
  RCALIBFRAC="Ratio of r-band spectroscopic flux to model flux for this standard star (confirmed via the "
             "official DESI datamodel docs)",
  EBV="Galactic extinction E(B-V) reddening from SFD98",
  MODEL_COLOR="G-R color of the best-fit model for this star",
  DATA_COLOR="G-R color measured from the data for this star",
  X="Focal-plane X position (mm)", Y="Focal-plane Y position (mm)",
  VALID="Whether this standard star was selected as good (1) for the flux calibration fit -- rejected (0) if "
        "a 3-sigma RCALIBFRAC outlier across petals, or if its G-R color differs from the model by more than "
        "0.2*EBV",
  )

d("fiberassign_table",
  TARGETID="Unique target identifier", PETAL_LOC="Petal (spectrograph unit) number 0-9",
  DEVICE_LOC="Positioner device location within the petal", LOCATION="PETAL_LOC*1000+DEVICE_LOC",
  FIBER="Fiber number, 0-4999 across the whole focal plane -- same numbering as cframe_table/fiberqa_table/calibstars's FIBER",
  TARGET_RA="Target RA (deg)", TARGET_DEC="Target Dec (deg)",
  FA_TARGET="Raw fiberassign target bitmask used at assignment time",
  DESI_TARGET="Targeting bitmask, main DARK/BRIGHT survey -- includes STD_FAINT/STD_WD/STD_BRIGHT standard-star bits",
  BGS_TARGET="BGS-specific targeting bitmask",
  MWS_TARGET="MWS-specific targeting bitmask -- also where BACKUP-program exposures (program='BACKUP') flag their "
             "standard stars (GAIA_STD_FAINT/GAIA_STD_WD/GAIA_STD_BRIGHT) instead of DESI_TARGET -- confirmed real, "
             "not hypothetical (see notebooks/calibstars_linphi.ipynb)",
  SCND_TARGET="Secondary-program targeting bitmask",
  )

# Generic FITS/table boilerplate keywords not specific to DESI -- not worth
# looking up in an instrument-specific comments file.
d("header",
  XTENSION="FITS extension type (e.g. BINTABLE, IMAGE)", BITPIX="Bits per pixel/data value",
  PCOUNT="Number of parameter bytes (FITS table heap size)", GCOUNT="Number of FITS groups (always 1 for a table)",
  TFIELDS="Number of table columns", BZERO="Zero-point offset for scaled data", BSCALE="Scale factor for scaled data",
  CHECKSUM="FITS file checksum", DATASUM="Checksum of the data unit only",
  ZCMPTYPE="FITS tile-compression algorithm used", ZNAME1="Tile-compression parameter 1 name",
  ZVAL1="Tile-compression parameter 1 value", ZNAME2="Tile-compression parameter 2 name", ZVAL2="Tile-compression parameter 2 value",
  )

# ---------------------------------------------------------------------------
# Fill in blanks (only) for the main FITS header from ~/fitsheader.py, a file
# the user supplied containing official descriptive comments that -- per the
# user -- didn't make it into the actual FITS files. Only fills keys we don't
# already have a hand-written description for, so project-specific notes
# (e.g. "confirmed distinct from db_row['posrms']") are never overwritten.
# ---------------------------------------------------------------------------
def _load_external_fits_comments(path="/global/homes/k/klaushon/fitsheader.py"):
    import os

    if not os.path.exists(path):
        return {}
    ns = {}
    exec(open(path).read(), ns)
    return dict(ns.get("FITS_COMMENTS", {}))


_EXTERNAL_HEADER_COMMENTS = _load_external_fits_comments()
_external_fill_count = 0
for _key, _comment in _EXTERNAL_HEADER_COMMENTS.items():
    if ("header", _key) not in DESC:
        DESC[("header", _key)] = _comment
        _external_fill_count += 1


def get_header(path, ext):
    with fitsio.FITS(path) as f:
        h = f[ext].read_header()
        return {k: h[k] for k in h.keys() if k}


def get_table_cols_and_row(path, ext):
    with fitsio.FITS(path) as f:
        data = f[ext].read()
    return data.dtype.names, {name: data[name][0] for name in data.dtype.names}


# === Main FITS header ===
section("Exposure directory: `desi-<expid>.fits.fz` header (`SPEC` extension)",
        f"Live example: expid {EXPID}, night {NIGHT}. {{n}} keys total; most descriptions below come from "
        f"`fitsheader.py` (official comments the user supplied -- {_external_fill_count} keys filled in from it -- "
        "these don't actually appear in the real FITS files, for reasons unknown). A handful with project-specific "
        "notes (e.g. cross-checked against another source) were written by hand and take priority over that file.")
main_fits = f"/global/cfs/cdirs/desi/spectro/data/{NIGHT}/{EXPID:08d}/desi-{EXPID:08d}.fits.fz"
header = get_header(main_fits, "SPEC")
OUT[-1] = OUT[-1].replace("{n}", str(len(header)))
_described = sum(1 for k in header if DESC.get(("header", k)))
OUT[-1] = OUT[-1].replace(f"-- {_external_fill_count} keys filled in from it --",
                          f"-- {_described}/{len(header)} keys here have one --")
rows = [(k, type(v).__name__, DESC.get(("header", k), ""), truncate(v), src("header", k)) for k, v in sorted(header.items())]
table(rows)

# === coordinates file ===
section("Exposure directory: `coordinates-<expid>.fits` (`DATA` extension)",
        "One row per fiber, indexed by (PETAL_LOC, DEVICE_LOC) once read via `fits_io.read_coordinates`.")
coords_path = f"/global/cfs/cdirs/desi/spectro/data/{NIGHT}/{EXPID:08d}/coordinates-{EXPID:08d}.fits"
with fitsio.FITS(coords_path) as f:
    coords = f["DATA"].read()
rows = [(name, str(coords.dtype[name]), DESC.get(("coords", name), ""), truncate(coords[name][0]), src("coords", name)) for name in coords.dtype.names]
table(rows)

# === ETC json ===
section("Exposure directory: `etc-<expid>.json` -- `header` block (scalar ETC summary)",
        "Full file also has expinfo/fassign/acquisition/guide_stars blocks (nested, exposure-setup info) and shutter/thru/sky/accum time-series blocks (parallel lists, one entry per ETC update) -- not flattened here; see `Exposure.etc`/`etc_timeseries(key)`.")
etc_path = f"/global/cfs/cdirs/desi/spectro/data/{NIGHT}/{EXPID:08d}/etc-{EXPID:08d}.json"
etc = json.load(open(etc_path))
rows = [(k, type(v).__name__, DESC.get(("etc_header", k), ""), truncate(v), src("etc_header", k)) for k, v in sorted(etc.get("header", {}).items())]
table(rows)

# === centroids.json ===
section("Exposure directory: `centroids-<expid>.json`",
        "Not a flat table -- top-level scalar fields (`expid`, `status`, `started_at`/`ended_at`, `target_ra`/`target_dec`, `mount_ha`/`mount_dec`), a `summary` dict (whole-exposure guiding stats: `duration`, `seeing`, `frames`, `meanx`/`meany`/etc.), and a `frames` dict keyed by frame number (1-indexed as *strings*) -- each frame's content is the file-based counterpart of one `telemetry.guider_centroids` row (same fields: `combined_x`/`combined_y`/`seeing`/`nstars`/`ngfas`/`tcs_correction_ra`/`tcs_correction_dec`/`guiding`, plus per-GFA-camera `GUIDE{n}_{0,1}` sub-blocks). `Exposure.centroids` returns this whole structure as-is (not parsed further); `Exposure.guider_centroids` (DB) is the preferred, already-structured equivalent.")

# === exposures-daily.csv ===
section("Offline QA: `exposures-daily.csv`",
        f"Live example row: expid {EXPID}. Full schema, one row per (science) exposure.")
daily = pd.read_csv(CFG.exposures_daily_csv)
daily_row = daily[daily["EXPID"] == EXPID].iloc[0] if (daily["EXPID"] == EXPID).any() else None
rows = []
for col in daily.columns:
    example = daily_row[col] if daily_row is not None else ""
    rows.append((col, str(daily[col].dtype), DESC.get(("exposures_daily", col), ""), truncate(example), src("exposures_daily", col)))
table(rows)

# === exposure_table CSV ===
section("Offline QA: `exposure_table_<night>.csv`",
        "One row per exposure that night, including calibration frames. Field definitions from `desispec.workflow.exptable` (installed pipeline source), not just docstrings." + NOTE_EXPOSURE_TABLE)
et_path = f"/global/cfs/cdirs/desi/spectro/redux/daily/exposure_tables/{str(NIGHT)[:6]}/exposure_table_{NIGHT}.csv"
et = pd.read_csv(et_path)
et_row = et[et["EXPID"] == EXPID].iloc[0] if (et["EXPID"] == EXPID).any() else et.iloc[0]
rows = [(col, str(et[col].dtype), DESC.get(("exposure_table", col), ""), truncate(et_row[col]), src("exposure_table", col)) for col in et.columns]
table(rows)

# === tiles-daily.csv ===
section("Offline QA: `tiles-daily.csv`", NOTE_TILES_DAILY)
tiles = pd.read_csv(CFG.redux_root / "daily" / "tiles-daily.csv")
example_tile = tiles.iloc[0]
rows = [(col, str(tiles[col].dtype), "", truncate(example_tile[col]), src("tiles_daily", col)) for col in tiles.columns]
table(rows)

# === exposure.exposure DB table ===
section("Database: `exposure.exposure`",
        f"187 columns, one row per exposure. Live example: expid {EXPID}. Only columns with a known/discussed meaning have a description -- the rest are listed for completeness with a real example value.")
cols = db.fetch_all(CFG, "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='exposure' AND table_name='exposure' ORDER BY ordinal_position")
row = db.fetch_one(CFG, "SELECT * FROM exposure.exposure WHERE id = %s LIMIT 1", (EXPID,))
rows = [(c["column_name"], c["data_type"], DESC.get(("db_row", c["column_name"]), ""), truncate(row.get(c["column_name"]) if row else ""), src("db_row", c["column_name"])) for c in cols]
table(rows)

# === exposure.stars / comments / positions / headers ===
for tname in ["stars", "comments", "positions", "headers"]:
    _note = note_unexposed_db(f"exposure.{tname}") if tname in ("positions", "headers") else ""
    section(f"Database: `exposure.{tname}`", _note)
    cols = db.fetch_all(CFG, "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='exposure' AND table_name=%s ORDER BY ordinal_position", (tname,))
    rows = [(c["column_name"], c["data_type"], "", "", src(tname, c["column_name"])) for c in cols]
    table(rows)

# === telemetry tables actually used ===
for tname in ["guider_centroids", "environmentmonitor_telescope", "environmentmonitor_tower", "environmentmonitor_dust"]:
    _note = NOTE_GUIDER if tname == "guider_centroids" else note_telemetry(tname)
    section(f"Database: `telemetry.{tname}`", _note)
    cols = db.fetch_all(CFG, "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='telemetry' AND table_name=%s ORDER BY ordinal_position", (tname,))
    example = db.fetch_one(CFG, f"SELECT * FROM telemetry.{tname} ORDER BY time_recorded DESC LIMIT 1")
    rows = [(c["column_name"], c["data_type"], DESC.get((tname, c["column_name"]), ""), truncate(example.get(c["column_name"])) if example else "", src(tname, c["column_name"])) for c in cols]
    table(rows)
OUT.append("\n*(93 tables total in the `telemetry` schema -- only the ones this project actually queries are listed here. "
           "To inspect another: `SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='telemetry' AND table_name='...'` "
           "via `telemetry_mining.db.fetch_all`.)*\n")

# === cframe FIBERMAP / SCORES ===
cframe_path = f"/global/cfs/cdirs/desi/spectro/redux/daily/exposures/{NIGHT}/{EXPID:08d}/cframe-z3-{EXPID:08d}.fits.gz"
section("Offline per-camera spectra: cframe `FIBERMAP` extension", f"Live example: camera z3, expid {EXPID}." + NOTE_CFRAME)
names, example = get_table_cols_and_row(cframe_path, "FIBERMAP")
rows = [(name, "", DESC.get(("cframe_fibermap", name), ""), truncate(example[name]), src("cframe_fibermap", name)) for name in names]
table(rows)

section("Offline per-camera spectra: cframe `SCORES` extension", "Row-aligned with FIBERMAP (no location columns of its own -- see project memory)." + NOTE_CFRAME)
names, example = get_table_cols_and_row(cframe_path, "SCORES")
rows = [(name, "", DESC.get(("cframe_scores", name), ""), truncate(example[name]), src("cframe_scores", name)) for name in names]
table(rows)

# === GFA offline summary ===
section("Offline GFA summary: `EXPOSURE_SUMMARY_STRICT` extension")
gfa_files = sorted(CFG.gfa_root.glob("offline_matched_coadd_ccds_main-thru_*.fits"))
gfa_path = str(gfa_files[-1])
names, example = get_table_cols_and_row(gfa_path, "EXPOSURE_SUMMARY_STRICT")
rows = [(name, "", DESC.get(("gfa_row", name), ""), truncate(example[name]), src("gfa_row", name)) for name in names]
table(rows)

# === FIBERQA / PETALQA ===
# FIBERQA is NOT just a small header -- confirmed by reading the actual table data (not
# just read_header()) that it's a 5000-row (one per fiber, whole focal plane) x 14-column
# binary table, with the scalar QA summary keys sitting as *extra* header keywords
# alongside the required TTYPE/TFORM/DEPNAM/DEPVER/CHECKSUM FITS boilerplate. Anand's
# message said "e.g." before listing 5 keys -- that was illustrative, not exhaustive.
qa_path = f"/global/cfs/cdirs/desi/spectro/redux/daily/exposures/{NIGHT}/{EXPID:08d}/exposure-qa-{EXPID:08d}.fits"

_BOILERPLATE_PREFIXES = ("TTYPE", "TFORM", "DEPNAM", "DEPVER")
_BOILERPLATE_EXACT = {"XTENSION", "BITPIX", "NAXIS", "NAXIS1", "NAXIS2", "PCOUNT", "GCOUNT",
                      "TFIELDS", "EXTNAME", "CHECKSUM", "DATASUM"}
_DUPLICATE_ELSEWHERE = {"NIGHT", "EXPID", "TILEID", "EXPTIME", "MJD-OBS", "TARGTRA", "TARGTDEC",
                        "MOUNTEL", "MOUNTHA", "AIRMASS", "ETCTEFF", "ACQFWHM", "TILERA", "TILEDEC",
                        "GOALTIME", "GOALTYPE", "FAPRGRM", "SURVEY", "EBVFAC", "MINTFRAC", "FAFLAVOR"}

full_header = get_header(qa_path, "FIBERQA")
scalar_keys = {
    k: v for k, v in full_header.items()
    if not k.startswith(_BOILERPLATE_PREFIXES) and k not in _BOILERPLATE_EXACT and k not in _DUPLICATE_ELSEWHERE
}

section("Offline per-exposure QA: `exposure-qa-<expid>.fits` -- `FIBERQA` header (scalar QA summary)",
        f"**Correction to an earlier assumption in this project**: `FIBERQA` is not just these ~{len(scalar_keys)} scalar "
        f"keys -- see the table below this one. The header also repeats ~{len(_DUPLICATE_ELSEWHERE)} exposure-metadata "
        "keys already available elsewhere (NIGHT/EXPID/TILEID/EXPTIME/pointing/AIRMASS/etc.) -- omitted here as duplicates." + NOTE_FIBERQA)
rows = [(k, type(v).__name__, DESC.get(("fiberqa", k), ""), truncate(v), src("fiberqa", k)) for k, v in scalar_keys.items()]
table(rows)

section("Offline per-exposure QA: `exposure-qa-<expid>.fits` -- `FIBERQA` table (per-fiber QA)",
        "5000 rows -- one per fiber across the **whole focal plane** (not per-camera like cframe's 500-row FIBERMAP). "
        "Available as `Exposure.fiberqa_table` (DataFrame indexed by (PETAL_LOC, DEVICE_LOC), same shape as `cframe_table`).")
names, example = get_table_cols_and_row(qa_path, "FIBERQA")
rows = [(name, str(example[name].dtype) if hasattr(example[name], "dtype") else type(example[name]).__name__,
         DESC.get(("fiberqa_table", name), ""), truncate(example[name]), src("fiberqa_table", name)) for name in names]
table(rows)

section("Offline per-exposure QA: `exposure-qa-<expid>.fits` -- `PETALQA` table",
        "10 rows (one per petal). Available as `Exposure.petalqa` (DataFrame indexed by PETAL_LOC). Most columns "
        "(NGOODPOS/NGOODFIB/NSTDSTAR/WORSTREADNOISE/STARRMS/NCFRAME and the per-petal sky/throughput RMS+chi2 "
        "columns) are genuinely new detail not available elsewhere in this project; the TSNR2_*/SKY_MAG_*_SPEC "
        "columns duplicate exposure-level totals already in `redux_row`/`exposures-daily.csv` (same metric, summed "
        "across petals) -- prefer those for the whole-exposure number.")
names, example = get_table_cols_and_row(qa_path, "PETALQA")
rows = [(name, str(example[name].dtype) if hasattr(example[name], "dtype") else type(example[name]).__name__,
         DESC.get(("petalqa", name), ""), truncate(example[name]), src("petalqa", name)) for name in names]
table(rows)

# === calibstars ===
# Suggested by the data-systems team as a source for linphi-vs-regular-positioner
# calibration-quality studies -- a plain CSV, not FITS, one row per standard star.
calibstars_path = f"/global/cfs/cdirs/desi/spectro/redux/daily/exposures/{NIGHT}/{EXPID:08d}/calibstars-{EXPID:08d}.csv"
calibstars_df = pd.read_csv(calibstars_path)
section("Offline per-exposure QA: `calibstars-<expid>.csv` -- standard-star flux calibration table",
        f"{len(calibstars_df)} rows (one per spectrophotometric standard star used for flux calibration). "
        "Available as `Exposure.calibstars` (DataFrame indexed by FIBER). FIBER is the whole-focal-plane "
        "0-4999 numbering (same as cframe_table/fiberqa_table's FIBER column) -- `FIBER // 500 == PETAL_LOC` "
        "always holds, but DEVICE_LOC has no formula and needs a join against `fiberqa_table`/`cframe_table` "
        "(both already carry FIBER alongside the (PETAL_LOC, DEVICE_LOC) index). Also available under other "
        "specprods (e.g. `redux_release='matterhorn'`), same directory/naming convention as cframe.")
example_row = calibstars_df.iloc[0]
rows = [(name, str(example_row[name].__class__.__name__), DESC.get(("calibstars", name), ""), truncate(example_row[name]), src("calibstars", name))
        for name in calibstars_df.columns if name != "FIBER"]
rows = [("FIBER", "int64", DESC.get(("calibstars", "FIBER"), ""), truncate(calibstars_df["FIBER"].iloc[0]), src("calibstars", "FIBER"))] + rows
table(rows)

# === fiberassign table ===
# Lives in the raw exposure directory (exposures_root), not the redux tree -- full history at
# NERSC, unlike cframe/calibstars/exposure-qa's rolling redux retention. Much faster than
# cframe_table for targeting-bitmask-only lookups: one whole-focal-plane file instead of
# looping every petal.
tileid = header.get("TILEID")
fa_path = f"/global/cfs/cdirs/desi/spectro/data/{NIGHT}/{EXPID:08d}/fiberassign-{tileid:06d}.fits.gz"
section("Exposure directory: `fiberassign-<tileid>.fits.gz` -- `FIBERASSIGN` extension",
        "5000 rows -- one per fiber across the **whole focal plane** (not per-petal like cframe's 500-row "
        "FIBERMAP). Available as `Exposure.fiberassign_table` (DataFrame indexed by (PETAL_LOC, DEVICE_LOC)). "
        "Carries the same targeting bitmasks as cframe's FIBERMAP (DESI_TARGET/BGS_TARGET/MWS_TARGET/SCND_TARGET) "
        "but in a single fast read -- confirmed ~60x faster than looping `cframe_table` over every petal for the "
        "same columns (~0.14s vs. ~9s per exposure).")
names, example = get_table_cols_and_row(fa_path, "FIBERASSIGN")
rows = [(name, str(example[name].dtype) if hasattr(example[name], "dtype") else type(example[name]).__name__,
         DESC.get(("fiberassign_table", name), ""), truncate(example[name]), src("fiberassign_table", name)) for name in names]
table(rows)


print("\n".join(OUT))
