"""Cached access to the offline GFA (guider) summary file.

`/global/cfs/cdirs/desi/survey/GFA/offline_matched_coadd_ccds_main-thru_<date>.fits`
-- a separate processing pipeline (not this project's telemetry/DB world)
that reduces nightly GFA images (full frames and postage stamps) into
per-exposure conditions: seeing, transparency, moon geometry, fiber-loss
fractions, etc. The filename's date suffix moves forward each time the file
is regenerated, so the path is resolved by globbing for the most recent
match, not hardcoded.

We use the EXPOSURE_SUMMARY_STRICT extension specifically (not
EXPOSURE_SUMMARY or CAMERA_SUMMARY), confirmed by direct inspection:
EXPOSURE_SUMMARY_STRICT is a strict subset of EXPOSURE_SUMMARY (192 fewer
rows out of 36761 at the time this was checked) that drops exposures with
incomplete/NaN measurements -- e.g. FWHM_ASEC is NaN-free in STRICT, not so
outside it. CAMERA_SUMMARY is one row per (exposure, individual GFA
camera) -- too granular for exposure-level correlation, not used here.
"""

from __future__ import annotations

import threading
from pathlib import Path

from .config import Config
from .exceptions import DataSourceUnavailableError

_cache: dict = {}
# Serializes the load-and-cache below. Without it, concurrent callers (e.g.
# select_exposures with max_workers over an L_see/L_field/gfa_row spec) each open
# the same FITS file at once -- fitsio/CFITSIO is not thread-safe for that, and a
# garbled concurrent read can write a bad DataFrame into _cache, poisoning every
# later lookup. Cache *hits* are checked before taking the lock, so the steady
# state stays lock-free.
_cache_lock = threading.Lock()

_FILENAME_GLOB = "offline_matched_coadd_ccds_main-thru_*.fits"
_EXTENSION = "EXPOSURE_SUMMARY_STRICT"


def _gfa_summary_path(config: Config) -> "Path | None":
    """Most recent GFA offline summary file, or None if unavailable at this site."""
    if config.gfa_root is None:
        return None
    matches = sorted(config.gfa_root.glob(_FILENAME_GLOB))
    return matches[-1] if matches else None


def load_gfa_summary(config: Config, refresh: bool = False):
    """Load (or return the cached copy of) EXPOSURE_SUMMARY_STRICT, indexed by EXPID.

    Raises DataSourceUnavailableError if this site has no GFA offline source
    at all (Config.gfa_root is None) or no matching file is found there --
    calling this directly is a caller asking for the table, unlike
    gfa_summary_row's None-means-absent contract.
    """
    import pandas as pd

    from .fits_io import _import_fitsio, _to_native_byteorder

    path = _gfa_summary_path(config)
    if path is None:
        raise DataSourceUnavailableError(
            f"No GFA offline summary source configured/found for site={config.site!r} "
            f"(Config.gfa_root={config.gfa_root!r})"
        )
    stat = path.stat()
    cache_key = (stat.st_mtime, stat.st_size)
    cached = _cache.get(path)
    if not refresh and cached is not None and cached[0] == cache_key:
        return cached[1]
    with _cache_lock:
        # Re-check under the lock: another thread may have loaded it while we waited,
        # so only the first thread reads the FITS file and the rest reuse its result.
        cached = _cache.get(path)
        if not refresh and cached is not None and cached[0] == cache_key:
            return cached[1]
        fitsio = _import_fitsio()
        with fitsio.FITS(str(path)) as f:
            data = f[_EXTENSION].read()
        df = pd.DataFrame(_to_native_byteorder(data))
        if "EXPID" in df.columns:
            df = df.set_index("EXPID", drop=False)
        _cache[path] = (cache_key, df)
        return df


def gfa_summary_row(expid: int, config: Config):
    """The EXPOSURE_SUMMARY_STRICT row for this expid, or None if unavailable.

    Absence is normal -- no GFA offline source at this site, no matching
    file found, or this expid isn't in the STRICT (quality-filtered) set --
    not an error.
    """
    if config.gfa_root is None:
        return None
    path = _gfa_summary_path(config)
    if path is None:
        return None
    df = load_gfa_summary(config)
    if expid not in df.index:
        return None
    row = df.loc[expid]
    return row.iloc[0] if hasattr(row, "iloc") and row.ndim == 2 else row
