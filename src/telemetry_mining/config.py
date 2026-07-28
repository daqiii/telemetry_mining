"""Site-aware configuration for locating DESI data and connecting to the DB.

Path/DB defaults are derived from the DOS_DB_* environment variables, which
are already populated correctly in the standard DESI environment. The
NERSC-vs-mountain path branch mirrors the logic in DOSlib.util.find_exposure
(``"lbl.gov" in DOS_DB_HOST``), centralized here instead of repeated at every
call site.

Confirmed against the real KPNO (mountain) deployment (2026-07-15):
- Same DOS_DB_* env vars, just pointing at a different host -- the DB has the
  full exposure/telemetry schemas there (no reduced-history special-casing
  needed for the DB side).
- /exposures/desi/<night>/<expid> (the path DOSlib already used) is correct.
- KPNO keeps only a rolling ~6 months of exposure *files* on disk (older ones
  are purged once confirmed at NERSC) -- exposure directories/files can
  legitimately not exist even though the DB record is complete.
- KPNO has no offline/redux reduction pipeline at all -- there is no
  equivalent of NERSC's exposures-daily.csv, not just a different path for
  it. redux_root is therefore Optional: None means "this site has no such
  source", not "guess and hope the path exists".

gfa_root (added 2026-07-16) follows the same None-means-no-source pattern
for the offline GFA (guider) summary pipeline, but unlike redux_root this
is an assumption by analogy (a survey-ops analysis product, presumably
NERSC-only like redux), not something confirmed with anyone at KPNO.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

NERSC_EXPOSURES_ROOT = Path("/global/cfs/cdirs/desi/spectro/data")
NERSC_REDUX_ROOT = Path("/global/cfs/cdirs/desi/spectro/redux")
NERSC_GFA_ROOT = Path("/global/cfs/cdirs/desi/survey/GFA")
MOUNTAIN_EXPOSURES_ROOT = Path("/exposures/desi")


def _detect_site(db_host: str) -> str:
    if "lbl.gov" in db_host:
        return "nersc"
    if db_host:
        return "kpno"
    return "unknown"


@dataclass(frozen=True)
class Config:
    """Bundle of paths and DB connection info. Every field is overridable."""

    site: str
    exposures_root: Path
    redux_root: Optional[Path]
    gfa_root: Optional[Path] = None
    redux_release: str = "daily"
    db_name: str = ""
    db_host: str = ""
    db_port: int = 5432
    db_user: str = ""
    db_password: str = field(default="", repr=False)

    @classmethod
    def default(cls) -> "Config":
        """Build a Config from the DOS_DB_* environment variables.

        Raises KeyError-free defaults for path roots (derived from db_host),
        but leaves DB credential fields blank if unset -- callers that need
        the DB will get a clear DatabaseUnavailableError at connection time
        rather than a confusing failure here.
        """
        db_host = os.environ.get("DOS_DB_HOST", "")
        site = _detect_site(db_host)
        if site == "nersc":
            exposures_root = NERSC_EXPOSURES_ROOT
            redux_root = NERSC_REDUX_ROOT
            gfa_root = NERSC_GFA_ROOT
        else:
            exposures_root = MOUNTAIN_EXPOSURES_ROOT
            redux_root = None  # no offline/redux pipeline at KPNO (or an unrecognized site)
            gfa_root = None  # the GFA offline-summary pipeline is a NERSC/survey-ops product, not run at KPNO
        return cls(
            site=site,
            exposures_root=exposures_root,
            redux_root=redux_root,
            gfa_root=gfa_root,
            db_name=os.environ.get("DOS_DB_NAME", ""),
            db_host=db_host,
            db_port=int(os.environ.get("DOS_DB_PORT", "5432") or 5432),
            db_user=os.environ.get("DOS_DB_READER", ""),
            db_password=os.environ.get("DOS_DB_READER_PASSWORD", ""),
        )

    @property
    def redux_daily_dir(self) -> Optional[Path]:
        if self.redux_root is None:
            return None
        return self.redux_root / self.redux_release

    @property
    def exposures_daily_csv(self) -> Optional[Path]:
        daily_dir = self.redux_daily_dir
        if daily_dir is None:
            return None
        return daily_dir / "exposures-daily.csv"
