"""The unified per-exposure accessor.

`Exposure(expid)` lazily resolves and exposes everything associated with one
DESI exposure: FITS header, fiber coordinates, ETC summary, guider metadata,
the condensed per-exposure DB record, a telemetry time-window query, and the
offline QA row -- so downstream analyses can be written against one object
instead of hand-rolling file paths and SQL per script.

Construction does zero I/O. Passing `night` explicitly lets every
file-based accessor (header/coords/etc/centroids/redux_row) work without any
DB access; only db_row/stars/comments/telemetry()/auto-resolved night touch
the database, so filesystem and DB failures stay independent of each other.
"""

from __future__ import annotations

import datetime as dt
import json
from functools import cached_property
from pathlib import Path
from typing import Optional, Sequence

from . import db, etc as etc_mod, gfa, paths as paths_mod, redux, tables, telemetry
from .config import Config
from .exceptions import DataSourceUnavailableError, ExposureNotFoundError
from .fits_io import (
    read_coordinates,
    read_fibermap,
    read_fibermap_and_scores,
    read_fiberassign_table,
    read_fiberqa_table,
    read_header,
    read_petalqa,
    read_scores,
    read_stationary,
)
from .tables import TableSource

# alarms.alarms columns worth exposing (the boolean alarm-handler routing flags,
# acknowledgement bookkeeping, etc. are deliberately omitted -- see Exposure.alarms).
DEFAULT_ALARM_COLUMNS = ("id", "time_recorded", "level", "component", "instance", "message")


def _read_cframe_camera(expid: int, night: int, config: Config, camera: str):
    """Top-level (picklable) worker for Exposure.cframe_tables's process pool.

    Must be a module-level function, not a method or closure -- multiprocessing
    pickles the callable by reference (module + qualified name), and a bound
    method or closure over `self` can't round-trip that way. Re-resolving a
    fresh Exposure here (instead of trying to pickle `self` across) also
    sidesteps needing this Exposure's own possibly-unpicklable/stateful caches
    (e.g. a live DB connection) to survive the trip -- `night` is passed in
    explicitly so no DB access happens inside the worker at all.
    """
    exp = Exposure(expid, night=night, config=config)
    return read_fibermap_and_scores(exp.cframe_path(camera))


def _parse_date_obs(value: str) -> dt.datetime:
    """Parse a FITS DATE-OBS string, tolerating >6 fractional-second digits."""
    if "." in value:
        base, frac = value.split(".", 1)
        frac_digits = "".join(ch for ch in frac if ch.isdigit())[:6].ljust(6, "0")
        value = f"{base}.{frac_digits}"
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def _clean_scalar(value):
    """Normalize pandas' NaN-for-blank-CSV-cell into None.

    A blank exposure_table cell (e.g. an unpopulated BADCAMWORD) reads back
    from pandas as float('nan'), not '' or None -- and bool(float('nan')) is
    True in Python, so leaving it as-is would make `if flags['BADCAMWORD']:`
    silently misread "no bad cameras" as "there is one." `value != value` is
    true only for NaN, so this needs no pandas/numpy import to check.
    """
    if isinstance(value, float) and value != value:
        return None
    return value


def _parse_pipe_list(value) -> list:
    """Parse desispec's exptable array-column convention: entries joined by '|', trailing '|'.

    Empty (no entries) is written as a single '|' character, not an empty
    string -- confirmed against real exposure_table CSV rows, not assumed.
    """
    if value is None:
        return []
    text = str(value)
    if text.endswith("|"):
        text = text[:-1]
    return text.split("|") if text else []


