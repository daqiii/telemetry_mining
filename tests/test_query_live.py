"""Live tests for select_exposures/harvest against the real DB + NERSC filesystem.

Skipped by default (see conftest.py); run with `pytest -m live` or
`pytest --run-live`.
"""

import pytest

from telemetry_mining.exposure import Exposure
from telemetry_mining.query import harvest, select_exposures

pytestmark = pytest.mark.live

DUST_EXAMPLE_EXPID = 359483
DUST_EXAMPLE_NIGHT = 20260702


def test_live_select_exposures_pulls_multiple_sources():
    table = select_exposures(
        "id = %s",
        columns={
            "exptime": "db_row.exptime",
            "etc_fracb": "header.ETCFRACB",
            "seeing_gfa": "gfa_row.FWHM_ASEC",
        },
        params=(DUST_EXAMPLE_EXPID,),
    )
    assert len(table) == 1
    row = table.iloc[0]
    assert row["EXPID"] == DUST_EXAMPLE_EXPID
    assert row["NIGHT"] == DUST_EXAMPLE_NIGHT
    assert row["etc_fracb"] == pytest.approx(0.134257)
    assert row["seeing_gfa"] == pytest.approx(1.530985, abs=1e-4)


def test_live_harvest_dict_mode_matches_direct_access():
    direct = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT).petalqa
    results = harvest([DUST_EXAMPLE_EXPID], lambda exp: exp.petalqa)
    assert results[DUST_EXAMPLE_EXPID].equals(direct)


def test_live_harvest_concat_pools_across_exposures():
    pooled = harvest([DUST_EXAMPLE_EXPID], lambda exp: exp.petalqa, concat=True)
    assert set(pooled["EXPID"]) == {DUST_EXAMPLE_EXPID}
    assert "PETAL_LOC" in pooled.columns
    assert len(pooled) == 10


def test_live_select_exposures_max_workers_matches_sequential_and_is_faster():
    """Confirms select_exposures' thread pool (max_workers) result matches
    sequential, and is actually faster on real data (not just by construction).

    Uses a callable spec that queries telemetry.guider_centroids and fits a
    line per exposure -- exactly the DB-round-trip-bound workload max_workers
    is meant for (a plain "db_row.*" spec would show no difference, since
    that's already one bulk query regardless of max_workers).
    """
    import time

    import numpy as np

    def rotation_rate_slope(exp):
        frames = exp.guider_centroids
        if len(frames) < 40:
            return None
        t_min = (frames["obstime"] - frames["obstime"].iloc[0]).dt.total_seconds() / 60.0
        slope, _intercept = np.polyfit(t_min, frames["rotation"], 1)
        return slope

    where = "night = %s and sequence = %s and totteff > %s and program like %s"
    params = (20250201, "DESI", 60.0, "DARK")
    columns = {"X": "db_row.tcs['mount_ha']", "C": rotation_rate_slope}

    t0 = time.time()
    sequential = select_exposures(where, columns=columns, params=params)
    sequential_time = time.time() - t0

    t0 = time.time()
    parallel = select_exposures(where, columns=columns, params=params, max_workers=8)
    parallel_time = time.time() - t0

    assert len(sequential) > 0
    assert list(parallel["EXPID"]) == list(sequential["EXPID"])
    assert list(parallel["C"]) == list(sequential["C"])
    assert parallel_time < sequential_time
