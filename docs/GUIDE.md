# telemetry_mining User Guide

This is the **task-oriented** guide — "how do I do X". It's the companion to two
reference documents:

- **[API.md](API.md)** — the exact signature, arguments, return type, and errors
  of every class and function. When this guide says "see the reference," it means
  there.
- **[FIELDS.md](FIELDS.md)** — a glossary of every field/column (what each header
  key, DB column, and table field means), plus an appendix of telemetry tables.

The **runnable, end-to-end examples live in the notebooks** under `notebooks/`.
This guide shows the key patterns inline and points you at the notebook that
demonstrates each one in full — see [Worked studies](#worked-studies-the-notebooks).

**The one idea:** you get **one Python object per exposure**, `Exposure(expid)`,
that lazily resolves everything about that exposure — the FITS header, fiber
coordinates, the ETC summary, guider metadata, the condensed DB record, a
telemetry time-window query, the offline QA/reduction row, alarms, and more —
so you stop hand-rolling file paths, raw SQL, and `fitsio`/`DATE-OBS` parsing.

> **⚠️ Before trending anything over time**, read the
> [data-uniformity caveat](API.md#data-uniformity-caveat-dailies-are-not-uniformly-reprocessed)
> in the reference: this reads the `daily` reduction, which is **not** uniformly
> reprocessed, so a change over time can be a pipeline change rather than the sky
> (the confirmed `RCALIBFRAC` mid-2025 shift is the canonical example).

## Contents

- [Setup: get the package importable](#setup-get-the-package-importable)
- [1. Look at a single exposure](#1-look-at-a-single-exposure)
- [2. Find the exposures you care about](#2-find-the-exposures-you-care-about)
- [3. Correlate telemetry with an exposure](#3-correlate-telemetry-with-an-exposure)
- [4. Population studies: one row per exposure (`select_exposures`)](#4-population-studies-one-row-per-exposure-select_exposures)
- [5. Richer per-exposure results (`harvest`)](#5-richer-per-exposure-results-harvest)
- [6. Bring in your own / external data (`TableSource`)](#6-bring-in-your-own--external-data-tablesource)
- [7. Alarms](#7-alarms)
- [8. Drop to raw SQL (`db.fetch_*`)](#8-drop-to-raw-sql-dbfetch_)
- [Worked studies (the notebooks)](#worked-studies-the-notebooks)
- [Pitfalls & tips](#pitfalls--tips)

## Setup: get the package importable

No install is required — put the checkout's `src/` on `sys.path`. Every notebook
in `notebooks/` starts with this exact cell, which reads the checkout location
from an environment variable (with a per-user fallback) so it works for anyone:

```python
import os, sys
tm_dir = os.getenv("DOS_TELEMETRY_MINING_DIR",
                   os.path.expanduser("~/telemetry_mining-trunk/src"))
sys.path.insert(0, tm_dir)

from telemetry_mining import (
    Exposure, Config, select_exposures, harvest, find_exposures)
```

**At KPNO** (the `msdos` or `desiobserver` accounts) you don't need the
`sys.path` line at all. Run `setup telemetry_mining` in the shell **first** —
before launching `python3` or starting the Jupyter server — and the `eups`
package manager puts the module on the import path for you. Then simply:

```python
from telemetry_mining import (
    Exposure, Config, select_exposures, harvest)
```

You need a Python with working `psycopg2` and `fitsio` (at NERSC:
`source /global/common/software/desi/desi_environment.sh master`, or the "DESI
master" Jupyter kernel; at KPNO `setup telemetry_mining` arranges this too). DB
credentials come from the `DOS_DB_*` environment variables already set in the
standard DESI environment — nothing to configure. For the full story, see
[API.md → Installation](API.md#installation--environment) and
[Deployment](API.md#deployment-nersc-and-kpno).

## 1. Look at a single exposure

Construct an `Exposure` and touch what you need — nothing is read until you do,
and each accessor is cached for the object's lifetime.

```python
exp = Exposure(255020)  # night resolved automatically via the DB

exp.summary()  # cheap scalar summary (never touches guider files)
exp.header_value("AIRMASS")  # 1.794, from the FITS header
exp.coords.shape  # (5133, 89): one row per fiber
exp.etc_summary["ETCTEFF"]  # 16.43, from etc-<expid>.json
exp.db_row["mountha"]  # from the exposure.exposure record (187 cols)
exp.redux_row["EFFTIME_SPEC"]  # offline reduction row, or None
```

**Tip that pays off everywhere:** build the `Exposure` **once** and reuse it.
Each accessor caches on the instance, so a second `exp.db_row` is free — but a
*new* `Exposure(255020)` starts cold and re-queries. If you already know the
night, pass it (`Exposure(255020, night=20240925)`) to skip a DB round-trip and
make every file-based accessor work with zero database access.

The full accessor tour — header, coordinates, ETC, guider, DB record, cframe,
QA tables, calibstars — is in [API.md → `Exposure`](API.md#exposure), and every
field they return is defined in [FIELDS.md](FIELDS.md).

## 2. Find the exposures you care about

Three ways in, from simplest to most powerful:

**The most recent exposure of a kind** — e.g. the latest science exposure:

```python
from telemetry_mining import find_last_exposure, Config
ref = find_last_exposure(Config.default(), sequence="DESI",
                         require_coords=True)
exp = Exposure(ref.expid, night=ref.night)
```

**A night, a night range, or a sequence** — a bulk list of lightweight refs:

```python
from telemetry_mining import find_exposures
refs = find_exposures(Config.default(),
                      night_range=(20240901, 20240930), limit=5000)
expids = [r.expid for r in refs]
```

**Any condition you can express in SQL** — this is the workhorse. `select_exposures`
takes a raw `WHERE` fragment against `exposure.exposure` (parameterize values with
`params`, never f-strings) and returns a DataFrame with `EXPID`/`NIGHT`:

```python
sel = select_exposures(
    "night between %s and %s and program = %s and exptime > %s",
    params=(20260101, 20260701, "dark", 100),
)
expids = list(sel["EXPID"])
```

> **Gotcha — splits.** `sequence = 'DESI'` selects only the *first* exposure of a
> split sequence; the follow-ups are tagged `'_Split'`. Use
> `sequence = ANY(ARRAY['DESI', '_Split'])` to include them. (More in
> [API.md → gotchas](API.md#known-gotchas).)

`select_exposures` can also compute columns per exposure in the same call — that's
[section 4](#4-population-studies-one-row-per-exposure-select_exposures).

## 3. Correlate telemetry with an exposure

This is the reason the package exists. There are two shapes of telemetry question.

**"Everything recorded during the exposure"** → `exp.telemetry(table)`, a
DataFrame of the rows whose timestamp falls in the exposure's time window (widen
with `pad_seconds`):

```python
exp.telemetry("environmentmonitor_telescope", pad_seconds=30)
exp.telemetry("environmentmonitor_tower",
              columns=["wind_speed", "wind_direction", "gust"])
```

**"The single value closest to the exposure"** → `exp.telemetry_nearest(table)`.
**Most `telemetry` tables are pure time series with no `expid` column**, so the
useful question is usually "the reading nearest the exposure's start," not the
whole window. It returns a `dict` (or `None`), with a signed `delta_seconds`:

```python
exp.telemetry_nearest(
    "environmentmonitor_dust",
    columns=["mayall_particle_1_micron_5"],
    max_delta_seconds=3600,
)
# -> {'mayall_particle_1_micron_5': 18, 'time_recorded': ...,
#     'delta_seconds': -0.58}      (or None)
```

> **Always pass `max_delta_seconds`** for a table you don't know has continuous
> coverage — otherwise a match from days away comes back looking like a real
> reading instead of `None`.

**Name a recurring lookup** so you don't repeat its arguments — a `TelemetryField`.
Attach it to one exposure, or register it process-wide so every later `Exposure`
picks it up:

```python
from telemetry_mining.telemetry import (
    TelemetryField, DEFAULT_TELEMETRY_FIELDS)

DEFAULT_TELEMETRY_FIELDS.append(TelemetryField(
    name="dust_5micron", table="environmentmonitor_dust",
    columns=["mayall_particle_1_micron_5"], max_delta_seconds=3600))

Exposure(255021).telemetry_field("dust_5micron")
# -> {'mayall_particle_1_micron_5': 18, ..., 'delta_seconds': ...}
```

A named field also becomes usable as a `"telemetry.<name>"` column spec in
`select_exposures` (next section). Don't know which telemetry table has what you
need? Browse the [FIELDS.md appendix](FIELDS.md#appendix-additional-telemetry-tables)
of 86 tables, or list any table's columns with `db.fetch_all` ([section 8](#8-drop-to-raw-sql-dbfetch_)).

**Full examples:** `windshake.ipynb` averages tower-wind telemetry over each
exposure's window; `mirror_temperature.ipynb` is a direct nightly telemetry query.

## 4. Population studies: one row per exposure (`select_exposures`)

Give `select_exposures` a `columns` dict and it resolves each spec **per matching
exposure**, returning one tidy row each — ready to correlate or plot. A spec is a
dotted path into an `Exposure` accessor, or a callable:

```python
table = select_exposures(
    "night between %s and %s and program = %s",
    columns={
        # offline GFA pipeline seeing
        "seeing_gfa": "gfa_row.FWHM_ASEC",
        # a FITS header key
        "etc_fracb": "header.ETCFRACB",
        # registered TelemetryFields (nearest-in-time values)
        "mirror_temp": "telemetry.mirror_avg_temp",
        "air_temp": "telemetry.air_temp",
        # a callable spec: arbitrary Python per exposure
        "hex_focus": lambda e: float(e.header["HEXPOS"].split(",")[2])
    },
    params=(20260101, 20260701, "dark"),
)
table["temp_diff"] = table["mirror_temp"] - table["air_temp"]
# then plot with matplotlib/etc. -- the package returns plain pandas
# and does no plotting of its own
```

Two options you'll want on real data:

- **`on_error="skip"`** — a file-based spec can fail if that exposure's file was
  purged/never transferred (a real, common gap). `"skip"` drops such exposures and
  records why in `table.attrs["skipped"]` (`{expid: exception}`) instead of raising.
- **`max_workers=8`** — resolve exposures concurrently when a spec costs a real
  per-exposure round-trip (e.g. a callable that queries `guider_centroids` and fits
  a line). Measured ~4× on a 29-exposure selection. A pure `"db_row.*"` selection is
  already one bulk query and needs none of this.

Full semantics (the free `db_row.*` specs, spec grammar, threading model) are in
[API.md → Bulk selection](API.md#bulk-selection-and-correlation-select_exposures--harvest)
and [Column/value specs](API.md#columnvalue-specs).

**Full examples:** `fieldrotation.ipynb` is a reusable X/Y/color template built on
exactly this (dotted-path specs); `fieldrotationcorrection.ipynb` swaps in a
callable spec; `obs_conditions.ipynb` uses header-keyword callback specs.

## 5. Richer per-exposure results (`harvest`)

When you want **more than one scalar per exposure** — a time series, a whole
per-fiber table — use `harvest(expids, fn)`, which runs `fn(Exposure)` for each
expid (resolving all the nights in one bulk query up front).

**`concat=False`** (default) returns `{expid: fn(exp)}` — for results that aren't
row-comparable, like a guider time series of differing length per exposure:

```python
# returns {expid: DataFrame}
series = harvest(expids, lambda e: e.guider_centroids)
for expid, frames in series.items():
    frames["drift"] = frames["rotation"] - frames["rotation"].iloc[0]
```

**`concat=True`** pools each returned DataFrame into one big frame with an `EXPID`
column added — for per-fiber/per-petal tables you want to group or join across
exposures. Return `None` to drop an exposure:

```python
def bright_fibers(e):
    tab = e.fiberqa_table
    return None if tab is None else tab[tab["EFFTIME_SPEC"] > 0]

# one pooled DataFrame with an EXPID column inserted
pooled = harvest(expids, bright_fibers, concat=True)
(pooled.groupby("EXPID")["QAFIBERSTATUS"]
       .apply(lambda s: (s == 0).mean()))
```

> **Performance caveat:** if `fn` itself reads many cframe files, use
> `exp.cframe_tables([...])` (parallel processes *within* one exposure) **without**
> also setting `harvest(max_workers=...)` — nesting a process pool under a thread
> pool oversubscribes the shared filesystem. See
> [API.md → cframe](API.md#offline-per-camera-spectra-cframe).

**Full examples:** `calibstars_linphi.ipynb` (`concat=True` + `max_workers=8`,
pooling standard-star rows) and `fiberflux_ratio_linphi.ipynb` (`concat=True` with
`cframe_tables` inside `fn`, so no `max_workers`).

## 6. Bring in your own / external data (`TableSource`)

Anything with one row per exposure — a saved query result, a CSV that became
available later, an external feed — can be attached as a `TableSource` and read
per exposure like any other accessor. Give it an in-memory DataFrame, a file, or a
loader callable:

```python
from telemetry_mining.tables import TableSource

exp = Exposure(255020, table_sources=[
    TableSource("my_query", dataframe=my_df),  # in-memory DataFrame
    TableSource("special", path="data/table.fits", extension="MYEXT"),
])
exp.table_source("my_query")  # this exposure's row, or None
```

**External *time-stamped* feeds** (not EXPID-keyed) get pre-matched to the nearest
exposure once, then exposed as an EXPID-indexed `TableSource`. The worked example
is WIYN seeing: `scripts/build_wiyn_seeing.py` matches each exposure to the nearest
WIYN FWHM within `--max-dt` and writes `data/wiyn_seeing.csv`:

```python
exp = Exposure(expid, table_sources=[
    TableSource("wiyn_seeing", path="data/wiyn_seeing.csv")])
row = exp.table_source("wiyn_seeing")  # None if no WIYN match
fwhm = None if row is None else row["WIYN_FWHM"]
```

This is the general recipe for **any** external time-stamped source: pre-match to
EXPID once, expose as a `TableSource`. Details, the rebuild command, and the
`index_column` option are in
[API.md → Custom table sources](API.md#custom-table-sources).

## 7. Alarms

Three complementary tools, all hiding the SQL:

- **`exp.alarms()`** — alarms recorded *during* one exposure (DataFrame, operator
  columns by default; filter with `level=`, widen with `pad_seconds=`).
- **`find_alarms(...)`** — *global* search across the whole alarm log by
  `alarm_id`, `level`, `component`, time range, or `message_like`.
- **`Exposure.at_time(when)`** — the exposure that was open at a timestamp; the
  bridge from a global alarm (which has a time but no expid) back to its exposure.

```python
from telemetry_mining import find_alarms

# every "large mount offset" alarm, all time
hits = find_alarms(alarm_id=9200)
# the exposure that was open when the first one fired
exp = Exposure.at_time(hits.iloc[0]["time_recorded"])
# its pointing -- db_row is already primed, so no extra query
exp.db_row["mountha"], exp.db_row["mountdec"]
```

`notebooks/alarm_9200_mount_offsets.ipynb` is the full worked example (alarm →
exposure → pointing, entirely module-based). Reference:
[API.md → Alarms](API.md#alarms).

## 8. Drop to raw SQL (`db.fetch_*`)

When no accessor covers what you need — exploring a telemetry table, a custom
join, a one-off count — query directly. Use `%s` placeholders and pass values
through `params` (never f-string them in):

```python
from telemetry_mining import Config, db

df = db.fetch_df(Config.default(),
    "SELECT * FROM telemetry.environmentmonitor_dust "
    "ORDER BY time_recorded DESC LIMIT 100")
rows = db.fetch_all(Config.default(),
    "SELECT id, night FROM exposure.exposure WHERE night = %s",
    (20260702,))
one = db.fetch_one(Config.default(),
    "SELECT date_obs FROM exposure.exposure WHERE id = %s",
    (255020,))
```

**List any telemetry table's columns** (handy before writing a query):

```python
cols = db.fetch_all(Config.default(),
    "SELECT column_name, data_type FROM information_schema.columns "
    "WHERE table_schema = %s AND table_name = %s "
    "ORDER BY ordinal_position",
    ("telemetry", "gfa_telemetry"))
[c["column_name"] for c in cols]
```

Many telemetry tables are already catalogued in the
[FIELDS.md appendix](FIELDS.md#appendix-additional-telemetry-tables). Full
`fetch_all`/`fetch_one`/`fetch_df`/`connect`/`identifier` docs:
[API.md → `db`](API.md#telemetry_miningdb--direct-database-access).

**Full example:** `mirror_temperature.ipynb` — the shortest notebook, a single
`fetch_df` nightly temperature query end to end.

## Worked studies (the notebooks)

The notebooks in `notebooks/` are the runnable, end-to-end examples — each a real
study that also doubles as a template for the pattern it uses.

**Read these first (new users):**

1. **`linphi_splitflux.ipynb`** — the single best introduction to the `Exposure`
   object: one cached handle reaching three sources (`db_row`, `coords`,
   `cframe_tables`) that share the `(PETAL_LOC, DEVICE_LOC)` index.
2. **`fieldrotation.ipynb`** — the cleanest intro to `select_exposures` and the
   `resolve_spec` dotted-path column specs, written as a reusable X/Y/color
   template. Teaches the "one bulk query, one row per exposure" mental model.
3. **`calibstars_linphi.ipynb`** — the definitive `select_exposures` +
   `harvest(concat=True)` pattern for pooling many rows per exposure across many
   exposures, including the `None`-to-skip convention and `max_workers`.

*(Gentlest on-ramp of all: `mirror_temperature.ipynb`, ~15 lines —
`Config.default()` + `db.fetch_df`.)*

| Notebook | Demonstrates | Key API used |
|---|---|---|
| `linphi_splitflux.ipynb` | One `Exposure` handle reaching 3 data sources; per-fiber flux across split exposures | `Exposure(...)` · `db_row` · `coords` · `cframe_tables` |
| `fieldrotation.ipynb` | Reusable X/Y/color template — one bulk query, one row per exposure | `select_exposures(columns=…)` dotted-path specs · `resolve_spec` · `attrs["skipped"]` |
| `fieldrotationcorrection.ipynb` | Same template with a **callable** column spec (guider-fit rotation slope) | `select_exposures(callable spec, max_workers=…)` · `guider_centroids` |
| `fieldrotation_correlation.ipynb` | Two spec sets (dotted + callable) over one population, joined on `EXPID` | two `select_exposures` calls · `guider_centroids` |
| `calibstars_linphi.ipynb` | Pool per-fiber calibration rows across many exposures; linphi vs regular | `select_exposures` + `harvest(concat=True, max_workers=8)` · `calibstars` · `fiberassign_table` · `coords` |
| `fiberflux_ratio_linphi.ipynb` | Bright-fiber delivered/expected flux ratio by positioner group | `harvest(concat=True)` (no `max_workers`) · `cframe_tables` |
| `obs_conditions.ipynb` | Dome-seeing: ΔT (mirror−air) vs seeing/throughput, from header keywords | `select_exposures` with header-callback specs · `header` |
| `windshake.ipynb` | Per-exposure wind telemetry vs whether exposures were accepted | `redux.load_exposures_daily` · `telemetry` · `time_window` · `header` |
| `mirror_temperature.ipynb` | Shortest end-to-end example — one parameterized query | `Config.default()` · `db.fetch_df` |
| `alarm_9200_mount_offsets.ipynb` | Large-mount-offset alarm → exposure → pointing (fully DB-based) | `find_alarms` · `Exposure.at_time` · `db_row` |

Two more notebooks — **`dar_fiber_loss_reproduction.ipynb`** and
**`dar_pointing_tests.ipynb`** — are self-contained *science/figure* notebooks
that read saved datasets and **do not call this package**; they belong to the DAR
reports (see `DAR_FIBER_LOSS_REPORT.md`) and are listed here only for completeness.

## Pitfalls & tips

Short list; each links to the full explanation in the reference.

- **Reuse the `Exposure` object** — accessors cache on the instance; re-constructing throws that away.
- **Trending over time?** The `daily` reduction isn't uniformly reprocessed — a trend can be a pipeline change ([caveat](API.md#data-uniformity-caveat-dailies-are-not-uniformly-reprocessed)).
- **`sequence='DESI'` drops split follow-ups** — use `ANY(ARRAY['DESI','_Split'])` ([gotchas](API.md#known-gotchas)).
- **`BACKUP` exposures flag standard stars in `MWS_TARGET`**, not `DESI_TARGET` ([gotchas](API.md#known-gotchas)).
- **Always pass `max_delta_seconds`** to `telemetry_nearest` for tables without known continuous coverage.
- **`FIBER` (0–4999) ≠ `(PETAL_LOC, DEVICE_LOC)`** — join through a table that carries both, don't compute it.
- **Not every header field is in `db_row`** and vice versa — check both if a value is unexpectedly `None`.
- **Storing `time_window` in a DataFrame column?** Initialize it with `None`, not `pd.NaT` (tz-aware dtype trap).

Full versions of all of these: [API.md → Known gotchas](API.md#known-gotchas).
