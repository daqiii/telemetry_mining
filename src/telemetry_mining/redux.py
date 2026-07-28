"""Cached access to the offline processing/QA tables under redux/daily/.

exposures-daily.csv covers every exposure (~12MB, updated nightly), so it is
loaded once per process and cached at module scope, keyed by (mtime, size)
so a long-lived process (notebook kernel, batch job) picks up nightly
updates without needing a restart or an explicit invalidation call.

exposure_tables/<YYYYMM>/exposure_table_<night>.csv is a second, unrelated
offline source: one small CSV per *night* (not one big file), from the
pipeline's own processing bookkeeping rather than a QA summary -- it
includes calibration exposures (zero/dark/arc/flat) that exposures-daily.csv
doesn't, and carries fields exposures-daily.csv has no equivalent for
(LASTSTEP, CAMWORD, BADCAMWORD, BADAMPS, EXPFLAG, HEADERERR). Cached the
same way, just one cache entry per night's file instead of one big table.
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .exceptions import DataSourceUnavailableError

_cache: dict[Path, tuple[tuple[float, int], "object"]] = {}
_exposure_table_cache: dict[Path, tuple[tuple[float, int], "object"]] = {}


def load_exposures_daily(config: Config, refresh: bool = False):
    """Load (or return the cached copy of) the exposures-daily table, indexed by EXPID.

    Raises DataSourceUnavailableError if this site's Config has no redux_root
    at all (e.g. KPNO has no offline/redux pipeline) -- calling this directly
    at such a site is a caller error, unlike redux_row's None-means-absent
    contract, which callers are expected to handle routinely.
    """
    import pandas as pd

    path = config.exposures_daily_csv
    if path is None:
        raise DataSourceUnavailableError(
            f"No offline/redux data source configured for site={config.site!r} "
            "(Config.redux_root is None)"
        )
    stat = path.stat()
    cache_key = (stat.st_mtime, stat.st_size)
    cached = _cache.get(path)
    if not refresh and cached is not None and cached[0] == cache_key:
        return cached[1]
    df = pd.read_csv(path)
    if "EXPID" in df.columns:
        df = df.set_index("EXPID", drop=False)
    _cache[path] = (cache_key, df)
    return df


def redux_row(expid: int, config: Config):
    """The exposures-daily row for this expid, or None if it's not present.

    Absence is normal (calibration/engineering exposures, an exposure taken
    too recently to be processed yet, or a site with no redux pipeline at
    all, e.g. KPNO) -- not an error.
    """
    if config.exposures_daily_csv is None:
        return None
    df = load_exposures_daily(config)
    if expid not in df.index:
        return None
    row = df.loc[expid]
    return row.iloc[0] if hasattr(row, "iloc") and row.ndim == 2 else row


def _exposure_table_path(config: Config, night: int) -> "Path | None":
    if config.redux_root is None:
        return None
    yyyymm = str(night)[:6]
    return config.redux_daily_dir / "exposure_tables" / yyyymm / f"exposure_table_{night}.csv"


def load_exposure_table(config: Config, night: int, refresh: bool = False):
    """Load (or return the cached copy of) one night's exposure_table CSV, indexed by EXPID.

    One row per exposure taken that night -- including calibration frames
    (zero/dark/arc/flat), not just science -- from the pipeline's own
    processing bookkeeping.

    Raises DataSourceUnavailableError if this site has no redux pipeline at
    all (Config.redux_root is None, e.g. KPNO); lets a plain
    FileNotFoundError propagate if redux exists but this particular night
    has no exposure_table file (e.g. too recent, or before this table format
    existed) -- calling this directly is a caller asking for one specific
    night's table, unlike exposure_table_row's None-means-absent contract.
    """
    import pandas as pd

    path = _exposure_table_path(config, night)
    if path is None:
        raise DataSourceUnavailableError(
            f"No offline/redux data source configured for site={config.site!r} "
            "(Config.redux_root is None)"
        )
    stat = path.stat()
    cache_key = (stat.st_mtime, stat.st_size)
    cached = _exposure_table_cache.get(path)
    if not refresh and cached is not None and cached[0] == cache_key:
        return cached[1]
    df = pd.read_csv(path)
    if "EXPID" in df.columns:
        df = df.set_index("EXPID", drop=False)
    _exposure_table_cache[path] = (cache_key, df)
    return df


def exposure_table_row(expid: int, night: int, config: Config):
    """The exposure_table row for this expid/night, or None if unavailable.

    Absence is normal -- no redux pipeline at this site, this night has no
    exposure_table file yet, or the expid isn't in it -- not an error.
    """
    path = _exposure_table_path(config, night)
    if path is None or not path.exists():
        return None
    df = load_exposure_table(config, night)
    if expid not in df.index:
        return None
    row = df.loc[expid]
    return row.iloc[0] if hasattr(row, "iloc") and row.ndim == 2 else row