class Exposure:
    """Lazy, cached accessor for all data associated with one DESI exposure."""

    def __init__(
        self,
        expid: int,
        night: Optional[int] = None,
        config: Optional[Config] = None,
        telemetry_fields: Optional[Sequence[telemetry.TelemetryField]] = None,
        table_sources: Optional[Sequence[TableSource]] = None,
    ):
        self.expid = int(expid)
        self._night_arg = night
        self.config = config or Config.default()
        self.telemetry_fields = (
            list(telemetry_fields) if telemetry_fields is not None else list(telemetry.DEFAULT_TELEMETRY_FIELDS)
        )
        seen_names = set()
        for field in self.telemetry_fields:
            if field.name in seen_names:
                raise ValueError(f"Duplicate telemetry field name: {field.name!r}")
            seen_names.add(field.name)
        self.table_sources = (
            list(table_sources) if table_sources is not None else list(tables.DEFAULT_TABLE_SOURCES)
        )
        seen_names = set()
        for source in self.table_sources:
            if source.name in seen_names:
                raise ValueError(f"Duplicate table source name: {source.name!r}")
            seen_names.add(source.name)
        self._telemetry_field_cache: dict = {}
        self._table_source_cache: dict = {}
        self._cframe_fibermap_cache: dict = {}
        self._cframe_scores_cache: dict = {}
        self._cframe_table_cache: dict = {}

    # ---- identity / resolution ----

    @cached_property
    def night(self) -> int:
        if self._night_arg is not None:
            return int(self._night_arg)
        return paths_mod.resolve_night(self.expid, self.config)

    @cached_property
    def directory(self) -> Path:
        directory = paths_mod.exposure_directory(self.expid, self.night, self.config)
        if not directory.exists():
            raise ExposureNotFoundError(self.expid, f"directory does not exist: {directory}")
        return directory

    @cached_property
    def paths(self) -> paths_mod.ExposurePaths:
        return paths_mod.ExposurePaths(self.directory, self.expid)

    # ---- FITS header ----

    @cached_property
    def header(self) -> dict:
        return read_header(self.paths.main_fits)

    def header_value(self, key: str, default=None):
        return self.header.get(key, default)

    # ---- coordinates ----

    @cached_property
    def coords(self):
        return read_coordinates(self.paths.coordinates)

    @cached_property
    def stationary(self):
        return read_stationary(self.paths.coordinates)

    @cached_property
    def fiberassign_table(self):
        """This exposure's FIBERASSIGN table (5000 rows, whole focal plane), or None.

        Reads `fiberassign-<tileid>.fits.gz`'s FIBERASSIGN extension -- a
        single-file, whole-focal-plane read (no per-petal looping needed,
        unlike `cframe_table`) carrying FIBER plus the DESI_TARGET/
        BGS_TARGET/MWS_TARGET/SCND_TARGET targeting bitmasks alongside the
        (PETAL_LOC, DEVICE_LOC) index. Confirmed ~60x faster than looping
        `cframe_table` over every petal for the same columns (~0.14s vs.
        ~0.9s x 10 petals) -- the right source whenever a targeting bitmask
        is all you need, with nothing camera/arm-specific from
        FIBERMAP/SCORES.

        `tileid` comes from the header (no DB round-trip needed). Lives in
        the same raw exposure directory as `coords`/`header`, so it shares
        their retention (full history at NERSC, ~6 months at KPNO) -- not
        cframe/calibstars's separate redux-tree retention.

        Unlike `header` itself (which raises if the main FITS file is
        missing, by design -- see `API.md`), this returns `None` in that
        case too: a caller reaching for `fiberassign_table` wants "is this
        available", not a hard failure, and a missing main FITS file is
        exactly the kind of real, expected-at-scale gap (see "Known
        gotchas") this accessor should degrade gracefully for, the same as
        a missing fiberassign file itself.
        """
        try:
            tileid = self.header.get("TILEID")
        except Exception:
            return None
        if tileid is None:
            return None
        path = self.paths.fiberassign(int(tileid))
        if not path.exists():
            return None
        try:
            return read_fiberassign_table(path)
        except Exception:
            return None

    # ---- ETC ----

    @cached_property
    def etc(self) -> dict:
        return etc_mod.load_etc(self.paths.etc_json)

    @cached_property
    def etc_summary(self) -> dict:
        return etc_mod.etc_summary(self.etc)

    def etc_timeseries(self, key: str):
        return etc_mod.etc_timeseries(self.etc, key)

    # ---- guider ----
    # Deliberately NOT cached_property: guide-<expid>.fits.fz can be GB-scale.
    # These must never be touched by __repr__/summary().

    @cached_property
    def centroids(self) -> dict:
        with open(self.paths.centroids_json) as f:
            return json.load(f)

    @cached_property
    def guider_centroids(self):
        """Per-frame guider centroid telemetry from telemetry.guider_centroids.

        This is DB data (one row per guider frame, keyed by expid/frame), not
        the FITS guider cube -- much faster than reading guide-<expid>.fits.fz
        when only the centroid/seeing/TCS-correction summary is needed.
        """
        columns = [
            "frame",
            "time_recorded",
            "obstime",
            "seeing",
            "nstars",
            "ngfas",
            "combined_x",
            "combined_y",
            "tcs_correction_ra",
            "tcs_correction_dec",
            "rotation",
        ]
        return db.fetch_df(
            self.config,
            f"SELECT {', '.join(columns)} FROM telemetry.guider_centroids WHERE expid = %s ORDER BY frame ASC",
            (self.expid,),
        )

    @cached_property
    def n_guide_frames(self) -> int:
        """Number of guider frames for this exposure.

        Prefers the FITS header's GFRAMES (cheap, no DB access); falls back
        to counting telemetry.guider_centroids rows if GFRAMES isn't present
        -- either because a present header lacks the key, or because the
        FITS file itself is unavailable (e.g. purged on disk at KPNO after
        the exposure ages out, while the DB record remains complete).
        """
        try:
            value = self.header.get("GFRAMES")
        except Exception:
            value = None
        if value is not None:
            return int(value)
        return len(self.guider_centroids)

    def guide_frame(self, frame: int = 0):
        """Open (but don't read) the single-frame or full guider cube FITS file."""
        import fitsio

        path = self.paths.guide_frame0 if frame == 0 else self.paths.guide_cube
        return fitsio.FITS(str(path))

    def guide_cube_path(self) -> Path:
        return self.paths.guide_cube

    # ---- DB record ----

    @cached_property
    def db_row(self) -> dict:
        row = db.fetch_one(
            self.config,
            "SELECT * FROM exposure.exposure WHERE id = %s LIMIT 1",
            (self.expid,),
        )
        if row is None:
            raise ExposureNotFoundError(self.expid, "no matching row in exposure.exposure")
        return row

    @cached_property
    def stars(self):
        return db.fetch_df(
            self.config,
            "SELECT * FROM exposure.stars WHERE expid = %s",
            (self.expid,),
        )

    @cached_property
    def comments(self):
        return db.fetch_df(
            self.config,
            "SELECT * FROM exposure.comments WHERE exposure_id = %s ORDER BY date",
            (self.expid,),
        )

    # ---- telemetry correlation ----

    @cached_property
    def time_window(self) -> tuple[dt.datetime, dt.datetime]:
        """(start, end) of this exposure, from the DB record, falling back to the FITS header.

        The header fallback itself may be unavailable -- e.g. at KPNO,
        exposure files are purged from disk after ~6 months even though the
        DB record persists -- so a failure to read the header is treated the
        same as missing header keys, not left to propagate as a raw
        FITS/OSError.
        """
        try:
            row = self.db_row
            start = row.get("date_obs")
            exptime = row.get("exptime")
            if start is not None and exptime is not None:
                return start, start + dt.timedelta(seconds=float(exptime))
        except Exception:
            pass
        try:
            header = self.header
        except Exception as exc:
            raise ExposureNotFoundError(
                self.expid,
                f"cannot determine time window (no usable DB row, and the FITS header is unavailable: {exc})",
            ) from exc
        date_obs = header.get("DATE-OBS")
        exptime = header.get("EXPTIME")
        if date_obs is None or exptime is None:
            raise ExposureNotFoundError(
                self.expid, "cannot determine time window (no DB row and no usable header keys)"
            )
        start = _parse_date_obs(date_obs)
        return start, start + dt.timedelta(seconds=float(exptime))

    @classmethod
    def at_time(cls, when, *, config: Optional[Config] = None):
        """The exposure open at `when` — the time-based inverse of `time_window`.

        Returns the `Exposure` whose `date_obs` is the latest at or before `when`
        (a tz-aware datetime): the exposure that was running then, or `None` if
        there is no such row. Lets you attach a timestamped event (an alarm, a log
        line) to the exposure it happened during without already knowing an
        exposure id. Whether `when` falls strictly *inside* that exposure (vs. a
        readout gap just after it) is `start <= when <= end` against the returned
        exposure's own `time_window`.

        Hides the DB lookup (one query on `date_obs`); the returned Exposure has
        its `db_row` primed, so accessing it (or `db_row`-backed fields) triggers
        no extra query.

        Performance: this is a *single-timestamp* lookup and orders by `date_obs`,
        which is not the primary key -- so unless `date_obs` is indexed it scans
        `exposure.exposure` per call. Fine for a one-off "what was running then?",
        but do **not** call it in a tight loop over many timestamps; batch that a
        different way (e.g. one range query joined in memory).
        """
        config = config or Config.default()
        row = db.fetch_one(
            config,
            "SELECT * FROM exposure.exposure WHERE date_obs <= %s ORDER BY date_obs DESC LIMIT 1",
            (when,),
        )
        if row is None or row.get("date_obs") is None:
            return None
        night = int(row["night"]) if row.get("night") is not None else None
        exp = cls(int(row["id"]), night=night, config=config)
        exp.__dict__["db_row"] = row  # already fetched -- avoid a redundant per-exposure query
        return exp

    def telemetry(
        self,
        table: str,
        *,
        pad_seconds: float = 0.0,
        columns: Optional[Sequence[str]] = None,
        time_column: str = "time_recorded",
    ):
        """Query a telemetry.<table> for rows within this exposure's time window."""
        start, end = self.time_window
        return telemetry.query_window(
            self.config, table, start, end, pad_seconds=pad_seconds, columns=columns, time_column=time_column
        )

    def alarms(
        self,
        *,
        pad_seconds: float = 0.0,
        level: Optional[str | Sequence[str]] = None,
        columns: Optional[Sequence[str]] = None,
    ):
        """Alarms (`alarms.alarms`) recorded during this exposure's time window.

        Returns a DataFrame ordered by `time_recorded`, defaulting to the
        operator-relevant columns (`id, time_recorded, level, component,
        instance, message`) -- the boolean alarm-handler routing flags
        (`tcs`, `slack`, `email_enabled`, ...) and acknowledgement bookkeeping
        are deliberately omitted; pass `columns=` to override (e.g. add
        `alarm_id`). Same time-window machinery as `telemetry()`, just against
        the `alarms` schema.

        - `pad_seconds` widens the window symmetrically on both sides (e.g. to
          catch an alarm that fired just before the shutter opened).
        - `level`, a string or list, keeps only those severities
          (`CRITICAL` / `ALERT` / `WARNING` / `EVENT`).
        """
        start, end = self.time_window
        df = telemetry.query_window(
            self.config,
            "alarms",
            start,
            end,
            pad_seconds=pad_seconds,
            columns=list(columns) if columns is not None else list(DEFAULT_ALARM_COLUMNS),
            schema="alarms",
        )
        if level is not None and len(df) and "level" in df.columns:
            levels = [level] if isinstance(level, str) else list(level)
            df = df[df["level"].isin(levels)].reset_index(drop=True)
        return df

    @property
    def telemetry_field_names(self) -> list[str]:
        """Names of the TelemetryField specs configured for this exposure."""
        return [field.name for field in self.telemetry_fields]

    def telemetry_field(self, name: str):
        """Run (and cache) the named TelemetryField spec against this exposure.

        Looks up `name` in `self.telemetry_fields` (either what was passed to
        the constructor, or a snapshot of `telemetry.DEFAULT_TELEMETRY_FIELDS`
        taken at construction time) and dispatches to query_nearest or
        query_window depending on the spec's `kind`. Result is cached per
        name, so repeated calls cost nothing after the first.
        """
        if name in self._telemetry_field_cache:
            return self._telemetry_field_cache[name]
        field = next((f for f in self.telemetry_fields if f.name == name), None)
        if field is None:
            raise KeyError(f"No telemetry field named {name!r} configured (available: {self.telemetry_field_names})")

        start, end = self.time_window
        if field.kind == "nearest":
            when = start if field.when == "start" else end
            result = telemetry.query_nearest(
                self.config,
                field.table,
                when,
                columns=field.columns,
                time_column=field.time_column,
                schema=field.schema,
                max_delta_seconds=field.max_delta_seconds,
            )
        else:  # 'window'
            result = telemetry.query_window(
                self.config,
                field.table,
                start,
                end,
                pad_seconds=field.pad_seconds,
                columns=field.columns,
                time_column=field.time_column,
                schema=field.schema,
            )
        self._telemetry_field_cache[name] = result
        return result

    def all_telemetry_fields(self) -> dict:
        """{name: result} for every configured TelemetryField (each cached per name)."""
        return {name: self.telemetry_field(name) for name in self.telemetry_field_names}

    # ---- custom table sources ----

    @property
    def table_source_names(self) -> list[str]:
        """Names of the TableSource specs configured for this exposure."""
        return [source.name for source in self.table_sources]

    def table_source(self, name: str):
        """Run (and cache) the named TableSource lookup for this exposure.

        Looks up `name` in `self.table_sources` (either what was passed to
        the constructor, or a snapshot of `tables.DEFAULT_TABLE_SOURCES`
        taken at construction time), and returns that table's row for this
        expid, or None if the expid isn't in it. Result is cached per name.
        """
        if name in self._table_source_cache:
            return self._table_source_cache[name]
        source = next((s for s in self.table_sources if s.name == name), None)
        if source is None:
            raise KeyError(f"No table source named {name!r} configured (available: {self.table_source_names})")
        result = tables.table_source_row(source, self.expid)
        self._table_source_cache[name] = result
        return result

    def all_table_sources(self) -> dict:
        """{name: result} for every configured TableSource (each cached per name)."""
        return {name: self.table_source(name) for name in self.table_source_names}

    # ---- offline QA ----

    @cached_property
    def redux_row(self):
        return redux.redux_row(self.expid, self.config)

    @cached_property
    def exposure_table_flags(self) -> Optional[dict]:
        """Curated subset of new fields from the offline exposure_table for this exposure.

        None if unavailable -- no redux pipeline at this site, no
        exposure_table file for this night, or this expid isn't in it (e.g.
        too recent to be processed yet). Not an error.

        Only the fields that add real information beyond `redux_row`/`db_row`
        are included, each a closed/enumerated vocabulary defined by
        `desispec.workflow.exptable` (verified against the installed
        pipeline source, not assumed):
        - LASTSTEP: how far the pipeline processed this exposure -- one of
          'ignore', 'skysub', 'stdstarfit', 'fluxcal', 'all'.
        - CAMWORD / BADCAMWORD: which cameras exist / are excluded, as a
          compact 'a'+spectrograph-numbers encoding.
        - BADAMPS: comma-separated '{camera}{petal}{amp}' entries, e.g. 'b7D,z8A'.
        - EXPFLAG: quality flags, e.g. 'low_sn', 'aborted', 'metadata_missing'.
        - HEADERERR: which header/metadata fields were corrected, and to what.
        Deliberately excludes COMMENTS -- confirmed (from the pipeline's own
        source comments) to be free-form human notes not used by the
        workflow itself, not a structured field worth building filtering
        around. Also excludes every column that duplicates `redux_row`/
        `db_row` (EXPTIME, AIRMASS, TILEID, ...).
        """
        row = redux.exposure_table_row(self.expid, self.night, self.config)
        if row is None:
            return None
        return {
            "LASTSTEP": _clean_scalar(row.get("LASTSTEP")),
            "CAMWORD": _clean_scalar(row.get("CAMWORD")),
            "BADCAMWORD": _clean_scalar(row.get("BADCAMWORD")),
            "BADAMPS": _clean_scalar(row.get("BADAMPS")),
            "EXPFLAG": _parse_pipe_list(row.get("EXPFLAG")),
            "HEADERERR": _parse_pipe_list(row.get("HEADERERR")),
        }

    @cached_property
    def gfa_row(self):
        """This exposure's row from the offline GFA (guider) summary file, or None.

        Comes from a separate processing pipeline (not this project's
        telemetry/DB world) that reduces nightly GFA images into per-exposure
        conditions: seeing (FWHM_ASEC), transparency, moon geometry
        (MOON_ILLUMINATION/MOON_ZD_DEG/MOON_SEP_DEG), fiber-loss fractions
        (FIBERFAC*), etc. Specifically the EXPOSURE_SUMMARY_STRICT extension
        (quality-filtered -- confirmed it drops exposures with incomplete/NaN
        measurements, unlike the plain EXPOSURE_SUMMARY extension) --
        CAMERA_SUMMARY (per individual GFA camera, not per exposure) isn't
        used here at all, being too granular for exposure-level correlation.

        None if unavailable: no GFA offline source at this site
        (`Config.gfa_root is None`), no summary file found, or this expid
        isn't in the quality-filtered STRICT set.
        """
        return gfa.gfa_summary_row(self.expid, self.config)

    @cached_property
    def fiberqa(self) -> Optional[dict]:
        """The FIBERQA header from this exposure's offline exposure-qa-<expid>.fits, or None.

        A per-exposure QA summary from the same offline reduction as cframes
        -- and subject to the same rolling retention (present for recent
        exposures, pruned for old ones once the file ages out).

        - NGOODFIB / NGOODPET: number of fibers / petals passing QA.
        - WORSTRDN: worst (highest) CCD read noise across cameras.
        - FPRMS2D: fiber positioning RMS (2D), from post-hoc QA -- distinct
          from `db_row['posrms']` (confirmed different values for the same
          real exposure: 0.0065 vs 0.0042 -- related concepts, not the same
          measurement).
        - EFFTIME: confirmed near-identical to `redux_row['EFFTIME_SPEC']`
          for a real exposure (230.08 vs 229.8) -- kept here for
          completeness since it's free once the header is open, but prefer
          `redux_row` if you don't need the rest of this dict.
        """
        if self.config.redux_root is None:
            return None
        path = self.paths.exposure_qa(self.config.redux_root, self.night, redux_release=self.config.redux_release)
        if not path.exists():
            return None
        try:
            header = read_header(path, extension="FIBERQA")
        except Exception:
            return None
        return {key: header.get(key) for key in ("NGOODFIB", "NGOODPET", "WORSTRDN", "FPRMS2D", "EFFTIME")}

    @cached_property
    def petalqa(self):
        """This exposure's PETALQA table (10 rows, one per petal), or None.

        Same offline exposure-qa-<expid>.fits file as `fiberqa`, so the
        same availability/retention rules apply (None if this site has no
        redux pipeline, the file doesn't exist, or the extension is
        missing).

        Per-petal detail that's genuinely not available anywhere else in
        this project: NGOODPOS/NGOODFIB/NSTDSTAR (positioner/fiber/
        standard-star counts passing QA, per petal), WORSTREADNOISE,
        STARRMS, NCFRAME, and per-petal sky-background/throughput RMS+chi2
        columns. The TSNR2_*/SKY_MAG_*_SPEC columns here *do* duplicate
        exposure-level totals already in `redux_row` (same metric, summed
        across petals) -- prefer `redux_row` for those specifically.
        """
        if self.config.redux_root is None:
            return None
        path = self.paths.exposure_qa(self.config.redux_root, self.night, redux_release=self.config.redux_release)
        if not path.exists():
            return None
        try:
            return read_petalqa(path)
        except Exception:
            return None

    @cached_property
    def fiberqa_table(self):
        """This exposure's FIBERQA per-fiber table (5000 rows, whole focal plane), or None.

        Same offline exposure-qa-<expid>.fits file as `fiberqa`/`petalqa`, so
        the same availability/retention rules apply. Per-fiber detail behind
        the exposure-level `fiberqa['NGOODFIB']`/`petalqa['NGOODFIB']`
        summaries -- most notably QAFIBERSTATUS (0 = good) and EFFTIME_SPEC
        (per-fiber effective spectroscopic time), indexed by
        (PETAL_LOC, DEVICE_LOC) like `coords`/`cframe_table`.
        """
        if self.config.redux_root is None:
            return None
        path = self.paths.exposure_qa(self.config.redux_root, self.night, redux_release=self.config.redux_release)
        if not path.exists():
            return None
        try:
            return read_fiberqa_table(path)
        except Exception:
            return None

    @cached_property
    def calibstars(self):
        """This exposure's standard-star flux calibration table, indexed by FIBER, or None.

        ~100-150 rows (one per spectrophotometric standard star used for this
        exposure's flux calibration) -- a plain CSV, not FITS, from the same
        offline redux tree/directory as cframe/exposure-qa (so the same
        availability/retention rules apply). Per the official DESI datamodel
        docs: RCALIBFRAC is the ratio of r-band spectroscopic flux to model
        flux (the natural quantity for a linphi-vs-regular calibration-quality
        comparison); EBV is SFD98 Galactic extinction; MODEL_COLOR/DATA_COLOR
        are the model/measured G-R color; X/Y are focal-plane position (mm);
        VALID is whether the star was kept (1) or rejected (0) as a 3-sigma
        RCALIBFRAC outlier across petals, or a G-R color mismatch > 0.2*EBV.

        FIBER here is the whole-focal-plane 0-4999 numbering, the SAME
        numbering as `cframe_table`/`fiberqa_table`'s FIBER column -- but
        this table is NOT indexed by (PETAL_LOC, DEVICE_LOC) itself.
        `FIBER // 500 == PETAL_LOC` always holds, but DEVICE_LOC has no
        formula -- join against `fiberqa_table` (single whole-focal-plane
        table) or `cframe_table(camera)` on FIBER to get it, e.g.:

            fiber_loc = exp.fiberqa_table.reset_index().set_index('FIBER')[['PETAL_LOC', 'DEVICE_LOC']]
            calib_with_loc = exp.calibstars.join(fiber_loc)
        """
        if self.config.redux_root is None:
            return None
        path = self.paths.calibstars(self.config.redux_root, self.night, redux_release=self.config.redux_release)
        if not path.exists():
            return None
        import pandas as pd

        try:
            return pd.read_csv(path).set_index("FIBER")
        except Exception:
            return None

    # ---- offline per-camera spectra (cframe) ----
    # Deliberately NOT cached_property: there are 30 cframe files per exposure
    # (one per camera), each tens of MB, and these are for occasional special
    # studies (e.g. per-fiber flux/SNR checks), not routine use -- nothing
    # here is ever touched by __repr__/summary(). Each is cached per camera
    # after first read, so repeated calls for the same camera are free.

    def cframe_path(self, camera: str) -> Path:
        """Path to this exposure's cframe-<camera>-<expid>.fits.gz (offline reduction).

        Raises DataSourceUnavailableError if this site has no redux pipeline
        at all (Config.redux_root is None, e.g. KPNO) -- cframes live under
        the same redux tree as the offline QA table.
        """
        if self.config.redux_root is None:
            raise DataSourceUnavailableError(
                f"No offline/redux data source configured for site={self.config.site!r} "
                "(Config.redux_root is None); cframe files live there and aren't available"
            )
        return self.paths.cframe(self.config.redux_root, self.night, camera, redux_release=self.config.redux_release)

    def cframe_fibermap(self, camera: str):
        """FIBERMAP table for one camera's cframe file (targeting/positioning, 500 rows)."""
        if camera not in self._cframe_fibermap_cache:
            self._cframe_fibermap_cache[camera] = read_fibermap(self.cframe_path(camera))
        return self._cframe_fibermap_cache[camera]

    def cframe_scores(self, camera: str):
        """SCORES table for one camera's cframe file (per-fiber flux/SNR summary).

        Row-aligned with cframe_fibermap(camera) -- see cframe_table for a
        version that's already combined and indexed by location.
        """
        if camera not in self._cframe_scores_cache:
            self._cframe_scores_cache[camera] = read_scores(self.cframe_path(camera))
        return self._cframe_scores_cache[camera]

    def cframe_table(self, camera: str):
        """FIBERMAP + SCORES combined for one camera, indexed by (PETAL_LOC, DEVICE_LOC).

        SCORES carries no location columns of its own -- it's guaranteed
        row-aligned with FIBERMAP within the same file (verified: identical
        row count, FIBER sorted ascending, LOCATION == PETAL_LOC*1000+DEVICE_LOC).
        This combines them and applies that location as an explicit index,
        so joining against e.g. `coords` (also indexed by PETAL_LOC/DEVICE_LOC)
        is a plain pandas join.

        Reads both extensions from a single file open when neither is
        already cached -- ~30% faster than the two separate opens that
        calling `cframe_fibermap`/`cframe_scores` independently would each
        pay (gzip decompression gets re-paid on every open). Still populates
        both of their caches either way, so a later standalone call to
        either is free.

        This is still dominated by gzip decompression regardless: FIBERMAP
        and SCORES are the last two extensions in the file, after the much
        larger FLUX/IVAR/MASK/WAVELENGTH/RESOLUTION pixel arrays, and gzip
        isn't seekable -- reaching them costs close to a full-file
        decompression no matter which extensions you ask for. See
        `cframe_tables` for reading several cameras at once, which sidesteps
        this cost via process-level parallelism instead.
        """
        if camera not in self._cframe_table_cache:
            import pandas as pd

            if camera in self._cframe_fibermap_cache and camera in self._cframe_scores_cache:
                fibermap = self._cframe_fibermap_cache[camera]
                scores = self._cframe_scores_cache[camera]
            else:
                fibermap, scores = read_fibermap_and_scores(self.cframe_path(camera))
                self._cframe_fibermap_cache[camera] = fibermap
                self._cframe_scores_cache[camera] = scores

            combined = pd.concat([fibermap, scores], axis=1)
            combined = combined.set_index(["PETAL_LOC", "DEVICE_LOC"])
            self._cframe_table_cache[camera] = combined
        return self._cframe_table_cache[camera]

    def cframe_tables(self, cameras: Sequence[str], max_workers: Optional[int] = None):
        """Read cframe_table for several cameras at once, in parallel OS processes.

        `cframe_table` pays close to a full gzip decompression per file even
        for one camera (FIBERMAP/SCORES are the last two extensions, after
        the much larger pixel-array extensions -- see its docstring), and
        that decompression is CPU-bound C code that does not release the
        GIL, so plain threads give no benefit (confirmed by direct
        measurement: threaded reads were no faster, sometimes slower, than
        sequential). Real OS processes do scale it: a 10-worker pool reading
        all 10 r-camera cframe files for one exposure measured ~3.8x faster
        than the equivalent sequential cframe_table calls (~0.4s/camera vs
        ~1.4s/camera). `max_workers` defaults to one worker per camera being
        fetched (capped by the machine's CPU count) -- pass an explicit
        value to use fewer.

        Returns `(tables, errors)`. `tables` maps camera -> the same
        DataFrame `cframe_table(camera)` would return, and populates this
        Exposure's normal per-camera caches, so a later `cframe_table`/
        `cframe_fibermap`/`cframe_scores` call for any of these cameras is
        free. `errors` maps camera -> the exception raised while reading it
        (e.g. a missing/pruned cframe file for an old exposure) -- a failed
        camera is simply absent from `tables`, mirroring the
        try/except-and-skip pattern used when looping `cframe_table`
        directly one camera at a time.

        Only worth using across the cameras of *one* exposure. Don't nest
        this with parallelism across many exposures at once (e.g. running
        several of these pools concurrently in an outer loop) -- that
        combination hits real shared-filesystem contention rather than
        compounding the speedup.
        """
        cameras = list(cameras)
        tables_out = {c: self._cframe_table_cache[c] for c in cameras if c in self._cframe_table_cache}
        to_fetch = [c for c in cameras if c not in self._cframe_table_cache]
        errors: dict = {}
        if not to_fetch:
            return tables_out, errors

        import multiprocessing
        import os
        from concurrent.futures import ProcessPoolExecutor, as_completed

        import pandas as pd

        night = self.night  # resolve once here so worker processes need no DB access
        workers = max_workers or min(len(to_fetch), os.cpu_count() or 4)

        # 'forkserver' instead of the Linux-default 'fork': this runs from real Jupyter
        # notebooks, and a Jupyter kernel is multi-threaded (ipykernel's zmq/heartbeat
        # threads) -- forking directly from a multi-threaded process is a known source of
        # rare child-process deadlocks. forkserver starts a clean single-threaded helper
        # process up front and forks lightweight children from that instead.
        ctx = multiprocessing.get_context("forkserver")
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
            futures = {
                pool.submit(_read_cframe_camera, self.expid, night, self.config, camera): camera
                for camera in to_fetch
            }
            for future in as_completed(futures):
                camera = futures[future]
                try:
                    fibermap, scores = future.result()
                except Exception as exc:
                    errors[camera] = exc
                    continue
                self._cframe_fibermap_cache[camera] = fibermap
                self._cframe_scores_cache[camera] = scores
                combined = pd.concat([fibermap, scores], axis=1)
                combined = combined.set_index(["PETAL_LOC", "DEVICE_LOC"])
                self._cframe_table_cache[camera] = combined
                tables_out[camera] = combined

        return tables_out, errors

    # ---- convenience ----

    def summary(self) -> dict:
        """Cheap, flattened scalar summary. Never triggers guider I/O."""
        out: dict = {"expid": self.expid}
        try:
            out["night"] = self.night
        except Exception as exc:
            out["night_error"] = str(exc)
        try:
            row = self.db_row
            for key in ("sequence", "tileid", "exptime", "date_obs", "program", "obstype", "airmass"):
                out[key] = row.get(key)
        except Exception as exc:
            out["db_error"] = str(exc)
        redux_row = self.redux_row
        out["in_redux_daily"] = redux_row is not None
        return out

    def __repr__(self) -> str:
        return f"Exposure(expid={self.expid})"
