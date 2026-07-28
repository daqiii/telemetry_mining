"""Night resolution and exposure file path building.

Mirrors the path-building logic in DOSlib.util.find_exposure, but split into
a DB lookup (resolve_night) and pure path construction (ExposurePaths) so
that file-based accessors can work with zero DB access when the caller
already knows the night.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import db
from .config import Config
from .exceptions import ExposureNotFoundError


def resolve_night(expid: int, config: Config) -> int:
    """Look up the observing night for an exposure ID via the exposure DB."""
    row = db.fetch_one(
        config,
        "SELECT night FROM exposure.exposure WHERE id = %s LIMIT 1",
        (expid,),
    )
    if row is None or row.get("night") is None:
        raise ExposureNotFoundError(expid, "no matching row in exposure.exposure")
    return int(row["night"])


def exposure_directory(expid: int, night: int, config: Config) -> Path:
    """Build the exposure directory path for a given night/expid, without touching disk."""
    return config.exposures_root / str(night) / f"{expid:08d}"


@dataclass(frozen=True)
class ExposureRef:
    """A lightweight (expid, night, sequence, directory) reference from a bulk lookup."""

    expid: int
    night: int
    sequence: str | None
    directory: Path


def find_exposures(
    config: Config,
    *,
    sequence: str | None = None,
    night: int | None = None,
    night_range: tuple[int, int] | None = None,
    limit: int = 2000,
) -> list[ExposureRef]:
    """Bulk exposure lookup by sequence and/or night (or night range).

    At least one of sequence/night/night_range must be given. Mirrors
    DOSlib.util.find_exposures, but uses parameterized queries (DOSlib's
    version builds the WHERE clause with raw %-string formatting) and
    honors config.exposures_root for the returned directory (DOSlib's
    version always builds the mountain-side '/exposures/desi' path here,
    even when running at NERSC).
    """
    if sequence is None and night is None and night_range is None:
        raise ValueError("must specify at least one of sequence, night, or night_range")

    clauses = []
    params: list = []
    if sequence is not None:
        clauses.append("sequence = %s")
        params.append(sequence)
    if night is not None:
        clauses.append("night = %s")
        params.append(night)
    elif night_range is not None:
        first, last = night_range
        clauses.append("night >= %s AND night <= %s")
        params.extend([first, last])

    where = " AND ".join(clauses)
    query = f"SELECT id, night, sequence FROM exposure.exposure WHERE {where} ORDER BY id ASC LIMIT %s"
    params.append(limit)

    rows = db.fetch_all(config, query, tuple(params))
    return [
        ExposureRef(
            expid=row["id"],
            night=row["night"],
            sequence=row["sequence"],
            directory=exposure_directory(row["id"], row["night"], config),
        )
        for row in rows
    ]


def find_last_exposure(config: Config, sequence: str, require_coords: bool = False) -> ExposureRef | None:
    """Most recent exposure for a sequence type, or None if none found.

    If require_coords is True, skips candidates that don't have a
    coordinates-<expid>.fits file on disk yet (mirrors DOSlib's
    require_coords check, but as a file-existence check rather than an
    eager parse of each candidate).
    """
    rows = db.fetch_all(
        config,
        "SELECT id, night, sequence FROM exposure.exposure WHERE sequence = %s ORDER BY id DESC LIMIT 20",
        (sequence,),
    )
    for row in rows:
        ref = ExposureRef(
            expid=row["id"],
            night=row["night"],
            sequence=row["sequence"],
            directory=exposure_directory(row["id"], row["night"], config),
        )
        if require_coords:
            coords_path = ExposurePaths(ref.directory, ref.expid).coordinates
            if not coords_path.exists():
                continue
        return ref
    return None


@dataclass(frozen=True)
class ExposurePaths:
    """Named accessors for every known file in an exposure directory."""

    directory: Path
    expid: int

    def _named(self, prefix: str, suffix: str) -> Path:
        return self.directory / f"{prefix}-{self.expid:08d}{suffix}"

    @property
    def main_fits(self) -> Path:
        return self._named("desi", ".fits.fz")

    @property
    def coordinates(self) -> Path:
        return self._named("coordinates", ".fits")

    @property
    def etc_json(self) -> Path:
        return self._named("etc", ".json")

    @property
    def etc_png(self) -> Path:
        return self._named("etc", ".png")

    @property
    def centroids_json(self) -> Path:
        return self._named("centroids", ".json")

    @property
    def guide_cube(self) -> Path:
        return self._named("guide", ".fits.fz")

    @property
    def guide_frame0(self) -> Path:
        return self.directory / f"guide-{self.expid:08d}-0000.fits.fz"

    @property
    def guide_rois(self) -> Path:
        return self._named("guide-rois", ".fits.fz")

    @property
    def focus(self) -> Path:
        return self._named("focus", ".fits.fz")

    @property
    def fvc(self) -> Path:
        return self._named("fvc", ".fits.fz")

    @property
    def platemaker(self) -> Path:
        return self._named("pm", ".fits")

    @property
    def platemaker_logs(self) -> Path:
        return self._named("pm", "-logs.tar")

    @property
    def sky(self) -> Path:
        return self._named("sky", ".fits.fz")

    @property
    def request_json(self) -> Path:
        return self._named("request", ".json")

    @property
    def checksum(self) -> Path:
        return self._named("checksum", ".sha256sum")

    def fiberassign(self, tileid: int) -> Path:
        """Fiberassign files are keyed by tileid, not expid."""
        return self.directory / f"fiberassign-{tileid:06d}.fits.gz"

    def cframe(self, redux_root: Path, night: int, camera: str, redux_release: str = "daily") -> Path:
        """Path to the offline-processed cframe file for one camera (e.g. 'z3')."""
        return (
            redux_root
            / redux_release
            / "exposures"
            / str(night)
            / f"{self.expid:08d}"
            / f"cframe-{camera}-{self.expid:08d}.fits.gz"
        )

    def exposure_qa(self, redux_root: Path, night: int, redux_release: str = "daily") -> Path:
        """Path to the offline exposure-qa-<expid>.fits file (same directory as cframe)."""
        return (
            redux_root
            / redux_release
            / "exposures"
            / str(night)
            / f"{self.expid:08d}"
            / f"exposure-qa-{self.expid:08d}.fits"
        )

    def calibstars(self, redux_root: Path, night: int, redux_release: str = "daily") -> Path:
        """Path to the offline calibstars-<expid>.csv file (same directory as cframe)."""
        return (
            redux_root
            / redux_release
            / "exposures"
            / str(night)
            / f"{self.expid:08d}"
            / f"calibstars-{self.expid:08d}.csv"
        )
