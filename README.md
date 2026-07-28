# telemetry_mining

Tools for analyzing DESI instrument telemetry and operational data, drawing
together exposure directories (FITS/JSON at NERSC), the replicator PostgreSQL
database (`telemetry` and `exposure` schemas), and offline processing/QA
table files (`redux/daily/*`).

**Documentation:**

- **[GUIDE.md](docs/GUIDE.md)** — the User Guide: task-oriented recipes and worked
  examples ("how do I select exposures and correlate telemetry?"). Start here.
- **[API.md](docs/API.md)** — the full API reference: every class/function with
  exact signatures, arguments, return types, and examples.
- **[FIELDS.md](docs/FIELDS.md)** — a glossary of the underlying FITS headers / CSV
  columns / database columns (what each one means and a real example value,
  independent of the Python API), plus an appendix of telemetry tables.

## Environment

This code needs a Python with working `psycopg2` and `fitsio` against real
DESI data. The account's default conda environment may not have these
compiled correctly. A known-good interpreter on Perlmutter:

```
/global/common/software/desi/perlmutter/desiconda/20260227-2.3.1/conda/bin/python3
```

or activate the DESI environment before running anything:

```
source /global/common/software/desi/desi_environment.sh master
```

DB connection details are read from the `DOS_DB_NAME`, `DOS_DB_HOST`,
`DOS_DB_PORT`, `DOS_DB_READER`, `DOS_DB_READER_PASSWORD` environment
variables (already set in the standard DESI environment).

This package intentionally depends on nothing but `psycopg2`, `fitsio`,
`pandas`, and `numpy` -- no dependency on DOSlib (or its own dependencies
like Pyro, which are irrelevant at NERSC). That keeps it installable in any
DESI Jupyter kernel or environment, not just the one it happened to be
developed in.

## Quick start

```python
from telemetry_mining import Exposure, find_exposures, find_last_exposure

exp = Exposure(255020)
exp.header_value("AIRMASS")
exp.coords                                    # fiber positioning DataFrame
exp.etc_summary                               # ETC scalar summary
exp.telemetry("environmentmonitor_telescope", pad_seconds=30)
exp.redux_row                                  # offline QA row, or None

# bulk lookups (e.g. to loop over exposures the way windshake.ipynb does)
find_exposures(exp.config, sequence="DESI", night=20240925)
find_last_exposure(exp.config, sequence="DESI", require_coords=True)
```

or from the command line:

```
python -m telemetry_mining <expid>
```

prints a summary of everything known about that exposure.

## Layout

- `src/telemetry_mining/config.py` — paths and DB connection config
- `src/telemetry_mining/db.py` — PostgreSQL connection + query helpers
- `src/telemetry_mining/paths.py` — exposure directory/file path resolution, plus
  bulk exposure lookups (`find_exposures`, `find_last_exposure`)
- `src/telemetry_mining/fits_io.py` — FITS header/table readers
- `src/telemetry_mining/etc.py` — ETC (exposure time calculator) JSON summaries
- `src/telemetry_mining/redux.py` — cached loader for the offline QA table
- `src/telemetry_mining/telemetry.py` — generic telemetry time-window queries
- `src/telemetry_mining/exposure.py` — `Exposure`, the unified per-exposure accessor

## Tests

```
pytest
```

runs the offline tests (synthetic fixtures, no NERSC/DB needed); tests
marked `live` are skipped by default. To also run those against the real
filesystem/database:

```
pytest --run-live
```
