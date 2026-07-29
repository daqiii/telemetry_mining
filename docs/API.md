# telemetry_mining API Reference

`telemetry_mining` gives you one Python object per DESI exposure — `Exposure(expid)` —
that lazily resolves everything associated with that exposure: the raw FITS header,
fiber coordinates, the ETC (exposure time calculator) summary, guider metadata, the
condensed per-exposure database record, a telemetry time-window query, and the
offline QA/reduction row. It replaces hand-rolled file paths, raw SQL, and manual
`fitsio`/`DATE-OBS` parsing with a single, consistent API.

This document is the **reference** — every public class and function, with exact
signatures, arguments, and return types. If you're learning the package or want
worked, task-oriented recipes ("how do I select exposures and correlate
telemetry?"), start with the **[User Guide](GUIDE.md)** instead, then come back
here for specifics. For what individual fields/columns mean, see
**[FIELDS.md](FIELDS.md)**; for design rationale, see `README.md`.

## Data-uniformity caveat: dailies are not uniformly reprocessed

**⚠️ Read this before trending any derived quantity over time.** This module reads the
**`daily`** reduction, where each night is processed **once** with the then-current
`desispec` and is **not** retroactively reprocessed. Pipeline changes therefore introduce
**time-dependent discontinuities**: a cross-time trend can reflect a software change
rather than the sky or the instrument.

**Confirmed example — `RCALIBFRAC` (calibstars).** Around **mid-2025** a point-source
flat→psf aperture correction was added to how `RCALIBFRAC` is computed (desispec PR #2484
/ Data Systems, released in 0.70.0), shifting its distribution at all airmass. See
`MEASURED_VS_EXPECTED_FLUX.md` for exactly how `RCALIBFRAC` and the other throughput /
"truth" variables are constructed, what correction each carries, and which to use for what.

**For time-consistent analyses**, use a single uniformly-reprocessed **data release** (not
`daily`), or reprocess the relevant step yourself with a frozen `desispec` version.

## Contents

- [Data-uniformity caveat: dailies are not uniformly reprocessed](#data-uniformity-caveat-dailies-are-not-uniformly-reprocessed)

- [Installation / environment](#installation--environment)
- [Deployment: NERSC and KPNO](#deployment-nersc-and-kpno)
- [Quick start](#quick-start)
- [`Config`](#config)
- [`Exposure`](#exposure)
  - [Identity and paths](#identity-and-paths)
  - [FITS header](#fits-header)
  - [Fiber coordinates](#fiber-coordinates)
  - [FIBERASSIGN table](#fiberassign-table)
  - [ETC (exposure time calculator) data](#etc-exposure-time-calculator-data)
  - [Guider data](#guider-data)
  - [Database record](#database-record)
  - [Telemetry correlation](#telemetry-correlation)
    - [Telemetry fields: declarative, per-exposure lookups](#telemetry-fields-declarative-per-exposure-lookups)
  - [Alarms](#alarms)
  - [Offline QA / reduction row](#offline-qa--reduction-row)
  - [Offline per-camera spectra (cframe)](#offline-per-camera-spectra-cframe)
  - [GFA offline summary](#gfa-offline-summary)
  - [FIBERQA](#fiberqa)
  - [PETALQA](#petalqa)
  - [FIBERQA per-fiber table](#fiberqa-per-fiber-table)
  - [Standard-star flux calibration table](#standard-star-flux-calibration-table)
  - [Custom table sources](#custom-table-sources)
  - [Convenience](#convenience)
- [Bulk exposure lookups](#bulk-exposure-lookups)
- [Bulk selection and correlation (`select_exposures` / `harvest`)](#bulk-selection-and-correlation-select_exposures--harvest)
  - [Column/value specs](#columnvalue-specs)
- [`ExposurePaths`](#exposurepaths)
- [Errors](#errors)
- [Command line](#command-line)
- [Module reference](#module-reference)
  - [`telemetry_mining.db` — direct database access](#telemetry_miningdb--direct-database-access)
  - [`telemetry_mining.telemetry` — time-window & nearest queries](#telemetry_miningtelemetry--time-window--nearest-in-time-queries)
  - [`telemetry_mining.redux` — offline reduction tables](#telemetry_miningredux--offline-reduction-tables)
  - [`telemetry_mining.gfa` — offline GFA summary](#telemetry_mininggfa--offline-gfa-guider-summary)
  - [`telemetry_mining.etc` — ETC JSON parsing](#telemetry_miningetc--etc-json-parsing)
  - [`telemetry_mining.tables` — custom table sources](#telemetry_miningtables--custom-per-exposure-table-sources)
  - [`telemetry_mining.alarms` — alarm-log search](#telemetry_miningalarms--alarm-log-search)
  - [`telemetry_mining.fits_io` — raw FITS readers](#telemetry_miningfits_io--raw-fits-readers)
  - [`telemetry_mining.paths` — path & night resolution](#telemetry_miningpaths--path--night-resolution)
  - [`telemetry_mining.query` — bulk selection & specs](#telemetry_miningquery--bulk-selection--specs)
- [Caching and cost model](#caching-and-cost-model)
- [Known gotchas](#known-gotchas)

## Installation / environment

This package needs a Python with working `psycopg2` and `fitsio`. On this
account, use:

```
source /global/common/software/desi/desi_environment.sh master
```

or the "DESI master" Jupyter kernel, which activates the same environment
(and, on this account only, has this package importable via a `pip install
-e . --user` done early in development — that's a per-user, per-Python-version
side effect, not something to rely on from a different account or kernel).

**The robust way, for any kernel/account**: no install is needed at all, just
put `<checkout>/src` on `sys.path` before importing, the same way you'd point
at a loose checkout like `~/DOSlib-trunk`. Read the checkout location from the
`DOS_TELEMETRY_MINING_DIR` environment variable (falling back to a sensible
default) rather than hardcoding it, so the same notebook/script works
unmodified for anyone who sets that variable to point at their own checkout:

```python
import os
import sys
tm_dir = os.getenv("DOS_TELEMETRY_MINING_DIR",
                   os.path.expanduser("~/telemetry_mining-trunk/src"))
sys.path.insert(0, tm_dir)
from telemetry_mining import (
    Config, Exposure, find_exposures, find_last_exposure)
```

This is the pattern every notebook in `notebooks/` uses (see their first code
cell) — it's why those notebooks have no other hardcoded path in them. The
fallback (`~/telemetry_mining-trunk/src`) resolves per-account via `$HOME`, so
it's not tied to any one person — it only actually finds a checkout for
someone whose own checkout happens to live at exactly that path; anyone
else needs `DOS_TELEMETRY_MINING_DIR` set (see below).

DB connection details come from the `DOS_DB_NAME`, `DOS_DB_HOST`, `DOS_DB_PORT`,
`DOS_DB_READER`, `DOS_DB_READER_PASSWORD` environment variables (already set in
the standard DESI environment). This is a shared, non-personal read-only
account — nothing here is tied to any one person's credentials, so any
collaborator sourcing the standard DESI environment gets working DB access
automatically, with nothing to distribute or coordinate separately.

**At KPNO** (the `msdos` / `desiobserver` accounts), skip the `sys.path` step
entirely: run `setup telemetry_mining` in the shell **first** — before launching
`python3` or the Jupyter server — and the `eups` package manager puts the module
on the import path, so `from telemetry_mining import Exposure` just works. See
[Deployment](#deployment-nersc-and-kpno) for the full KPNO/NERSC picture.

### For collaborators at NERSC without their own editable install

If you don't have (or don't want) your own editable install, get your own
checkout rather than pointing at someone else's home directory — home
directories are typically not traversable by other accounts (`chmod 700`),
so that wouldn't work anyway even if offered. Check out the SVN repo into
your own space:

```
svn checkout \
    https://desi.lbl.gov/svn/code/online/telemetry_mining/trunk \
    telemetry_mining
```

Then, since no install is required (see below), set `DOS_TELEMETRY_MINING_DIR`
in your shell (e.g. in `.bash_profile`) to that checkout's `src` directory:

```
export DOS_TELEMETRY_MINING_DIR=$HOME/telemetry_mining/src
```

and any notebook/script using the `os.getenv("DOS_TELEMETRY_MINING_DIR", ...)`
pattern above (including every notebook in `notebooks/`) will pick up your
checkout automatically, with no per-file edits:

```python
import os
import sys
tm_dir = os.getenv("DOS_TELEMETRY_MINING_DIR",
                   os.path.expanduser("~/telemetry_mining-trunk/src"))
sys.path.insert(0, tm_dir)
from telemetry_mining import Config, Exposure
```

You still need the same working `psycopg2`/`fitsio` environment as above —
either `source /global/common/software/desi/desi_environment.sh master`
first, or a Jupyter kernel built on that same desiconda. Check with your
group whether a NERSC JupyterHub kernel already matches that build (NERSC's
DESI kernels are typically registered via
`/global/common/software/desi/install_jupyter_kernel`) before assuming one
does — a data-release kernel (e.g. `desi-edr-*`) is not necessarily the
same desiconda build this package targets.

If this grows beyond a couple of collaborators, a single shared checkout
under `/global/cfs/cdirs/desi/software/` (group-readable by the whole
`desi` unix group) would beat everyone maintaining their own SVN checkout —
but that's DESI-operations territory to set up, not something to do
unilaterally; worth raising once there's real multi-user demand.

## Deployment: NERSC and KPNO

The package has no dependency on where it's installed from — it doesn't need
`pip install` at all. Confirmed: adding `<checkout>/src` to `PYTHONPATH` is
sufficient for a plain `import telemetry_mining` to work, with no editable
install, no `.egg-info`, nothing else. That's what makes it deployable
through KPNO's package management without any packaging changes.

The canonical copy of this project is the DESI SVN repo
(`https://desi.lbl.gov/svn/code/online/telemetry_mining/trunk`) — both the
NERSC development checkout and the KPNO deployment below are checked out
from it, rather than being separate copies that can drift apart.

**At KPNO**, the package is installed on the DESI cluster and declared as a
product in the ICS environment (the `msdos` and `desiobserver` accounts).
From those accounts:

```
setup telemetry_mining
```

then, in `python3`:

```python
from telemetry_mining import exposure
```

(`exposure` here is the module; the class most callers actually want is
`Exposure`, i.e. `from telemetry_mining import Exposure` — see
[Quick start](#quick-start) below.)

**Site differences, and how the code adapts:**

| | NERSC | KPNO |
|---|---|---|
| DB (`telemetry` + `exposure` schemas) | full history | full history (same `DOS_DB_*` env vars, different host — confirmed no other difference) |
| Exposure files (FITS/JSON) | full history | only a rolling ~6 months — older ones are purged once confirmed at NERSC |
| Offline/redux QA (`exposures-daily.csv`) | present | **does not exist** — no reduction pipeline runs at KPNO at all |

`Config.default()` already auto-detects site from `DOS_DB_HOST` (`"lbl.gov"` →
`nersc`, anything else non-empty → `kpno`) and picks the right
`exposures_root` (`/exposures/desi` at KPNO, confirmed correct against
DOSlib's convention). `Config.redux_root` is `None` at any non-NERSC site —
not a guessed path — since there's no redux data source to point at, not
just a different location for one. Every place that reads it
(`Exposure.redux_row`, `redux.redux_row`) treats `None` the same as "this
exposure isn't in the table": routine, not an error. Calling
`redux.load_exposures_daily(config)` directly when `redux_root is None`
raises `DataSourceUnavailableError`, since asking for the table at a site
that fundamentally has no such table is a caller mistake, unlike a normal
per-exposure absence.

The file-purge behavior means an `Exposure` whose on-disk directory has aged
out at KPNO will legitimately fail on any file-based accessor (`header`,
`coords`, `etc`, ...) with a clear `ExposureNotFoundError` — expected, since
those files are genuinely gone. DB-only access still works fully regardless
of file availability: `db_row`, `stars`, `comments`, `guider_centroids`, and
`time_window`/`telemetry(...)`/`telemetry_field(...)` (which prefer the DB
record and only touch the FITS header as a fallback) don't require the
exposure directory to exist at all, as long as the DB record is complete.

## Quick start

```python
from telemetry_mining import Exposure

exp = Exposure(255020)  # night resolved automatically via the DB
exp.summary()
# -> {'expid': 255020, 'night': 20240925, 'sequence': 'DESI',
#     'tileid': 22258, 'exptime': 579.8482,
#     'date_obs': datetime(2024, 9, 26, 12, 21, 46, tzinfo=utc),
#     'program': 'BRIGHT', 'obstype': 'SCIENCE', 'airmass': 1.794142,
#     'in_redux_daily': True}

exp.header_value('AIRMASS')  # 1.794142  (reads the FITS header)
exp.coords.shape  # (5133, 89) -- one row per fiber
exp.etc_summary['ETCTEFF']  # 16.432716  (reads etc-<expid>.json)
# DataFrame
exp.telemetry('environmentmonitor_telescope', pad_seconds=30)
exp.redux_row['TILEID']  # 22258 (or None if not yet processed)
```

Passing `night` explicitly skips a DB round-trip and makes every file-based
accessor work with **zero** database access:

```python
exp = Exposure(255020, night=20240925)
exp.header_value('SEQUENCE')  # works with no DB connection at all
```

## `Config`

```python
from telemetry_mining import Config
```

`Config` (defined in `telemetry_mining/config.py`) is a frozen dataclass bundling
filesystem roots and DB connection info. Every field is a plain constructor
argument, so it's easy to build a `Config` pointing somewhere else (tests do
this to point at a `tmp_path` tree).

| Field | Type | Meaning |
|---|---|---|
| `site` | `str` | `"nersc"`, `"kpno"`, or `"unknown"` (auto-detected) |
| `exposures_root` | `Path` | root of exposure directories (`<root>/<night>/<expid>`) |
| `redux_root` | `Path \| None` | root of the offline reduction tree, or `None` if this site has no redux pipeline at all (e.g. KPNO) |
| `gfa_root` | `Path \| None` | root of the offline GFA (guider) summary pipeline, or `None` if unavailable at this site. Unlike `redux_root`, KPNO-absence here is an assumption by analogy, not confirmed with anyone |
| `redux_release` | `str` | subdirectory under `redux_root`, default `"daily"` |
| `db_name` | `str` | Postgres database name |
| `db_host` | `str` | Postgres host |
| `db_port` | `int` | Postgres port, default `5432` |
| `db_user` | `str` | Postgres user |
| `db_password` | `str` | Postgres password (excluded from `repr()`) |

**`Config.default()`** — the usual way to get one — reads the `DOS_DB_*`
environment variables and derives `site`/`exposures_root`/`redux_root` from
`DOS_DB_HOST` (the same `"lbl.gov" in DOS_DB_HOST` check DOSlib uses, centralized
here instead of repeated at every call site). If `DOS_DB_HOST` isn't set to a
recognized NERSC host, it falls back to the mountain-side exposures path
(`/exposures/desi`, confirmed correct for KPNO) and sets `redux_root = None`
(confirmed there's no offline/redux pipeline at KPNO to point at).

```python
config = Config.default()
config.site               # 'nersc'
# PosixPath('/global/cfs/cdirs/desi/spectro/data')
config.exposures_root
config.redux_root         # None at KPNO; a Path at NERSC
config.gfa_root           # None at KPNO (assumed); a Path at NERSC
```

Two derived properties, both `None` if `redux_root` is `None`:

- `config.redux_daily_dir` → `redux_root / redux_release`
- `config.exposures_daily_csv` → `redux_daily_dir / "exposures-daily.csv"`

Every `Exposure`, `find_exposures`, `find_last_exposure`, and lower-level
function takes a `Config` (or defaults to `Config.default()` if omitted where
applicable), so swapping environments is one object, not a search-and-replace.

## `Exposure`

```python
Exposure(
    expid: int,
    night: int | None = None,
    config: Config | None = None,  # None -> Config.default()
    telemetry_fields: Sequence[TelemetryField] | None = None,
)
```

Constructing an `Exposure` does **zero I/O** — nothing is read from disk or
queried from the database until you actually touch an attribute. Everything
below except `guide_frame`/`guide_cube_path` and the `cframe_*` methods is a
`functools.cached_property`:
computed once on first access, cached for the object's lifetime.

- `expid` — the exposure ID (coerced to `int`).
- `night` — pass this to skip a DB lookup; if omitted, `exp.night` triggers one
  query against `exposure.exposure`.
- `config` — defaults to `Config.default()`.
- `telemetry_fields` — named, declarative telemetry lookups this exposure can
  run on demand; defaults to a snapshot of `telemetry.DEFAULT_TELEMETRY_FIELDS`
  taken at construction time. See [Telemetry fields](#telemetry-fields-declarative-per-exposure-lookups).

### Identity and paths

| Member | Type | Notes |
|---|---|---|
| `exp.night` | `int` | explicit constructor arg, or resolved via one DB query |
| `exp.directory` | `Path` | `<exposures_root>/<night>/<expid:08d>`; raises `ExposureNotFoundError` if it doesn't exist on disk |
| `exp.paths` | `ExposurePaths` | named accessors for every known file — see [below](#exposurepaths) |
| `exp.config` | `Config` | the config this instance was built with (public attribute, not a property) |

```python
# PosixPath('/global/cfs/cdirs/desi/spectro/data/20240925/00255020')
exp.directory
exp.paths.main_fits        # .../desi-00255020.fits.fz
exp.paths.coordinates      # .../coordinates-00255020.fits
```

### FITS header

```python
exp.header  # dict, from the 'SPEC' extension of desi-<expid>.fits.fz
exp.header_value(key, default=None) # exp.header.get(key, default)
```

`exp.header` reads the `SPEC` extension by default (falls back to the primary
HDU if `SPEC` isn't present — not every exposure type has one). Typical keys:
`SKYRA`, `SKYDEC`, `MOUNTHA`, `MOUNTAZ`, `MOUNTEL`, `DATE-OBS`, `EXPTIME`,
`AIRMASS`, `WINDSPD`, `WINDDIR`, `GUST`, `SEQUENCE`, `SPLITEXP`, `PMIRTEMP`,
`TAIRTEMP`, `SKYLEVEL`, `PMTRANS`, `PMSEEING`.

### Fiber coordinates

```python
exp.coords  # DataFrame, DATA extension of coordinates-<expid>.fits
exp.stationary     # DataFrame, STATIONARY extension (fixed fiducials)
```

Both are indexed by `(PETAL_LOC, DEVICE_LOC)`, one row per fiber/fiducial. This
fixes two real bugs present in the equivalent `DOSlib.util.coords2df` /
`stationary2df`: a `NameError` in its directory-path branch (references an
undefined variable), and an `AttributeError` under NumPy≥2.0 (it calls
`ndarray.newbyteorder()`, which was removed).

```python
exp.coords.loc[(1, 420)]  # fiber on petal 1, device 420
list(exp.coords.columns)
# -> POS_Q, POS_S, POS_X, POS_Y, POS_LINPHI, TARGET_RA/DEC,
#    FIBER_RA/DEC/X/Y, per-iteration EXP_*/FVC_*/CNT_* fields, ...
```

### FIBERASSIGN table

```python
# DataFrame indexed by (PETAL_LOC, DEVICE_LOC), 5000 rows, or None
exp.fiberassign_table
```

Reads `fiberassign-<tileid>.fits.gz`'s `FIBERASSIGN` extension (`tileid` comes from the
header, no DB round-trip needed) -- one file, whole focal plane, carrying `FIBER` and the
targeting bitmasks (`DESI_TARGET`/`BGS_TARGET`/`MWS_TARGET`/`SCND_TARGET`) alongside
`(PETAL_LOC, DEVICE_LOC)`. This is the fast path whenever you need a targeting bitmask and
nothing camera/arm-specific from `cframe_table`'s FIBERMAP/SCORES: confirmed ~60x faster
than looping `cframe_table` over every petal for the same columns (~0.14s vs. ~9s per
exposure, since a single ~9MB fiberassign file beats reading ten cframe files with large
spectral arrays you don't use).

Lives in the raw exposure directory (`Config.exposures_root`), like `coords`/`header` --
not the redux tree, so it shares their retention (full history at NERSC, ~6 months at
KPNO), not `cframe`/`calibstars`/`exposure_qa`'s separate rolling redux retention.
Confirmed: still available for an exposure whose `cframe`/`calibstars` files have already
been pruned.

`None` (not a raised exception) if the main FITS file itself is missing too -- unlike
`header` directly, which raises in that case by design. `fiberassign_table` needs `header`
internally (for `TILEID`), but callers reaching for it want "is this available", not a hard
failure -- a missing main FITS file for an otherwise-valid DB-listed exposure is a real,
confirmed gap at scale (e.g. from known DESI downtime periods -- maintenance, wildfire
evacuation, a cybersecurity incident), not hypothetical.

**Real gotcha, confirmed against real data**: `DESI_TARGET`'s `STD_FAINT`/`STD_WD`/
`STD_BRIGHT` bits flag standard stars for the main DARK/BRIGHT survey, but `BACKUP`-program
exposures (`program='BACKUP'`, bright/nearby targets for poor conditions) flag their
standard stars in `MWS_TARGET` instead (`GAIA_STD_FAINT`/`GAIA_STD_WD`/`GAIA_STD_BRIGHT`) --
found by running `notebooks/calibstars_linphi.ipynb` over a wide selection and hitting a
`BACKUP` exposure that matched 0/297 calibstars fibers against `DESI_TARGET` alone. Both
masks happen to use identical bit positions (`0xE00000000` for the three STD bits), just in
different columns, so check both if you don't already know an exposure's program.

### ETC (exposure time calculator) data

```python
exp.etc  # full parsed etc-<expid>.json, as nested dicts/lists
# etc['header'] block: ETCTEFF, ETCREAL, ETCTRANS, ETCSKY, ACQFWHM,
# ...
exp.etc_summary
# 'shutter' | 'thru' | 'sky' | 'accum' -> DataFrame
exp.etc_timeseries(key)
```

`etc_timeseries` turns one of the JSON's time-series blocks into a DataFrame:
list-valued entries become columns, and any scalar entries in the same block
(e.g. `mjd0`) are attached to `df.attrs` rather than dropped.

```python
df = exp.etc_timeseries('accum')
df.columns
# -> Index(['dt', 'dt_src', 'src', 'signal', 'background',
#           'efftime', 'realtime', 'remaining', 'next_split'])
df.attrs['mjd0']  # 60579.51512359493
```

### Guider data

Guider files are GB-scale (a full cube can be 800MB+), so these are
**deliberately not** `cached_property` — nothing here is ever touched by
`repr()` or `summary()`, and reading a whole cube is something you opt into
explicitly.

```python
# dict, from centroids-<expid>.json (small; this one IS cached)
exp.centroids
# DataFrame, one row per guider frame -- see below
exp.guider_centroids
exp.n_guide_frames  # int: number of guider frames for this exposure
# opens (doesn't read) guide-<expid>-0000.fits.fz; a fitsio.FITS
# handle
exp.guide_frame(frame=0)
# frame != 0 opens the full guide-<expid>.fits.fz cube instead
exp.guide_frame(frame=1)
# Path to the full cube, for callers who want to read it themselves
exp.guide_cube_path()
```

**`guider_centroids`** queries `telemetry.guider_centroids` (DB, not the FITS
guider cube) for this exposure's `expid`, one row per guider frame, ordered by
`frame`. Much faster than opening `guide-<expid>.fits.fz` (GB-scale) when only
the per-frame summary is needed. Columns: `frame`, `time_recorded`, `obstime`,
`seeing`, `nstars`, `ngfas`, `combined_x`, `combined_y`, `tcs_correction_ra`,
`tcs_correction_dec`, `rotation` (per-frame field-rotation estimate, same
units — arcsec/min-consistent magnitude — as `db_row.hexapod['rot_rate']`,
confirmed 2026-07-20 by comparing a real exposure's fitted rotation-vs-`obstime`
slope against its `rot_rate`, one order of magnitude smaller as expected for a
residual after the rate model's correction). (The table also has per-GFA-camera
`jsonb` columns like `guide0_0`/`guide2_1`/etc. and TCS-guiding-state fields
(`guiding`, `send_guide_corrections`) not fetched here; query
`telemetry.guider_centroids` directly via `telemetry_mining.db` if you need
those.)

```python
exp.guider_centroids.shape  # (72, 11) for a typical science exposure
exp.guider_centroids['seeing'].mean()
```

**`n_guide_frames`** prefers the FITS header's `GFRAMES` field (no DB access
needed — this is the same header block that also has the `GUIDER` jsonb
summary with `gframes` in it) and falls back to `len(exp.guider_centroids)`
if `GFRAMES` isn't present — whether because a present header lacks the key,
or because the FITS file itself is unavailable (again, the KPNO purge case).

`guide_frame`/`guide_cube_path` are the only unimplemented-beyond-a-stub piece
of the accessor today — actually reading postage stamps/ROIs out of the full
image cube is a natural next extension, not yet built.

### Database record

```python
# dict: the full exposure.exposure row (187 columns; jsonb columns
# auto-decode to dict/list)
exp.db_row
# DataFrame: exposure.stars rows for this expid (guide star catalog;
# often empty)
exp.stars
# DataFrame: exposure.comments rows for this expid, ordered by date
# (often empty)
exp.comments
```

`db_row` raises `ExposureNotFoundError` if there's no matching row. Note: not
every header field is reliably mirrored into `exposure.exposure` — e.g.
`winddir`/`windspd`/`gust`/`pmirtemp` were `None` in the DB row for a real
exposure whose FITS header had them populated. Prefer `exp.header` for those
specific fields; use `db_row` for the fields it's known to carry well (`night`,
`date_obs`, `mjd_obs`, `exptime`, `sequence`, `tileid`, `skyra`/`skydec`,
`mountha`/`az`/`el`, `airmass`, `pmseeing`, and the `jsonb` blocks like `tcs`,
`etc`, `guider`).

### Telemetry correlation

This is the core reason the package exists: correlating an exposure with the
telemetry recorded while it was happening.

```python
exp.time_window  # (start, end) tz-aware UTC datetimes
exp.telemetry(table, *, pad_seconds=0.0, columns=None,
              time_column='time_recorded')
```

`time_window` prefers the DB record's `date_obs`/`exptime` (directly comparable
to telemetry's `time_recorded` timestamptz columns, no MJD/UTC conversion
needed) and falls back to the FITS header's `DATE-OBS`/`EXPTIME` if the DB is
unreachable or the row is missing those fields — including if the header
itself can't be read at all (e.g. the exposure's files were purged, which
happens routinely at KPNO after ~6 months), in which case it raises a clean
`ExposureNotFoundError` rather than a raw FITS/OS error.

`telemetry(table, ...)` queries **any** of the 93 tables in the `telemetry`
schema for rows within `time_window` (widened by `pad_seconds` on both ends),
returning a pandas DataFrame ordered by `time_column` ascending. `table`,
`columns`, and `time_column` are validated against an identifier pattern and
safely quoted — never string-interpolated into SQL.

```python
exp.telemetry('environmentmonitor_telescope', pad_seconds=30)
exp.telemetry('environmentmonitor_tower',
              columns=['wind_speed', 'wind_direction', 'gust'])
```

**Most of the 93 `telemetry` tables have no `expid` column at all** — they're
pure time series (only `time_recorded`), unlike `exposure.exposure` or
`guider_centroids`. For those, the useful question usually isn't "everything
during the exposure" but "the value closest to the exposure's start time, by
convention" — that's what `telemetry_nearest`/`query_nearest` and the
`telemetry_fields` mechanism below are for.

```python
exp.telemetry_nearest(table, *, when='start', columns=None,
                      time_column='time_recorded',
                      max_delta_seconds=None)
```

`when` is `'start'` (the convention) or `'end'`, or pass a `datetime`
directly. Returns a `dict` (not a DataFrame — this is a single-row lookup) or
`None` if the table has no rows, or if the nearest one is farther than
`max_delta_seconds` away. The result always has a `delta_seconds` key: how
many seconds *after* `when` that row's timestamp falls (negative = the row is
from before `when`).

```python
exp.telemetry_nearest('environmentmonitor_dust',
                      columns=['mayall_particle_1_micron_5'],
                      max_delta_seconds=3600)
# -> {'mayall_particle_1_micron_5': 18,
#     'time_recorded': datetime(2026, 7, 3, 4, 9, 44, ...),
#     'delta_seconds': -0.584274}
```

Under the hood (`telemetry_mining.telemetry.query_nearest`), this runs two
bounded queries — nearest row at-or-before `when`, nearest row at-or-after —
rather than scanning a window and sorting by distance. Both halves use
`time_column`'s index (confirmed via `EXPLAIN` against a real table: `Index
Only Scan`, not a sequential scan), so this stays fast even on tables with
millions of rows.

#### Telemetry fields: declarative, per-exposure lookups

As more of these get added, hardcoding one `Exposure` property per table
doesn't scale. Instead, describe each lookup once as a **`TelemetryField`**,
and either pass a list at construction time or register defaults once,
process-wide:

```python
from telemetry_mining.telemetry import TelemetryField
from telemetry_mining import Exposure

# dynamic: only for this Exposure
exp = Exposure(255020, telemetry_fields=[
    TelemetryField(
        name='dust_5micron', table='environmentmonitor_dust',
        columns=['mayall_particle_1_micron_5'],
        max_delta_seconds=3600),
])
exp.telemetry_field('dust_5micron')
# -> {'mayall_particle_1_micron_5': 18, 'time_recorded': ...,
#     'delta_seconds': -0.58}

# static: register once; every later Exposure() picks it up
from telemetry_mining.telemetry import DEFAULT_TELEMETRY_FIELDS
DEFAULT_TELEMETRY_FIELDS.append(TelemetryField(
    name='dust_5micron', table='environmentmonitor_dust',
    columns=['mayall_particle_1_micron_5'], max_delta_seconds=3600))
# works with no extra argument
Exposure(255021).telemetry_field('dust_5micron')
```

`TelemetryField` fields:

| Field | Default | Meaning |
|---|---|---|
| `name` | required | key used to look it up (`telemetry_field(name)`) |
| `table` | required | telemetry table name |
| `kind` | `'nearest'` | `'nearest'` (query_nearest) or `'window'` (query_window) |
| `columns` | `None` (all) | columns to select |
| `time_column` | `'time_recorded'` | the table's timestamp column |
| `schema` | `'telemetry'` | schema the table lives in |
| `when` | `'start'` | `'nearest'` kind only: exposure `'start'` or `'end'` |
| `pad_seconds` | `0.0` | `'window'` kind only: widen the exposure's time span |
| `max_delta_seconds` | `None` | `'nearest'` kind only: reject matches farther than this |

Related `Exposure` members:

```python
# the list of TelemetryField specs this instance uses
exp.telemetry_fields
exp.telemetry_field_names     # just their names
# run (or return the cached result for) one named field
exp.telemetry_field(name)
# {name: result} for every configured field
exp.all_telemetry_fields()
```

Nothing is queried until `telemetry_field`/`all_telemetry_fields` is actually
called — having many fields configured (whether passed dynamically or coming
from `DEFAULT_TELEMETRY_FIELDS`) costs nothing until they're used, and each
result is cached per name so repeated access is free. `telemetry_fields`
passed at construction (or the default list, if omitted) is **snapshotted**
at construction time — appending to `DEFAULT_TELEMETRY_FIELDS` later doesn't
retroactively change `Exposure` instances already built. Duplicate names in
the same list raise `ValueError` immediately, and looking up an unconfigured
name raises `KeyError`.

### Alarms

```python
# DataFrame, ordered by time_recorded
exp.alarms(*, pad_seconds=0.0, level=None, columns=None)
```

The operational **alarms** recorded while the exposure was happening — the same
time-window machinery as `telemetry()`, but against the `alarms.alarms` table
(the DESI alarm log, in its own `alarms` schema). Returns a pandas DataFrame of
the alarms whose `time_recorded` falls within `time_window` (widened by
`pad_seconds` on both ends), ordered by time, with the operator-relevant columns
by default:

`id, time_recorded, level, component, instance, message`

The boolean **alarm-handler routing flags** (`tcs`, `ocs`, `slack`,
`email_enabled`, `stop_exposure_loop`, `shutdown_gfa`, …) and acknowledgement
bookkeeping are deliberately omitted — they control *how* an alarm is dispatched,
not what it was. Pass `columns=` to choose your own set (e.g. add `alarm_id`).

```python
exp.alarms()  # every alarm during the exposure
# ...widen to catch one just before the shutter
exp.alarms(pad_seconds=60)
# only CRITICAL (also 'ALERT'/'WARNING'/'EVENT')
exp.alarms(level='CRITICAL')
exp.alarms(level=['CRITICAL', 'ALERT'])         # a list of severities
exp.alarms(columns=['time_recorded', 'level', 'component',
                    'alarm_id', 'message'])
```

`level` post-filters the returned frame by the alarm severities (`CRITICAL` /
`ALERT` / `WARNING` / `EVENT`, the table's own `alarms_level_check`). Column and
schema names get the same identifier validation and safe quoting as
`telemetry()`. `alarms.alarms` lives in a different schema, but the DB layer is
schema-generic, so this reuses the existing connection code — no new plumbing.

**Global search — `find_alarms`.** `exp.alarms()` is *per-exposure*; for the
complementary "every alarm of this type across the whole log" question, use the
module-level `find_alarms`:

```python
from telemetry_mining import find_alarms

# one alarm type, all time, ordered by time
find_alarms(alarm_id=9200)
find_alarms(level=['CRITICAL', 'ALERT'], since=t0, until=t1)
find_alarms(component='OCS', message_like='%mount offset%',
            columns=['time_recorded', 'level', 'message'], limit=100)
```

All filters (`alarm_id`, `level`, `component`, `since`/`until`, `message_like`)
are optional and ANDed; values are parameterized and `columns` are
identifier-validated. Returns a DataFrame ordered by `time_recorded`.

**Mapping an alarm back to its exposure — `Exposure.at_time`.** A global alarm
carries a timestamp but no exposure id; `Exposure.at_time(when)` is the
time-based inverse of `time_window` — the exposure that was open at `when`
(latest `date_obs ≤ when`), or `None`:

```python
# the exposure running when the alarm fired
exp = Exposure.at_time(alarm_time)
in_window = (exp is not None and
             exp.time_window[0] <= alarm_time <= exp.time_window[1])
```

The returned Exposure has its `db_row` primed, so pulling its columns (mount
pointing, etc.) costs no extra query. Together, `find_alarms` + `Exposure.at_time`
let a notebook go alarm → exposure → pointing without any hand-written SQL.

### Offline QA / reduction row

```python
exp.redux_row     # pandas Series from exposures-daily.csv, or None
```

`None` (not an exception) when the expid isn't in the offline reduction table
yet — normal for calibration/engineering exposures, exposures taken very
recently, or a site with no redux pipeline at all (`Config.redux_root is
None`, e.g. KPNO — see [Deployment](#deployment-nersc-and-kpno)). Backed by a
module-level cache shared across all `Exposure` instances in the process;
see [Caching and cost model](#caching-and-cost-model).

```python
exp.exposure_table_flags   # dict or None
```

A second, unrelated offline source: `redux/daily/exposure_tables/<YYYYMM>/exposure_table_<night>.csv`
— one small CSV *per night* (not one big file like `exposures-daily.csv`),
from the pipeline's own processing bookkeeping (`desispec.workflow.exptable`).
It covers every exposure taken that night, including calibration frames
(`zero`/`dark`/`arc`/`flat`) that `exposures-daily.csv` doesn't include at all.

`exposure_table_flags` returns only the fields that add real information
beyond `redux_row`/`db_row` — everything else in that CSV (`EXPTIME`,
`AIRMASS`, `TILEID`, ...) duplicates what's already available elsewhere:

```python
{
    # how far the pipeline processed this exposure
    'LASTSTEP':   'all',
    # which cameras exist, as a compact encoding
    'CAMWORD':    'a0123456789',
    'BADCAMWORD': None,  # which cameras are excluded (None = none)
    # excluded '{camera}{petal}{amp}' entries (None = none)
    'BADAMPS':    None,
    'EXPFLAG':    ['low_sn'],  # quality flags (see below)
    # which header fields were corrected, and to what
    'HEADERERR':  [],
}
```

`LASTSTEP`, `CAMWORD`/`BADCAMWORD`, `BADAMPS`, and `EXPFLAG` are all
closed/enumerated vocabularies defined by `desispec.workflow.exptable` on
the installed pipeline (verified against that source, not assumed):

- **`LASTSTEP`** — one of `ignore`, `skysub`, `stdstarfit`, `fluxcal`, `all`
  (`get_last_step_options()`). How far the pipeline processed this exposure,
  inclusive of the named step.
- **`CAMWORD`/`BADCAMWORD`** — `desispec.io.util.create_camword`/`decode_camword`'s
  encoding: `'a'` + spectrograph numbers means all 3 cameras (b/r/z) present
  for those spectrographs; e.g. `a01234678b59z9` means spectrographs
  0,1,2,4,6,7,8 fully present, plus just `b` for 5/9 and just `z` for 9.
  `BADCAMWORD` uses the same encoding for cameras to *exclude*.
  `Exposure.paths.cframe(...)`/`cframe_path`/etc. don't consult this — it's
  informational, for deciding whether to trust/skip a camera's data.
- **`BADAMPS`** — comma-separated `{camera}{petal}{amp}` entries, e.g.
  `'b7D,z8A'` (petal = spectrograph number 0–9, amp = CCD quadrant A–D).
- **`EXPFLAG`** — a list of zero or more flags from a fixed vocabulary
  (`get_exposure_flags()`): `good`, `extra_cal`, `low_flux`, `short_exposure`,
  `low_sn`, `low_speed`, `aborted`, `metadata_missing`, `metadata_mismatch`,
  `misconfig_cal`, `misconfig_petal`, `off_target`, `no_stdstars`, `test`,
  `corrupted`, `junk`, `bad`.
- **`HEADERERR`** — a list of `key:->value` corrections applied to this
  exposure's metadata (e.g. `['SEQTOT:->1']` means `SEQTOT` was corrected to 1).

`EXPFLAG`/`HEADERERR` are parsed from `desispec`'s own on-disk convention:
entries joined by `'|'` with a trailing `'|'`, where a bare `'|'` means "no
entries" (confirmed against real rows, not assumed — a naive `.split('|')`
would misread that as one empty-string entry). `BADCAMWORD`/`BADAMPS` are
normalized from pandas' NaN-for-a-blank-CSV-cell to `None` — `bool(float('nan'))`
is `True` in Python, so leaving a blank field as NaN would make
`if flags['BADCAMWORD']:` silently misread "no bad cameras" as "there is one."

**`COMMENTS` is deliberately excluded.** Per the pipeline's own source
comment: *"These are not used by the workflow but useful for humans to put
notes for other humans."* Free-form text (e.g. `'efftime=8.2s lt 20.0'`
explaining a `low_sn` flag) — not a structured field worth building
filtering around. Not currently exposed at all, even as a pass-through.

`None` (not an exception) if this site has no redux pipeline
(`Config.redux_root is None`), this night has no `exposure_table` file yet
(e.g. too recent), or this expid isn't in it. Cached per instance like
`redux_row`.

### Offline per-camera spectra (cframe)

For occasional special studies (e.g. per-fiber flux/SNR checks like
`~/Notebooks/linphi_splitflux.ipynb`) — **not** part of routine per-exposure
use, so these are deliberately plain methods rather than `cached_property`:
there are 30 cframe files per exposure (one per camera — `b0`–`b9`,
`r0`–`r9`, `z0`–`z9`), each tens of MB. Nothing here is ever touched by
`repr()`/`summary()`. Each is cached per camera after first read, so
repeated calls for the same camera cost nothing.

```python
exp.cframe_path(camera)  # Path to cframe-<camera>-<expid>.fits.gz
# FIBERMAP table: targeting/positioning, 500 rows
exp.cframe_fibermap(camera)
# SCORES table: per-fiber flux/SNR summary, 500 rows
exp.cframe_scores(camera)
# FIBERMAP + SCORES combined, indexed by (PETAL_LOC, DEVICE_LOC)
exp.cframe_table(camera)
# Several cameras at once, read in parallel (see Performance below)
exp.cframe_tables(cameras)
```

A cframe file has 8 extensions: `FLUX`/`IVAR`/`MASK`/`CHI2PIX` (per-fiber
per-wavelength-pixel arrays, `[500, npix]`), `WAVELENGTH` (shared 1D grid),
`RESOLUTION` (`[500, 11, npix]`), and the two table extensions above. Only
the tables are wrapped here — the pixel arrays aren't, since this project is
about telemetry/metadata correlation, not spectral extraction itself.

**Performance**: `cframe_table(camera)` reads both `FIBERMAP` and `SCORES`
from a single file open when neither is already cached, avoiding the two
separate opens that calling `cframe_fibermap`/`cframe_scores` independently
would each pay (gzip decompression gets re-paid on every open, not cached
across opens within the same process). A controlled A/B measurement (using
different camera files per method, so neither side gets an unfair OS
page-cache warm-up from the other) found one combined open ~30% faster on
average than two separate opens for real cframe files — a real but modest
win, since gzip/CFS I/O dominates either way. Both individual caches still
get populated from that one combined read, so a later standalone
`cframe_fibermap`/`cframe_scores` call is free either way. If you only ever
need one of the two, call it directly rather than going through
`cframe_table` — no reason to pay for the other extension's decompression.

Even combined, `cframe_table` is dominated by gzip decompression: `FIBERMAP`
and `SCORES` are the *last* two extensions in the file, after the much
larger `FLUX`/`IVAR`/`MASK`/`WAVELENGTH`/`RESOLUTION` pixel arrays, and gzip
isn't seekable — reaching them costs close to a full-file decompression
regardless of which extensions you actually ask for (confirmed: reading the
same two tables from an already-decompressed local copy of the file took
0.01s, vs. ~1-2.5s reading them directly from the `.gz`). That per-file cost
is structurally unavoidable while the files stay gzip-compressed with
tables last.

**`cframe_tables(cameras, max_workers=None)`** reads several cameras'
`cframe_table` at once, in parallel OS processes, to work around that fixed
per-file cost — useful when you need most/all cameras of one exposure (e.g.
all 10 `r{petal}` cameras for an R-band-only study). The decompression cost
above is CPU-bound C code that does not release Python's GIL, so plain
threads give no benefit (confirmed by direct measurement — threaded reads
were no faster, sometimes slower, than sequential); real OS processes do
scale it, close to linearly: a 10-worker pool reading all 10 r-camera
cframe files for one exposure measured ~3.8x faster than the equivalent
sequential `cframe_table` calls (~0.4s/camera vs. ~1.4s/camera). Returns
`(tables, errors)` — `tables` maps camera → the same DataFrame
`cframe_table(camera)` returns (and populates the normal per-camera caches,
so later individual calls are free); `errors` maps camera → the exception
hit reading it (e.g. a missing/pruned file for an old exposure), so a
failed camera is simply absent from `tables` rather than aborting the whole
batch — mirrors the try/except-and-skip pattern you'd otherwise write by
hand looping `cframe_table`. Uses the `forkserver` multiprocessing start
method rather than the Linux default `fork`, since this is meant to be
called from live Jupyter notebooks — Jupyter kernels are multi-threaded
(zmq/heartbeat threads), and forking directly from a multi-threaded process
is a known source of rare child-process deadlocks; `forkserver` avoids that
by forking from a clean helper process instead. Only worth parallelizing
across the cameras of *one* exposure — don't nest this with parallelism
across many exposures at once (e.g. several of these pools running
concurrently in an outer loop), which trades the speedup for real
shared-filesystem contention instead.

**`SCORES` carries no location columns of its own** (no `PETAL_LOC`,
`DEVICE_LOC`, or `FIBER`) — confirmed by direct inspection, not assumed. It's
guaranteed row-aligned with `FIBERMAP` within the same file instead: same row
count, `FIBER` sorted ascending, and `LOCATION == PETAL_LOC*1000 + DEVICE_LOC`
holds for every row. `cframe_table` does exactly what
`linphi_splitflux.ipynb` already did — `pd.concat([fibermap, scores], axis=1)`
then `.set_index(['PETAL_LOC', 'DEVICE_LOC'])` — as a plain, reusable method
that also lets you `.join()` the result straight against `exp.coords` (same
index).

```python
# one fiber's targeting + flux/SNR summary
exp.cframe_table('z3').loc[(3, 69)]
# add fiber-positioning columns too
exp.cframe_table('z3').join(exp.coords)
```

`cframe_path`/the readers raise `DataSourceUnavailableError` at a site with
no redux pipeline at all (`Config.redux_root is None`, e.g. KPNO) — cframes
live under the same redux tree as the offline QA table.

### GFA offline summary

```python
exp.gfa_row   # pandas Series, or None
```

A *separate* processing pipeline (not this project's telemetry/DB world, and
not part of `redux/`) that reduces nightly GFA (guider) images — full frames
and postage stamps — into per-exposure observing conditions: seeing
(`FWHM_ASEC`), atmospheric `TRANSPARENCY`, moon geometry
(`MOON_ILLUMINATION`/`MOON_ZD_DEG`/`MOON_SEP_DEG`), and fiber-loss fractions
(`FIBERFAC`/`FIBERFAC_ELG`/`FIBERFAC_BGS`, `FIBER_FRACFLUX*`), among ~29
columns total. Source: the most recent
`<gfa_root>/offline_matched_coadd_ccds_main-thru_*.fits` file (the date
suffix moves forward each time it's regenerated, so the path is resolved by
globbing for the latest match, not hardcoded), `EXPOSURE_SUMMARY_STRICT`
extension specifically.

That file actually has three extensions, and the choice of which one matters:

- `CAMERA_SUMMARY` — one row per **(exposure, individual GFA camera)** —
  too granular for exposure-level correlation, not used here.
- `EXPOSURE_SUMMARY` — one row per exposure, but includes some with
  incomplete/NaN measurements.
- `EXPOSURE_SUMMARY_STRICT` — **what `gfa_row` uses.** A strict subset of
  `EXPOSURE_SUMMARY` (confirmed: every `EXPOSURE_SUMMARY_STRICT` expid is
  also in `EXPOSURE_SUMMARY`, 192 fewer out of 36761 at the time this was
  checked) that drops exposures with incomplete data — confirmed `FWHM_ASEC`
  is NaN-free across all of `EXPOSURE_SUMMARY_STRICT`, while 81 of the 192
  dropped rows have NaN there (and more when checking other columns
  together) — a reliability filter, not an arbitrary cut.

`None` if unavailable: no GFA offline source at this site
(`Config.gfa_root is None`), no matching file found, or this expid isn't in
the quality-filtered `STRICT` set. `gfa_summary_row`/`load_gfa_summary` in
`telemetry_mining.gfa` are the underlying functions if you need the whole
table rather than one exposure's row.

### FIBERQA

```python
exp.fiberqa   # dict, or None
```

The `FIBERQA` header from this exposure's offline
`exposure-qa-<expid>.fits` file (same directory, and same rolling retention,
as [cframe](#offline-per-camera-spectra-cframe) files — present for recent
exposures, pruned for old ones). That same file also has a `PETALQA` table
with per-petal detail — see [PETALQA](#petalqa) below.

```python
{
    'NGOODFIB': 4362,          # number of fibers passing QA
    'NGOODPET': 10,            # number of petals passing QA
    'WORSTRDN': 4.57,  # worst (highest) CCD read noise across cameras
    'FPRMS2D': 0.0064,  # fiber positioning RMS (2D), post-hoc QA
    'EFFTIME': 230.08,         # see note below
}
```

`NGOODFIB`/`NGOODPET`/`WORSTRDN` are genuinely new information — no
equivalent per-exposure QA-outcome count exists anywhere else in this
package. Two are **not** as new as they look:

- `FPRMS2D` is related to but **not the same as** `db_row['posrms']` —
  confirmed different values for the same real exposure (0.0065 vs 0.0042).
  Different measurement (real-time positioner telemetry vs. post-hoc QA),
  not a duplicate — worth having, just don't assume they should match.
- `EFFTIME` is confirmed **near-identical** to `redux_row['EFFTIME_SPEC']`
  for the same real exposure (230.08 vs 229.8) — prefer `redux_row` if you
  don't need the rest of this dict.

`None` if unavailable: no redux pipeline at this site
(`Config.redux_root is None`), or this exposure's `exposure-qa` file has
been pruned or never existed.

### PETALQA

```python
exp.petalqa   # DataFrame indexed by PETAL_LOC (10 rows), or None
```

The `PETALQA` table from the same `exposure-qa-<expid>.fits` file as
[`fiberqa`](#fiberqa) — same directory and same rolling retention, so
`None` under the same conditions (`Config.redux_root is None`, or the file
has been pruned or never existed).

Most columns here are genuinely new — no equivalent per-petal breakdown
exists anywhere else in this package:

- `NGOODPOS`/`NGOODFIB`/`NSTDSTAR` — positioner/fiber/standard-star counts
  passing QA, **per petal**. (`FIBERQA`'s `NGOODFIB`/`NGOODPET` in the
  header above are exposure-level totals; this is the per-petal detail
  behind them.)
- `WORSTREADNOISE`, `STARRMS`, `NCFRAME` — per-petal read noise, flux-cal
  residual RMS, and cframe count.
- `BSKYTHRURMS`/`RSKYTHRURMS`/`ZSKYTHRURMS`, `BSKYCHI2PDF`/`RSKYCHI2PDF`/
  `ZSKYCHI2PDF`, `BTHRUFRAC`/`RTHRUFRAC`/`ZTHRUFRAC` — per-camera-arm,
  per-petal sky-subtraction and throughput QA.

Two column groups **do** duplicate exposure-level data available elsewhere
— prefer those if you only need the whole-exposure number:

- `TSNR2_<TRACER>_<BAND>` (24 columns) — same target-class S/N² metrics as
  `redux_row['TSNR2_<TRACER>']`/`exposures-daily.csv`, but per petal/camera
  rather than summed across the exposure.
- `SKY_MAG_{G,R,Z}_SPEC` — same quantity as `fiberqa['SKY_MAG_{G,R,Z}_SPEC']`
  (whole-exposure), but per petal.

See `FIELDS.md` for the full column list with descriptions and example
values.

### FIBERQA per-fiber table

```python
# DataFrame indexed by (PETAL_LOC, DEVICE_LOC), 5000 rows, or None
exp.fiberqa_table
```

The `FIBERQA` extension's per-fiber table data (as opposed to its header,
which is [`fiberqa`](#fiberqa) above) — one row per fiber across the
**whole focal plane** (not per-camera like `cframe_table`'s 500-row
FIBERMAP). Same file/availability/retention as `fiberqa`/`petalqa`.

Most notably: `QAFIBERSTATUS` (per-fiber QA status bitmask, 0 = good — the
detail behind `fiberqa['NGOODFIB']`/`petalqa['NGOODFIB']`) and
`EFFTIME_SPEC` (per-fiber effective spectroscopic time, finer-grained than
`fiberqa['EFFTIME']`). Also carries `TARGETID`/targeting/positioning
columns — see `FIELDS.md` for the full list.

### Standard-star flux calibration table

```python
exp.calibstars   # DataFrame indexed by FIBER, ~100-150 rows, or None
```

`calibstars-<expid>.csv` — one row per spectrophotometric standard star used
for this exposure's flux calibration, same directory/availability/retention
as `cframe`/`exposure_qa` (a plain CSV, not FITS). Per the official DESI
datamodel docs:

- `RCALIBFRAC` — ratio of r-band spectroscopic flux to model flux, **normalized by
  the per-exposure median** (so it measures within-exposure fiber-to-fiber variation,
  not absolute throughput). The natural quantity for a calibration-quality comparison
  (e.g. linphi vs. regular positioners). **⚠️ Its construction changed around mid-2025**
  (a flat→psf aperture correction was added, desispec PR #2484) — see the
  [data-uniformity caveat](#data-uniformity-caveat-dailies-are-not-uniformly-reprocessed)
  and `MEASURED_VS_EXPECTED_FLUX.md` for what it means and which variable to use for the
  absolute "measured vs. expected" comparison.
- `EBV` — SFD98 Galactic extinction.
- `MODEL_COLOR`/`DATA_COLOR` — model/measured G-R color.
- `X`/`Y` — focal-plane position (mm).
- `VALID` — whether the star was kept (1) or rejected (0): a 3-sigma
  `RCALIBFRAC` outlier across petals, or a G-R color mismatch > `0.2*EBV`.

**`FIBER` here is the whole-focal-plane 0-4999 numbering** (same as
`cframe_table`/`fiberqa_table`'s `FIBER` column) — this table is *not*
indexed by `(PETAL_LOC, DEVICE_LOC)`. `FIBER // 500 == PETAL_LOC` always
holds, but `DEVICE_LOC` has no formula; join against `fiberqa_table` (one
call, whole focal plane) or `cframe_table(camera)` on `FIBER` to get it:

```python
fiber_loc = (exp.fiberqa_table.reset_index()
             .set_index('FIBER')[['PETAL_LOC', 'DEVICE_LOC']])
calib_with_loc = exp.calibstars.join(fiber_loc)
```

Also works for older exposures reduced under a different specprod —
`calibstars` (like `cframe`/`exposure_qa`) honors `Config.redux_release`,
e.g. `dataclasses.replace(Config.default(), redux_release='matterhorn')`.

### Custom table sources

```python
from telemetry_mining.tables import TableSource

exp.table_sources  # list of TableSource specs this instance uses
exp.table_source_names     # just their names
# run (or return the cached result for) one named source
exp.table_source(name)
exp.all_table_sources()  # {name: result} for every configured source
```

For data you already have that's indexed (or has a column) by `EXPID` —
results of a previous query you saved, a table that became available
later, anything not built into this package. Same shape as
[`TelemetryField`](#telemetry-fields-declarative-per-exposure-lookups):
register dynamically via `Exposure(..., table_sources=[...])`, or
process-wide via `tables.DEFAULT_TABLE_SOURCES.append(...)` — either way,
nothing is loaded until `table_source(name)` is called, and the result is
cached per name afterward.

```python
from telemetry_mining.tables import TableSource

# a DataFrame you already have in memory (e.g. a saved previous query)
exp = Exposure(255020, table_sources=[
    TableSource(name='my_query', dataframe=my_df),
])
exp.table_source('my_query')

# or a file -- .csv, or FITS with `extension` naming the HDU to read
TableSource(name='special', path=Path('/some/table.fits'),
            extension='MYEXT')

# or full control via a zero-arg loader (e.g. resolve a moving
# "latest file" glob)
TableSource(name='rolling',
            loader=lambda: pd.read_csv(find_latest_file()))
```

Exactly one of `dataframe`/`path`/`loader` must be given (raises
`ValueError` otherwise, at construction). `index_column` defaults to
`'EXPID'` but is itself a parameter, since not everything calls it that
(`db_row`/`stars`/`gfa_row` use lowercase `'expid'`/`'EXPID'` inconsistently
across sources already). A `dataframe` source is **never mutated** — it's
re-indexed into a new frame if needed, your original is untouched.
`path`-based sources are cached by `(mtime, size)`, same as `redux_row`;
`loader`-based sources are responsible for their own caching if wanted.
Duplicate names in the same list raise `ValueError` at construction (like
`TelemetryField`); looking up an unconfigured name raises `KeyError`.

**Worked example — WIYN seeing (external, time-stamped → EXPID).** The WIYN
telescope (also on Kitt Peak) logs seeing on its own clock — an independent
site-seeing monitor, correlated with but not identical to DESI's. Since it's
time-stamped, not EXPID-keyed, `scripts/build_wiyn_seeing.py` matches each
exposure to the nearest-in-time WIYN FWHM within a maximum time gap (`--max-dt`,
default 30 min; matched to the exposure midpoint) and writes an EXPID-indexed
`data/wiyn_seeing.csv`. Register that as a `TableSource`:

```python
from telemetry_mining.tables import TableSource

exp = Exposure(expid, table_sources=[
    TableSource('wiyn_seeing', path=Path('data/wiyn_seeing.csv')),
])
# None if this exposure had no WIYN match
row = exp.table_source('wiyn_seeing')
fwhm = None if row is None else row['WIYN_FWHM']
```

Columns: `WIYN_FWHM` (arcsec), `WIYN_DT_MIN` (signed minutes, WIYN − exposure
midpoint), `WIYN_SOURCE` (measurement type — e.g. drop `Focus` if wanted),
`WIYN_UT`. Only matched exposures are written, so `table_source()` returns
`None` for the rest — the clean "no data" semantics. Two caveats: coverage is
limited to WIYN's own date range (most historical exposures have no match), and
the match is only as good as the `--max-dt` you allow (seeing varies on
minutes; a looser gap is a coarser proxy). This is the general recipe for
**any** external time-stamped feed: pre-match to EXPID once, expose it as a
`TableSource`.

**To (re)build the table** — when earlier/later WIYN data arrives (no special
tooling or assistant required):

```bash
python scripts/build_wiyn_seeing.py \
    --wiyn data/WIYN-Seeing-<file>.cvs --max-dt 30 \
    --out data/wiyn_seeing.csv
```

Offline this matches against `data/dar_exposure_pointing.csv`; at NERSC pass
`--exposures` a full `EXPID`/`mjd_obs`/`exptime` dump from `exposure.exposure`
to cover every exposure, not just the science subset. `python
scripts/build_wiyn_seeing.py --help` lists all options.

### Convenience

```python
exp.summary()   # cheap dict of scalars; never triggers guider I/O
repr(exp)       # 'Exposure(expid=255020)'
```

`summary()` includes `expid`, `night` (or `night_error` if resolution failed),
`sequence`/`tileid`/`exptime`/`date_obs`/`program`/`obstype`/`airmass` from
`db_row` (or `db_error` if that failed), and `in_redux_daily` (bool).

## Bulk exposure lookups

```python
from telemetry_mining import (
    find_exposures, find_last_exposure, ExposureRef)
```

For iterating over many exposures (the way `windshake.ipynb`-style analyses
do), rather than looking up one at a time.

```python
find_exposures(
    config: Config, *,
    sequence: str | None = None,
    night: int | None = None,
    night_range: tuple[int, int] | None = None,
    limit: int = 2000,
) -> list[ExposureRef]
```

At least one of `sequence`/`night`/`night_range` is required (raises
`ValueError` otherwise).

```python
find_exposures(config, sequence='DESI', night=20240925)
find_exposures(config, night_range=(20240901, 20240930), limit=5000)
```

```python
find_last_exposure(config: Config, sequence: str,
                   require_coords: bool = False) -> ExposureRef | None
```

Returns the most recent exposure for a sequence type, or `None`. With
`require_coords=True`, skips candidates that don't yet have a
`coordinates-<expid>.fits` file on disk (useful right after an exposure starts,
before its coordinates file has been written).

Both return **`ExposureRef`**, a lightweight frozen dataclass:

```python
ExposureRef(expid: int, night: int, sequence: str | None,
            directory: Path)
```

Turn a reference into a full accessor with `Exposure(ref.expid, night=ref.night, config=config)`.

These fix two real bugs in the equivalent `DOSlib.util.find_exposures`/
`find_last_exposure`: raw `%`-string-formatted SQL (ours is fully
parameterized), and always building the mountain-side `/exposures/desi` path
even when running at NERSC (ours honors `config.exposures_root`).

## Bulk selection and correlation (`select_exposures` / `harvest`)

```python
from telemetry_mining import select_exposures, harvest
```

Two primitives for correlation studies across many exposures, so the same
loop over `Exposure` objects doesn't get hand-rolled every time. No
plotting lives here or anywhere else in this package — both return plain
pandas objects; do the plotting/analysis with whatever you already use
(matplotlib, etc.).

**`select_exposures`** — one row per matching exposure. Use this for
population-level correlation (does seeing depend on mirror/air temperature
difference?) or to build a candidate list for `harvest` below (e.g. "which
exposures are at low declination, for a differential-refraction study?").

```python
select_exposures(
    where: str,  # raw SQL WHERE fragment against exposure.exposure
    # output column name -> spec (see below)
    columns: dict[str, Spec] | None = None,
    config: Config | None = None,  # None -> Config.default()
    # parameterize `where`, same as db.fetch_all
    params: Sequence | Mapping | None = None,
    # raw SQL ORDER BY fragment; None skips ordering
    order_by: str | None = "id",
    on_error: str = "raise",  # "raise" or "skip" -- see below
    # None = sequential (default); see below
    max_workers: int | None = None,
# EXPID, NIGHT, + one column per `columns` entry
) -> pandas.DataFrame
```

`where` is required (no default) so you can't accidentally scan the whole
table. Parameterize actual values via `params`, never by interpolating
them into `where` directly.

`order_by` defaults to `"id"` (ascending EXPID) — without an `ORDER BY`,
SQL makes no row-order guarantee at all, and results come back in whatever
order the query planner finds convenient (typically following whichever
index served the `WHERE`, not EXPID) — this surprised a user running a
`NIGHT_RANGE` selection and seeing EXPIDs come back shuffled. Pass
`order_by=None` to skip ordering (saves a sort step if you don't care), or
e.g. `order_by="night, id"` for something else.

```python
table = select_exposures(
    "night between %s and %s and program = %s",
    columns={
        # free -- read from the one bulk exposure.exposure query:
        "airmass": "db_row.airmass",  # a flat column
        "mount_ha": "db_row.tcs['mount_ha']",  # jsonb value
        "air_temp": "db_row.telescope['air_temp']",  # jsonb value
        # one lookup per matching exposure:
        "seeing_gfa": "gfa_row.FWHM_ASEC",  # offline GFA summary
        "etc_fracb": "header.ETCFRACB",  # a FITS header key
    },
    params=(20260101, 20260701, "dark"),
)
```

**`config` defaults to `Config.default()`** — the example omits it on purpose;
pass `config=...` only to point at a different site/DB. `EXPID` and `NIGHT` are
always in the returned frame; add derived columns with plain pandas afterward
(e.g. `table["x"] = table["a"] - table["b"]`).

**Reading `db_row` is free** — the `WHERE` filter already does one bulk
`SELECT *` from `exposure.exposure`, and `select_exposures` reuses that row, so
any spec into it costs nothing extra. Two forms:

- **flat column** → `db_row.<column>` (e.g. `db_row.airmass`, `db_row.exptime`,
  `db_row.mountha`). The name is the **`exposure.exposure` column name, which is
  lower-case** — unlike a FITS `header.<KEY>` spec, whose keys are UPPER-case
  (`header.AIRMASS`).
- **value inside a jsonb block** → `db_row.<block>['<key>']` (e.g.
  `db_row.tcs['mount_ha']`, `db_row.telescope['air_temp']`,
  `db_row.hexapod['rot_rate']`). The jsonb columns (`tcs`, `telescope`,
  `hexapod`, `etc`, `guider`, `dome`, `tower`, ...) auto-decode to dicts, so you
  dot into the block, then index the key. Also free.

See [FIELDS.md](FIELDS.md) for every `exposure.exposure` column and the keys in
each jsonb block. Every **other** prefix costs one lookup per matching exposure
— `header.<KEY>` (a FITS open), `gfa_row.<COL>`, `telemetry.<name>`, or a
callable — see [Caching and cost model](#caching-and-cost-model).

**`telemetry.<name>` specs need a registered field first.** A `telemetry.<name>`
spec resolves to `exp.telemetry_field('<name>')`, and `DEFAULT_TELEMETRY_FIELDS`
is **empty by default**, so an *unregistered* name raises `KeyError`. Register it
once (process-wide), then the spec works — handy when a quantity isn't in
`db_row` (e.g. mirror temperature; `db_row.pmirtemp` is often `None` even when
the telemetry table has it):

```python
from telemetry_mining.telemetry import (
    TelemetryField, DEFAULT_TELEMETRY_FIELDS)
DEFAULT_TELEMETRY_FIELDS.append(TelemetryField(
    name="mirror_avg_temp", table="environmentmonitor_telescope",
    columns=["mirror_avg_temp"]))
# now "telemetry.mirror_avg_temp" works as a columns spec
```

**Custom `TableSource`s (e.g. WIYN seeing) — join them after the fact.** Table
sources are **not** part of the dotted spec grammar (only `telemetry.<name>` is
special-cased). But a `TableSource` like WIYN is already an **EXPID-indexed**
table, so the clean approach is a pandas join onto the result:

```python
from telemetry_mining.tables import TableSource, load_table
wiyn = TableSource("wiyn_seeing", path="data/wiyn_seeing.csv")
table = table.merge(load_table(wiyn),
                    left_on="EXPID", right_index=True, how="left")
# -> adds WIYN_FWHM etc.; NaN for exposures with no WIYN match
```

The `TableSource` only *reads* the pre-built `data/wiyn_seeing.csv`; **building**
that csv from raw WIYN logs (the step that needs an exposure list) is the
separate `scripts/build_wiyn_seeing.py` — see
[Custom table sources](#custom-table-sources). To instead get it as a column
*inside* the `select_exposures` call, use a callable spec:

```python
from telemetry_mining.tables import table_source_row
def wiyn_fwhm(exp):
    row = table_source_row(wiyn, exp.expid)
    return None if row is None else row["WIYN_FWHM"]
# columns={..., "wiyn_fwhm": wiyn_fwhm}
```

**`on_error` — handling missing files in a bulk scan.** A spec touching a
file-based source (`header`, `gfa_row`, ...) can fail for a given exposure
if that file has been purged or was never transferred — a real, common
gap, not an edge case: one bulk scan hit 28 missing files out of 831
exposures in a recent 6-week window.

- `on_error="raise"` (default, unchanged behavior): the first failure
  propagates immediately — filter your own expid list first if you expect
  gaps and want to fail fast.
- `on_error="skip"`: an exposure with a failing spec is left out of the
  result entirely — if *any* column fails for an exposure, the whole
  exposure row is dropped, not just that one cell (matches the
  `skipped.append(exp)`/`continue` pattern already used by hand throughout
  `notebooks/`). What was skipped and why is recorded in the returned
  DataFrame's `.attrs["skipped"]` — a `{expid: exception}` dict, always
  present (empty under `"raise"`), not printed:

  ```python
  table = select_exposures(..., on_error="skip")
  skipped = table.attrs["skipped"]
  if skipped:
      print(f'{len(skipped)} exposures skipped: {list(skipped)}')
  ```

  This deliberately doesn't print or log anything itself — `.attrs` is the
  same lightweight escape hatch already used elsewhere for attaching
  metadata to a plain DataFrame rather than building a custom output
  container (see `mjd0` on ETC timeseries results, above). Report, count,
  or ignore it however fits your notebook.

**`max_workers` — parallelizing a per-exposure column spec (added
2026-07-20).** Default `None` means sequential, unchanged prior behavior.
Worth setting once a `columns` spec costs a real per-exposure round-trip
(e.g. a callable that queries `telemetry.guider_centroids` and fits a
line) and there are enough matching exposures for the wait to matter — a
selection using only `"db_row.*"` specs is already one bulk query and
gets no benefit. Uses a thread pool, not a process pool (unlike
`Exposure.cframe_tables`, which needs processes because `fitsio`'s C-level
gzip decompression doesn't release the GIL) — the per-exposure cost here
is typically DB network I/O, and `psycopg2` releases the GIL during a
blocking query, so threads genuinely help. Safe because `telemetry_mining.db`'s
connection cache is thread-local (each pool thread gets its own DB
connection, not a shared one) — this was **not** true before 2026-07-20;
don't call `max_workers` code against an older checkout.

Real, measured result (not a guess): a 29-exposure single-night selection
with a `rotation_rate_slope` callable (queries `guider_centroids`, fits a
line) went from 61.9s sequential (2.13s/exposure) to 15.7s with
`max_workers=8` (0.54s/exposure) — **~4x speedup**, with threaded and
sequential results verified identical row-for-row. `max_workers=16` gave
no further improvement over 8 for this workload (15.4s) — more threads
than that didn't help here, so 8 is a reasonable starting point rather
than assuming higher is always better.

With `on_error="raise"` and `max_workers` set, an exception still
propagates out of the call, but other in-flight lookups may finish first
(already-dispatched threads keep running) rather than stopping at the
exact first failure the way the sequential path does.

**`harvest`** — run a function per exposure across an explicit list of
expids. Use this once you have a candidate list (from `select_exposures`,
or your own), when what you want isn't one scalar per exposure but
something richer — a time series, a per-fiber table.

```python
harvest(
    expids: Sequence[int],
    fn: Callable[[Exposure], Any],
    config: Config | None = None,  # None -> Config.default()
    concat: bool = False,
    # None = sequential (default); see select_exposures's max_workers
    # docs
    max_workers: int | None = None,
) -> dict[int, Any] | pandas.DataFrame
```

`night` for every expid is resolved in a single bulk query up front
(instead of one round-trip per exposure just to resolve it) — the one
per-exposure DB cost `harvest` removes for free. Whatever `fn` itself
touches is still one round-trip per exposure per source; that's inherent
to per-exposure data (a FITS header, a time-windowed telemetry query, ...)
and isn't something this function batches away — see
[Caching and cost model](#caching-and-cost-model).

With `concat=False` (default), returns `{expid: fn(Exposure(expid))}` — use
this when results aren't row-comparable across exposures, e.g. a guider
time series of differing length per exposure:

```python
candidates = select_exposures(
    "targtdec between %s and %s and exptime > %s",
    params=(-30, -20, 900))
# EXPID/NIGHT are always included even with no `columns` given
series = harvest(candidates["EXPID"],
                 lambda exp: exp.guider_centroids)
# series: {expid: DataFrame}, one guider_centroids frame per exposure

for expid, frames in series.items():
    # obstime (frame observation time) is the physically correct clock
    # -- time_recorded is just the DB insert timestamp
    t0 = frames["obstime"].iloc[0]
    r0 = frames["rotation"].iloc[0]
    frames["elapsed_s"] = (frames["obstime"] - t0).dt.total_seconds()
    frames["rotation_drift"] = frames["rotation"] - r0
```

With `concat=True`, `fn` must return a DataFrame; results are pooled into
one DataFrame with an `EXPID` column inserted (a named index, e.g.
`fiberqa_table`'s `(PETAL_LOC, DEVICE_LOC)`, is preserved as a column
first). Exposures where `fn` returned `None` are skipped. Use this for
per-fiber/per-petal tables you want to group/join across exposures:

```python
from telemetry_mining.tables import TableSource

linphi_flag = TableSource(
    name="linphi", path="~/my_linphi_positioners.csv",
    index_column="LOCATION")

fiber_data = harvest(bright_expids, lambda exp: exp.fiberqa_table,
                     concat=True)
fiber_data = fiber_data.join(linphi_flag.load_table(), on="LOCATION")
grp = fiber_data.groupby("has_linphi_issue")["QAFIBERSTATUS"]
success_rate = grp.apply(lambda s: (s == 0).mean())
```

### Column/value specs

Used by `select_exposures`'s `columns` and directly available as
`telemetry_mining.resolve_spec(exp, spec)`. A spec is either a plain
callable, or a dotted path string naming an `Exposure` accessor and how to
walk into it:

```python
"header.ETCFRACB"                    # dict key
"gfa_row.FWHM_ASEC"                  # pandas Series member
"telemetry.mirror_avg_temp"  # exp.telemetry_field('mirror_avg_temp')
"db_row.hexapod['hex_trim'][2]"      # jsonb dict -> list -> index
"header.HEXPOS[2]"  # bracket indexing on the base value itself
```

`[n]` indexes a list/array; `['key']`/`["key"]` indexes a dict; either can
be chained. This mini-language deliberately does not guess at implicit
reinterpretation — e.g. `HEXPOS` is actually a comma-joined **string** in
the header (`"1347.3,-187.7,-1309.6,-18.4,32.3,-33.0"`), not a real list,
so `header.HEXPOS[2]` would index a *character*, not the third number.
Anything that needs real parsing like that should be a callable instead:

```python
"hexapod_focus": lambda exp: float(exp.header["HEXPOS"].split(",")[2])
```

## `ExposurePaths`

```python
# or: from telemetry_mining.paths import ExposurePaths;
# ExposurePaths(directory, expid)
exp.paths
```

A frozen dataclass (`directory`, `expid`) with one property per known file in
an exposure directory — pure path construction, no disk access:

| Property/method | File |
|---|---|
| `main_fits` | `desi-<expid>.fits.fz` |
| `coordinates` | `coordinates-<expid>.fits` |
| `etc_json` | `etc-<expid>.json` |
| `etc_png` | `etc-<expid>.png` |
| `centroids_json` | `centroids-<expid>.json` |
| `guide_cube` | `guide-<expid>.fits.fz` |
| `guide_frame0` | `guide-<expid>-0000.fits.fz` |
| `guide_rois` | `guide-rois-<expid>.fits.fz` |
| `focus` | `focus-<expid>.fits.fz` |
| `fvc` | `fvc-<expid>.fits.fz` |
| `platemaker` | `pm-<expid>.fits` |
| `platemaker_logs` | `pm-<expid>-logs.tar` |
| `sky` | `sky-<expid>.fits.fz` |
| `request_json` | `request-<expid>.json` |
| `checksum` | `checksum-<expid>.sha256sum` |
| `fiberassign(tileid)` | `fiberassign-<tileid:06d>.fits.gz` (keyed by **tileid**, not expid) |
| `cframe(redux_root, night, camera, redux_release='daily')` | `<redux_root>/<redux_release>/exposures/<night>/<expid>/cframe-<camera>-<expid>.fits.gz` |

## Errors

```python
from telemetry_mining.exceptions import (
    TelemetryMiningError, MissingDependencyError,
    ExposureNotFoundError, DatabaseUnavailableError,
    DataSourceUnavailableError,
)
```

All inherit from **`TelemetryMiningError`**.

- **`MissingDependencyError(module_name, original_error)`** — raised when
  `psycopg2` or `fitsio` fails to import. The message names a known-good
  interpreter directly, since this account's default Python has broken builds
  of both.
- **`ExposureNotFoundError(expid, detail)`** — no matching DB row, no directory
  on disk, or an unresolvable time window (including when the FITS header
  fallback itself is unavailable, e.g. purged files at KPNO). `.expid` is set.
- **`DatabaseUnavailableError(original_error)`** — wraps any `psycopg2`
  connection/query failure with a message pointing at the `DOS_DB_*` env vars
  and network/VPN access.
- **`DataSourceUnavailableError(message)`** — a data source isn't configured
  for the current site *at all* (currently: calling
  `redux.load_exposures_daily` directly when `Config.redux_root is None`,
  e.g. at KPNO) — distinct from a specific record being missing (that's
  `None`/`ExposureNotFoundError`) or the DB being unreachable.

## Command line

```
python -m telemetry_mining <expid> [<night>]
```

Prints `Exposure(expid, night=night).summary()`, one key per line. Useful as a
quick smoke test that the environment/DB/filesystem are all reachable.

## Module reference

`Exposure` and the bulk helpers are built from smaller, independently usable
functions. Every one takes an explicit `config` (use `Config.default()`) and
can be called on its own — reach for them when you want something more specific
than an `Exposure` accessor, or a raw query. Functions already given a full
treatment above (`select_exposures`, `harvest`, `resolve_spec`, `find_exposures`,
`find_last_exposure`, `Exposure.telemetry`/`telemetry_nearest`) are cross-linked
rather than repeated.

### `telemetry_mining.db` — direct database access

```python
from telemetry_mining import Config, db
```

Parameterized SQL over a **reused, thread-local connection** (one per thread per
`(host, port, dbname, user)`, opened on first use and kept warm — see
[Caching and cost model](#caching-and-cost-model)). Use these for any query the
higher-level accessors don't already cover: exploring a `telemetry` table,
joining `exposure.stars` yourself, one-off counts.

**Two rules that matter:**
1. **Pass values through `params`, never f-string them into the query.** Use
   `%s` placeholders and a tuple/list; psycopg2 quotes and type-adapts them.
   This is both a SQL-injection guard and a correctness one (dates, `None`,
   arrays adapt correctly; string-formatting them silently doesn't).
2. **Identifiers (schema/table/column names) can't be `%s` params.** If a table
   or column name is dynamic, validate it against an allowlist/regex, or compose
   with `identifier()` (below) — don't interpolate untrusted text.

---

**`db.fetch_all(config, query, params=None) -> list[dict]`**

Run a query and return **every row as a plain `dict`** (column name → value;
`jsonb` columns decode to `dict`/`list`). Reuses the cached connection; if it
went stale (server dropped an idle connection), discards it and retries once.

- `config` — a `Config`; almost always `Config.default()`.
- `query` — SQL string, with `%s` placeholders for any values.
- `params` — a sequence (or mapping, for `%(name)s` placeholders) of values for
  those placeholders, or `None` if the query has none.

```python
rows = db.fetch_all(
    Config.default(),
    "SELECT id, night, exptime FROM exposure.exposure "
    "WHERE night = %s AND exptime > %s",
    (20260702, 100),
)
len(rows)            # e.g. 47
# 1065.056 -- rows[0] is a dict keyed by column name
rows[0]["exptime"]
```

**Listing a table's columns** (the recipe from `FIELDS.md`), where the value is
a `%s` param but the schema/table names are literals in the query text:

```python
cols = db.fetch_all(
    Config.default(),
    "SELECT column_name, data_type FROM information_schema.columns "
    "WHERE table_schema = %s AND table_name = %s "
    "ORDER BY ordinal_position",
    ("telemetry", "environmentmonitor_telescope"),
)
# ['environmentmonitor_telescope', 'telescope_timestamp', ...]
[c["column_name"] for c in cols]
```

---

**`db.fetch_one(config, query, params=None) -> dict | None`**

The **first row** as a `dict`, or `None` if the query returned no rows. A thin
wrapper over `fetch_all` (same args). Use it for lookups you expect to hit one
row — add `LIMIT 1` so the DB stops early.

```python
row = db.fetch_one(Config.default(),
    "SELECT date_obs, mountha, mountdec "
    "FROM exposure.exposure WHERE id = %s", (255020,))
row["mountha"] if row else None
```

---

**`db.fetch_df(config, query, params=None) -> pandas.DataFrame`**

The whole result as a **pandas `DataFrame`** (one column per SQL column, in
SELECT order; an empty DataFrame if there were no rows). Same args as
`fetch_all`. Reach for this when you want to keep working in pandas — filtering,
joining, plotting.

```python
df = db.fetch_df(Config.default(),
    "SELECT * FROM telemetry.environmentmonitor_dust "
    "ORDER BY time_recorded DESC LIMIT 100")
df[["time_recorded", "mayall_particle_1_micron_5"]].describe()
```

---

**`db.connect(config)`** — context manager yielding a **brand-new, one-off**
psycopg2 connection that you are responsible for (the `with` block closes it).
For advanced/manual use only — explicit transaction control, a cursor you drive
yourself. Most callers want `fetch_all`/`fetch_one`/`fetch_df` instead, which
reuse a warm connection rather than paying a fresh TCP+auth handshake per call.

```python
with db.connect(Config.default()) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM exposure.exposure")
        (n,) = cur.fetchone()
```

---

**`db.identifier(name)`** → a `psycopg2.sql.Identifier`, and
**`db.sql_text(query)`** → a `psycopg2.sql.SQL` fragment. Safe SQL *composition*
for when part of the statement is a dynamic **identifier** (which `%s` can't
carry). Compose the statement from these and pass it to a cursor:

```python
import psycopg2.sql as S
from telemetry_mining import db
table = "environmentmonitor_tower"  # validated/known-safe name
stmt = S.SQL(
    "SELECT time_recorded, {col} FROM telemetry.{tbl} "
    "ORDER BY time_recorded DESC LIMIT %s"
).format(col=db.identifier("wind_speed"), tbl=db.identifier(table))
with db.connect(Config.default()) as conn, conn.cursor() as cur:
    cur.execute(stmt, (10,))
    latest = cur.fetchall()
```

---

**`db.close_all_connections() -> None`** — close and forget every cached
connection **for the calling thread** (worker threads spawned by
`max_workers` hold their own, released when those threads exit). Mostly for
tests/cleanup; you don't need it in normal notebook use.

### `telemetry_mining.telemetry` — time-window & nearest-in-time queries

```python
from telemetry_mining import telemetry
```

The schema-generic primitives behind [`Exposure.telemetry`](#telemetry-correlation)
and [`telemetry_nearest`](#telemetry-correlation). Call them directly when you
have explicit `start`/`end`/`when` datetimes rather than an `Exposure`.

**`telemetry.query_window(config, table, start, end, *, pad_seconds=0.0, columns=None, time_column='time_recorded', schema='telemetry', limit=None) -> pandas.DataFrame`**

All rows of `schema.table` whose `time_column` is between `start` and `end`
(inclusive), widened by `pad_seconds` on each end, ordered by `time_column`
ascending. `table`/`columns`/`time_column`/`schema` are identifier-validated and
safely quoted.

- `start`, `end` — tz-aware `datetime`s (directly comparable to a `timestamptz` column).
- `pad_seconds` — widen the window symmetrically.
- `columns` — list of columns to select, or `None` for all.
- `schema` — defaults to `'telemetry'`; set e.g. `'alarms'` to reuse this for another schema.
- `limit` — cap the row count.

```python
import datetime as dt
start = dt.datetime(2026, 7, 3, 4, 0, tzinfo=dt.timezone.utc)
end   = start + dt.timedelta(minutes=20)
telemetry.query_window(
    Config.default(), "environmentmonitor_tower", start, end,
    columns=["wind_speed", "wind_direction"])
```

**`telemetry.query_nearest(config, table, when, *, columns=None, time_column='time_recorded', schema='telemetry', max_delta_seconds=None) -> dict | None`**

The **single row** of `schema.table` closest in time to `when`. Runs two bounded,
index-friendly queries (nearest at-or-before and at-or-after `when`) rather than
scanning a window. Returns a `dict` with an added **`delta_seconds`** key (signed:
how many seconds after `when` the row falls; negative = before), or `None` if the
table is empty or the nearest row is farther than `max_delta_seconds`.

- `when` — a tz-aware `datetime`.
- `max_delta_seconds` — **pass this** for any table you don't know has continuous
  coverage, so a match from days away comes back as `None` instead of looking real
  (see the [gotcha](#known-gotchas)).

```python
telemetry.query_nearest(
    Config.default(), "environmentmonitor_dust", when,
    columns=["mayall_particle_1_micron_5"], max_delta_seconds=3600)
# -> {'mayall_particle_1_micron_5': 18,
#     'time_recorded': datetime(...), 'delta_seconds': -0.58}
# (or None)
```

**`telemetry.TelemetryField(...)`** and the mutable module list
**`telemetry.DEFAULT_TELEMETRY_FIELDS`** declare these lookups once and attach
them to exposures — see [Telemetry fields](#telemetry-fields-declarative-per-exposure-lookups).

### `telemetry_mining.redux` — offline reduction tables

```python
from telemetry_mining import redux
```

The backends for [`Exposure.redux_row`](#offline-qa--reduction-row) and
[`exposure_table_flags`](#offline-qa--reduction-row). The `load_*` functions
return the **whole** table (cached per process); the `*_row` functions return one
exposure's row (or `None`). **`None` means "not in the table" and is routine**
(unprocessed/too-recent/calibration exposures); the `load_*` functions instead
**raise `DataSourceUnavailableError`** if the site has no redux pipeline at all
(`Config.redux_root is None`, e.g. KPNO), because asking for the whole table there
is a caller mistake.

**`redux.load_exposures_daily(config, refresh=False) -> pandas.DataFrame`** —
the full `exposures-daily` table, indexed by `EXPID` (cached per process; keyed by
the CSV's `(mtime, size)`, so a long-lived kernel picks up nightly updates —
`refresh=True` forces a reread).

**`redux.redux_row(expid, config) -> pandas.Series | None`** — one exposure's
`exposures-daily` row, or `None`.

**`redux.load_exposure_table(config, night, refresh=False) -> pandas.DataFrame`** —
one night's `exposure_table_<night>.csv` (every exposure that night, calibration
frames included), indexed by `EXPID`.

**`redux.exposure_table_row(expid, night, config) -> pandas.Series | None`** —
one exposure's `exposure_table` row, or `None`. This is the raw source behind
`Exposure.exposure_table_flags`, and the full row (not just the curated flag
subset) — use it when you need a column the flags accessor doesn't surface.

```python
row = redux.exposure_table_row(255020, 20240925, Config.default())
None if row is None else row["LASTSTEP"]        # 'all'
```

### `telemetry_mining.gfa` — offline GFA (guider) summary

```python
from telemetry_mining import gfa
```

Backend for [`Exposure.gfa_row`](#gfa-offline-summary). Same `load_*`-raises /
`*_row`-returns-`None` contract as `redux`.

**`gfa.load_gfa_summary(config, refresh=False) -> pandas.DataFrame`** — the
`EXPOSURE_SUMMARY_STRICT` table, indexed by `EXPID` (resolved by globbing for the
latest `offline_matched_coadd_ccds_main-thru_*.fits`; cached per process). Raises
`DataSourceUnavailableError` if `Config.gfa_root is None` or no file is found.

**`gfa.gfa_summary_row(expid, config) -> pandas.Series | None`** — one exposure's
row, or `None` (no GFA source here, no file, or the expid isn't in the
quality-filtered STRICT set).

### `telemetry_mining.etc` — ETC JSON parsing

```python
from telemetry_mining import etc
```

Backends for [`Exposure.etc`/`etc_summary`/`etc_timeseries`](#etc-exposure-time-calculator-data).
Operate on a **file path** / the parsed dict, so they're usable without an
`Exposure`.

**`etc.load_etc(path) -> dict`** — parse a whole `etc-<expid>.json`.
**`etc.etc_summary(etc) -> dict`** — the scalar `header` block (`ETCTEFF`,
`ETCREAL`, `ETCTRANS`, `ETCSKY`, ...) from a parsed dict.
**`etc.etc_timeseries(etc, key) -> pandas.DataFrame`** — one time-series block
(`'shutter'`/`'thru'`/`'sky'`/`'accum'`) as a DataFrame; scalar entries in that
block (e.g. `mjd0`) are attached to `df.attrs`, not dropped.

```python
data = etc.load_etc(exp.paths.etc_json)      # or any path
etc.etc_summary(data)["ETCTEFF"]              # 16.43
etc.etc_timeseries(data, "accum").attrs["mjd0"]
```

### `telemetry_mining.tables` — custom per-exposure table sources

```python
from telemetry_mining.tables import TableSource
```

The [custom table source](#custom-table-sources) machinery. `TableSource` names a
table with one row per exposure; the two functions below are its plumbing (usually
you go through `exp.table_source(name)` instead).

**`TableSource(name, *, dataframe=None, path=None, loader=None, index_column='EXPID', extension=1)`** —
exactly one of `dataframe`/`path`/`loader` must be given (see
[Custom table sources](#custom-table-sources) for each, and the WIYN worked
example).

**`tables.load_table(source) -> pandas.DataFrame`** — the source's whole table
(loading + caching a `path` source by `(mtime, size)`; returning a `dataframe`
source as-is; calling a `loader`).
**`tables.table_source_row(source, expid) -> pandas.Series | None`** — this
exposure's row, or `None` if absent. `tables.DEFAULT_TABLE_SOURCES` is the
process-wide list.

```python
src = TableSource("wiyn_seeing", path="data/wiyn_seeing.csv")
tables.load_table(src).shape                  # whole matched table
tables.table_source_row(src, 255020)  # one exposure's row, or None
```

### `telemetry_mining.alarms` — alarm-log search

```python
from telemetry_mining import find_alarms
```

**`find_alarms(config=None, *, alarm_id=None, level=None, component=None, since=None, until=None, message_like=None, columns=None, limit=None) -> pandas.DataFrame`** —
global search over `alarms.alarms`, all filters optional and ANDed, ordered by
`time_recorded`. Fully documented with examples under [Alarms](#alarms) (alongside
`exp.alarms()` and `Exposure.at_time`). `config` defaults to `Config.default()`.

### `telemetry_mining.fits_io` — raw FITS readers

```python
from telemetry_mining import fits_io
```

The `fitsio`-based readers behind the `Exposure` file accessors. Each takes a
**path** and returns a plain dict / DataFrame, so you can read a file you already
have without constructing an `Exposure`. All fix the NumPy≥2.0 `newbyteorder()`
breakage present in the equivalent DOSlib helpers.

| Function | Reads | Returns |
|---|---|---|
| `read_header(path, extension='SPEC')` | a FITS header HDU | `dict` |
| `read_coordinates(path)` | `coordinates-<expid>.fits` `DATA` ext | DataFrame indexed by `(PETAL_LOC, DEVICE_LOC)` |
| `read_stationary(path)` | same file's `STATIONARY` ext | DataFrame |
| `read_fibermap(path)` | a cframe `FIBERMAP` ext | DataFrame (500 rows) |
| `read_scores(path)` | a cframe `SCORES` ext | DataFrame (500 rows) |
| `read_fibermap_and_scores(path)` | both, in one file open | `(fibermap_df, scores_df)` |
| `read_petalqa(path)` | `exposure-qa` `PETALQA` ext | DataFrame (10 rows) |
| `read_fiberqa_table(path)` | `exposure-qa` `FIBERQA` per-fiber table | DataFrame (5000 rows) |
| `read_fiberassign_table(path)` | `fiberassign-<tileid>` `FIBERASSIGN` ext | DataFrame (5000 rows) |

```python
# same dict as exp.header
hdr = fits_io.read_header(exp.paths.main_fits)
hdr = fits_io.read_header(some_path, extension="FIBERQA")
```

### `telemetry_mining.paths` — path & night resolution

```python
from telemetry_mining import paths
```

**`paths.resolve_night(expid, config) -> int`** — the observing night for an
expid, via one `exposure.exposure` query (what `Exposure.night` calls when you
don't pass `night`).
**`paths.exposure_directory(expid, night, config) -> Path`** — build the
`<exposures_root>/<night>/<expid:08d>` path, **without touching disk** (no
existence check, unlike `Exposure.directory`).

`find_exposures`, `find_last_exposure`, `ExposureRef`, and `ExposurePaths` also
live here and are documented under [Bulk exposure lookups](#bulk-exposure-lookups)
and [`ExposurePaths`](#exposurepaths).

### `telemetry_mining.query` — bulk selection & specs

**`select_exposures`**, **`harvest`**, and **`resolve_spec`** — the correlation
primitives, documented in full under
[Bulk selection and correlation](#bulk-selection-and-correlation-select_exposures--harvest)
and [Column/value specs](#columnvalue-specs).

## Caching and cost model

**At a glance — cost of pulling one field per exposure** (details below):

| Source | Cost per exposure |
|---|---|
| `db_row.<col>` and jsonb blocks | **cheapest** — one indexed lookup by primary key, and **free inside `select_exposures`** (bundled in the one bulk WHERE query) |
| `header.<KEY>` | one FITS header open (a file read) |
| `telemetry(...)` / `telemetry_field` | one indexed time-range query (`nearest` runs two); fast each, but **one round-trip per exposure** |
| `redux_row` / `gfa_row` / `exposure_table_flags` | a **big table read once per process**, then O(1) — first access pays it (~12 MB / ~400 MB), rest are free |
| `fiberqa` / `petalqa` / `calibstars` | one small per-exposure file open each |
| `cframe_table(camera)` | **slowest** — gzip-decompresses a whole cframe file (~1–2.5 s each); use `cframe_tables([...])` for parallel-process reads |

- Constructing `Exposure(expid)` does no I/O at all.
- Every property listed above (except `guide_frame`/`guide_cube_path` and the
  `cframe_*` methods) is a `functools.cached_property`: computed once per
  instance, on first access. Reuse the same `Exposure` object across multiple
  cells/functions rather than re-constructing it, to avoid redundant file
  reads/DB queries — this matters most for `time_window`/`telemetry(...)`,
  which otherwise repeat the `exposure.exposure` lookup.
- `cframe_fibermap`/`cframe_scores`/`cframe_table` are plain methods (not
  `cached_property`, since they're parameterized by camera) but cache their
  result per camera in an instance dict, so calling the same one twice for
  the same camera costs one file read, not two.
- `redux_row` is backed by a **module-level** cache (in `telemetry_mining.redux`)
  shared across every `Exposure` in the process, keyed by the CSV's
  `(mtime, size)` — the ~12MB file is read once per process, not once per
  exposure, and a long-lived notebook kernel will pick up nightly updates
  automatically. `exposure_table_flags` is cached the same way, but keyed
  per night's file (one small CSV per night, not one big file) — every
  `Exposure` on the same night shares one cached read. `gfa_row` is the same
  pattern again, one shared cache entry for the whole (~400MB) GFA summary
  file. `fiberqa` isn't a bulk table at all — it's a per-exposure file, same
  cost profile as `header`/`cframe_*` (one small file open per exposure).
- `table_source(name)` is cached per name per `Exposure` instance, same as
  `telemetry_field(name)`. Underlying `path`-based `TableSource`s share a
  module-level `(mtime, size)`-keyed cache (in `telemetry_mining.tables`,
  same pattern as `redux_row`); `dataframe`-based ones do no caching at all
  (the object's already in memory) but do re-run a cheap index check on
  first access per `Exposure` instance.
- **DB connections are reused**, not reopened per query. `db.fetch_all`/`fetch_one`/`fetch_df`
  share one connection per `(host, port, dbname, user, password)`, cached at
  module scope, rather than paying a fresh TCP+auth handshake on every call —
  this matters once a single `Exposure` can trigger half a dozen queries
  (`db_row`, `guider_centroids`, each `telemetry_field`, ...). If the cached
  connection turns out to be stale (e.g. the server dropped an idle
  connection), it's discarded and the query is retried once with a fresh one,
  automatically. Call `telemetry_mining.db.close_all_connections()` to force
  everything closed (mostly useful for tests/cleanup).
- Each `Exposure` still costs, roughly: one FITS header open (`header`), one DB
  query for the full 187-column row (`db_row`, also triggered internally by
  `time_window`), and one DB query per `telemetry(...)`/`telemetry_field(...)`
  call (two, for `'nearest'`-kind fields — a bounded query in each time
  direction). Connection reuse removes the handshake overhead from each of
  these, but each is still a distinct round-trip. For a handful to a few
  hundred exposures this is fine (validated against ~100 real exposures in
  `~/Notebooks/windshake_telemetry_mining.ipynb`); for tens of thousands
  (e.g. reproducing `windshake.ipynb`'s original `NIGHT>20210514` full-history
  range) this still means tens of thousands of individual round-trips — there
  is no bulk/vectorized telemetry query yet (one query covering many
  exposures at once) if that turns out to be too slow in practice.
- `cached_property` is not thread-safe, and the shared connection cache is
  process-global, not per-thread; treat `Exposure` instances and this package
  generally as single-thread/single-notebook-cell use.

## Known gotchas

- **`sequence='DESI'` alone excludes split follow-up exposures.** Only the *first*
  exposure of a split sequence (repeated short exposures of one tile, taken to
  limit cosmic-ray contamination in poor conditions) is tagged `sequence='DESI'`
  — every follow-up split exposure is tagged `sequence='_Split'` instead
  (confirmed against the DB: 251 `DESI` vs. 73 `_Split` rows in one 10-night
  window). Filter on `sequence = ANY(ARRAY['DESI', '_Split'])` if you want splits
  included.
- **Standard-star targeting bits live in a different column for `BACKUP`
  exposures.** `DESI_TARGET`'s `STD_FAINT`/`STD_WD`/`STD_BRIGHT` bits flag
  standard stars for the main DARK/BRIGHT survey, but `program='BACKUP'`
  exposures (bright/nearby targets for poor conditions) flag theirs in
  `MWS_TARGET` instead (`GAIA_STD_FAINT`/`GAIA_STD_WD`/`GAIA_STD_BRIGHT`) — found
  by running `notebooks/calibstars_linphi.ipynb` over a wide selection and
  hitting a `BACKUP` exposure that matched 0/297 fibers against `DESI_TARGET`
  alone. Both masks use identical bit positions (`0xE00000000`), just in
  different columns — check both unless you already know the exposure's
  program. See [FIBERASSIGN table](#fiberassign-table).
- **Guider image-cube access is a stub.** `guide_frame`/`guide_cube_path` give
  you a path or an unread `fitsio.FITS` handle; actually decoding
  postage-stamp/ROI data is not implemented.
- **Not every header field is in the DB row**, and vice versa — check both if
  a field you expect is unexpectedly `None` (see [Database record](#database-record)).
- **pandas + tz-aware datetimes**: if you store `exp.time_window` values into a
  DataFrame column, initialize that column with `None`, not `pd.NaT` —
  `pd.NaT` infers a naive `datetime64[ns]` dtype that raises
  `ValueError: Invalid value ... for dtype 'datetime64[ns]'` when you later
  assign a timezone-aware `datetime` into it. This is easy to miss if the
  assignment is inside a broad `try/except` (it was, in an early draft of
  `windshake_telemetry_mining.ipynb` — every single row silently hit this
  before the fix).
- **No KPNO *execution* confirmed yet.** The package is installed at KPNO
  (see [Deployment](#deployment-nersc-and-kpno)) and the mountain-side paths,
  DB behavior, and KPNO-specific limitations (~6 months of exposure files,
  no redux) are confirmed facts (from the person running DESI ops there),
  and the code has been written and tested (with synthetic fixtures
  simulating purged files, missing redux, etc.) to handle them — but it
  hasn't been confirmed actually exercised against live KPNO data/DB from
  this project's side. Only NERSC has been tested end-to-end against real
  data.
- **`FIBER` (0-4999, whole focal plane) is not the same thing as
  `(PETAL_LOC, DEVICE_LOC)`, and there's no formula between them beyond
  `FIBER // 500 == PETAL_LOC`.** `DEVICE_LOC` is a hardware positioner ID,
  not sequential — confirmed by inspecting real data (e.g. petal 3's `FIBER`
  values 1500-1999 map to scattered `DEVICE_LOC` values like 69, 78, 10, 111,
  ...). Sources indexed by `(PETAL_LOC, DEVICE_LOC)` (`coords`,
  `cframe_table`, `petalqa`, `fiberqa_table`) and sources indexed by `FIBER`
  alone (`calibstars`) need an explicit join via a source that carries both
  — `fiberqa_table`/`cframe_table` both do — not a computed index.
- **`telemetry_nearest`/`query_nearest` always returns *something* if the table
  has any rows at all**, even if the nearest one is from a year away — a
  table may simply not have data covering the exposure's time (e.g.
  `environmentmonitor_dust` only has rows from 2025-10-21 onward; querying it
  for an earlier exposure returns whatever the *first* row is, ~390 days
  away). Always pass `max_delta_seconds` for tables you don't already know
  have continuous coverage, so a nonsensical match comes back as `None`
  instead of silently looking like a real reading.
- **Different sources sometimes measure similar-sounding things differently
  — don't assume a match.** Confirmed for two real pairs so far:
  `fiberqa['EFFTIME']` vs. `redux_row['EFFTIME_SPEC']` (near-identical, safe
  to treat as the same quantity) vs. `fiberqa['FPRMS2D']` vs.
  `db_row['posrms']` (confirmed *different* values for the same exposure —
  related concepts, not the same measurement). Check before assuming two
  sources agree, the same way these two were checked.
- **`Config.gfa_root` being `None` at KPNO is an assumption, not confirmed**
  (unlike `redux_root`, which was) — it's inferred by analogy to `redux_root`
  since the GFA offline pipeline looks like another NERSC/survey-ops
  product, not something anyone at KPNO has verified.
