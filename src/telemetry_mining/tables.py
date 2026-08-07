"""User-extensible, named, EXPID-indexed table sources.

The same shape as `telemetry.TelemetryField`/`DEFAULT_TELEMETRY_FIELDS`, but
for arbitrary tabular data the user already has -- results of a previous
query they saved, a table that became available later, anything indexed (or
with a column) by exposure ID. Register one dynamically via
`Exposure(..., table_sources=[...])`, or process-wide via
`DEFAULT_TABLE_SOURCES.append(...)` -- either way, nothing is loaded until
`Exposure.table_source(name)` is actually called, and the result is cached
per name afterward.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class TableSource:
    """A named table, one row per exposure, looked up by `index_column`.

    Exactly one of `dataframe`, `path`, or `loader` must be given:
    - `dataframe`: an already-in-memory pandas DataFrame -- e.g. the result
      of a query you already ran and want to reuse. Not cached (it's already
      in memory); re-indexed on first use per Exposure, non-destructively
      (your original DataFrame is never mutated).
    - `path`: a `.csv`, `.parquet`, or FITS (`.fits`/`.fits.gz`/`.fz`) file to
      load, cached by (mtime, size) so a long-lived process picks up a changed
      file without needing a restart. For FITS, `extension` selects which
      HDU to read (name or index; default 1, the first non-primary HDU).
    - `loader`: a zero-argument callable returning a DataFrame, for full
      control (e.g. resolving a moving "latest file" glob pattern, or
      combining several files) -- responsible for its own caching if wanted.
    """

    name: str
    dataframe: Optional[Any] = None
    path: Optional[Path] = None
    loader: Optional[Callable[[], Any]] = None
    index_column: str = "EXPID"
    extension: Any = None

    def __post_init__(self):
        given = [x is not None for x in (self.dataframe, self.path, self.loader)]
        if sum(given) != 1:
            raise ValueError(
                f"TableSource {self.name!r}: exactly one of dataframe, path, or loader must be given"
            )
        # accept a plain string (or any os.PathLike) for `path` -- coerce to Path
        # so _load_path's path.stat()/.suffixes work (frozen dataclass -> setattr)
        if self.path is not None and not isinstance(self.path, Path):
            object.__setattr__(self, "path", Path(self.path))


DEFAULT_TABLE_SOURCES: list = []

_cache: dict = {}


def _ensure_indexed(df, index_column: str):
    if df.index.name == index_column:
        return df
    if index_column not in df.columns:
        raise ValueError(
            f"index_column {index_column!r} is not a column of this table "
            f"(available: {list(df.columns)})"
        )
    return df.set_index(index_column, drop=False)


def _load_path(source: TableSource):
    import pandas as pd

    path = source.path
    stat = path.stat()
    cache_key = (stat.st_mtime, stat.st_size)
    cached = _cache.get(path)
    if cached is not None and cached[0] == cache_key:
        return cached[1]

    suffix = "".join(path.suffixes).lower()
    if suffix.endswith(".csv"):
        df = pd.read_csv(path)
    elif suffix.endswith(".parquet") or suffix.endswith(".pq"):
        df = pd.read_parquet(path)
    elif suffix.endswith(".fits") or suffix.endswith(".fits.gz") or suffix.endswith(".fz"):
        from .fits_io import _import_fitsio, _to_native_byteorder

        fitsio = _import_fitsio()
        ext = source.extension if source.extension is not None else 1
        with fitsio.FITS(str(path)) as f:
            data = f[ext].read()
        df = pd.DataFrame(_to_native_byteorder(data))
    else:
        raise ValueError(
            f"TableSource {source.name!r}: don't know how to load {path} "
            "(supported: .csv, .parquet, .fits/.fits.gz/.fz -- load it yourself and pass dataframe=... for anything else)"
        )
    df = _ensure_indexed(df, source.index_column)
    _cache[path] = (cache_key, df)
    return df


def load_table(source: TableSource):
    """Load (or return the cached/given copy of) a TableSource's full table."""
    if source.dataframe is not None:
        return _ensure_indexed(source.dataframe, source.index_column)
    if source.loader is not None:
        return _ensure_indexed(source.loader(), source.index_column)
    return _load_path(source)


def table_source_row(source: TableSource, expid: int):
    """The row for this expid in `source`'s table, or None if it's not present."""
    df = load_table(source)
    if expid not in df.index:
        return None
    row = df.loc[expid]
    return row.iloc[0] if hasattr(row, "iloc") and row.ndim == 2 else row
