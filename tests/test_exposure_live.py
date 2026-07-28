"""Live tests against real NERSC filesystem + the replicator DB.

Skipped by default (see conftest.py); run with `pytest -m live` or
`pytest --run-live` from an environment with working psycopg2/fitsio
(e.g. after `source /global/common/software/desi/desi_environment.sh master`).
"""

import pytest

from telemetry_mining.exposure import Exposure
from telemetry_mining.telemetry import TelemetryField

pytestmark = pytest.mark.live

LIVE_EXPID = 255020
LIVE_NIGHT = 20240925
LIVE_TILEID = 22258

# A recent exposure within telemetry.environmentmonitor_dust's actual data
# coverage (that table only starts 2025-10-21 -- LIVE_EXPID above predates it
# entirely, so it can't be used for the nearest-value dust example).
DUST_EXAMPLE_EXPID = 359483
DUST_EXAMPLE_NIGHT = 20260702


def test_live_exposure_end_to_end():
    exp = Exposure(LIVE_EXPID, night=LIVE_NIGHT)

    assert exp.night == LIVE_NIGHT
    assert exp.header_value("SEQUENCE") == "DESI"
    assert exp.coords.shape[0] > 1000

    row = exp.db_row
    assert row["tileid"] == LIVE_TILEID

    start, end = exp.time_window
    assert end > start

    tel = exp.telemetry("environmentmonitor_telescope", pad_seconds=30)
    assert len(tel) > 0
    assert "time_recorded" in tel.columns

    assert exp.redux_row is not None
    assert int(exp.redux_row["TILEID"]) == LIVE_TILEID

    assert exp.n_guide_frames == 72  # from the FITS header's GFRAMES, verified against this real exposure
    centroids = exp.guider_centroids
    assert len(centroids) == exp.n_guide_frames
    for col in ["frame", "seeing", "nstars", "ngfas", "combined_x", "combined_y",
                "tcs_correction_ra", "tcs_correction_dec", "rotation"]:
        assert col in centroids.columns


def test_live_night_autoresolves_from_db():
    exp = Exposure(LIVE_EXPID)
    assert exp.night == LIVE_NIGHT


def test_live_telemetry_field_nearest_dust_example():
    """The exact use case that motivated query_nearest/TelemetryField: attach a
    pure time-series table (no expid column at all) to an exposure by nearest
    timestamp to its start, by convention."""
    field = TelemetryField(
        name="dust_5micron",
        table="environmentmonitor_dust",
        columns=["mayall_particle_1_micron_5"],
        max_delta_seconds=3600,
    )
    exp = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT, telemetry_fields=[field])

    result = exp.telemetry_field("dust_5micron")
    assert result is not None
    assert "mayall_particle_1_micron_5" in result
    assert abs(result["delta_seconds"]) < 60  # dust telemetry samples every few seconds

    # cached: a second call must not re-query
    assert exp.telemetry_field("dust_5micron") is result


def test_live_cframe_fibermap_scores_and_table():
    """Verifies the FIBERMAP/SCORES row-alignment finding against a real cframe file."""
    exp = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT)

    path = exp.cframe_path("z3")
    assert path.name == "cframe-z3-00359483.fits.gz"

    fm = exp.cframe_fibermap("z3")
    assert len(fm) == 500
    assert set(fm["PETAL_LOC"].unique()) == {3}
    assert (fm["LOCATION"] == fm["PETAL_LOC"] * 1000 + fm["DEVICE_LOC"]).all()

    sc = exp.cframe_scores("z3")
    assert len(sc) == 500
    assert "PETAL_LOC" not in sc.columns  # confirmed: SCORES carries no location columns of its own

    table = exp.cframe_table("z3")
    assert table.index.names == ["PETAL_LOC", "DEVICE_LOC"]
    assert len(table) == 500
    assert "MEDIAN_CALIB_SNR_Z" in table.columns


def test_live_cframe_table_single_open_faster_than_two_separate_opens():
    """Confirms the combined-open path is faster against real data, not just synthetic.

    Uses a different camera per method (rather than the same file back-to-back)
    so neither measurement gets an unfair OS page-cache warm-up from the other --
    an earlier same-file version of this comparison overstated the speedup
    (~8x) for exactly that reason. A fair average-of-several, different-file-
    per-method comparison instead measures ~30% faster for one combined open."""
    import time

    from telemetry_mining.fits_io import read_fibermap, read_fibermap_and_scores, read_scores

    exp = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT)
    # Cameras not already touched/cached by other tests in this module. 5 per side
    # (rather than 3) to average out real CFS I/O variance -- a modest ~30% true
    # effect is small enough that a 3-sample average occasionally flips on noise.
    two_open_cameras = ["b0", "r0", "z0", "b1", "r1"]
    one_open_cameras = ["z1", "b2", "r2", "z2", "b3"]

    t0 = time.time()
    for camera in two_open_cameras:
        path = exp.cframe_path(camera)
        read_fibermap(path)
        read_scores(path)
    two_opens_avg = (time.time() - t0) / len(two_open_cameras)

    t0 = time.time()
    for camera in one_open_cameras:
        path = exp.cframe_path(camera)
        read_fibermap_and_scores(path)
    one_open_avg = (time.time() - t0) / len(one_open_cameras)

    assert one_open_avg < two_opens_avg


def test_live_cframe_tables_matches_sequential_and_is_faster():
    """Confirms cframe_tables' process-pool result matches looping cframe_table,
    and is actually faster on real data (not just by construction)."""
    import time

    exp_seq = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT)
    exp_par = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT)

    # Cameras not already touched by other tests in this module.
    cameras = ["b8", "r8", "z8", "b9", "r9", "z9"]

    t0 = time.time()
    sequential = {c: exp_seq.cframe_table(c) for c in cameras}
    sequential_time = time.time() - t0

    t0 = time.time()
    parallel, errors = exp_par.cframe_tables(cameras)
    parallel_time = time.time() - t0

    assert errors == {}
    for camera in cameras:
        assert sequential[camera].equals(parallel[camera])

    assert parallel_time < sequential_time


def test_live_cframe_tables_reports_errors_for_pruned_exposure():
    exp = Exposure(LIVE_EXPID, night=LIVE_NIGHT)
    tables, errors = exp.cframe_tables(["z3", "z5"])
    assert tables == {}
    assert set(errors) == {"z3", "z5"}


def test_live_exposure_table_flags():
    """Real exposure_table rows found while investigating field definitions with the user."""
    exp = Exposure(330382, night=20260105)
    flags = exp.exposure_table_flags
    assert flags["LASTSTEP"] == "all"
    assert flags["CAMWORD"] == "a123456789"
    assert flags["BADCAMWORD"] is None
    assert flags["EXPFLAG"] == ["metadata_missing"]
    assert flags["HEADERERR"] == ["SEQTOT:->1"]
    assert "COMMENTS" not in flags

    exp2 = Exposure(330403, night=20260105)
    flags2 = exp2.exposure_table_flags
    assert flags2["LASTSTEP"] == "skysub"
    assert flags2["EXPFLAG"] == ["low_sn"]
    assert flags2["HEADERERR"] == []


def test_live_gfa_row():
    exp = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT)
    row = exp.gfa_row
    assert row is not None
    assert row["FWHM_ASEC"] == pytest.approx(1.530985, abs=1e-4)
    assert row["MOON_ILLUMINATION"] == pytest.approx(0.908568, abs=1e-4)


def test_live_fiberqa():
    exp = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT)
    fq = exp.fiberqa
    assert fq is not None
    assert fq["NGOODFIB"] == 4362
    assert fq["NGOODPET"] == 10
    assert fq["WORSTRDN"] == pytest.approx(4.5657738006904065)


def test_live_fiberqa_none_for_pruned_old_exposure():
    """exposure-qa files follow the same rolling retention as cframes."""
    exp = Exposure(LIVE_EXPID, night=LIVE_NIGHT)
    assert exp.fiberqa is None


def test_live_petalqa():
    exp = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT)
    pq = exp.petalqa
    assert pq is not None
    assert list(pq.index) == list(range(10))
    assert pq.loc[0, "NGOODPOS"] == 471
    assert pq.loc[0, "NGOODFIB"] == 464
    assert pq.loc[0, "NSTDSTAR"] == 10


def test_live_petalqa_none_for_pruned_old_exposure():
    exp = Exposure(LIVE_EXPID, night=LIVE_NIGHT)
    assert exp.petalqa is None


def test_live_fiberqa_table():
    exp = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT)
    ft = exp.fiberqa_table
    assert ft is not None
    assert len(ft) == 5000
    row = ft.loc[(0, 311)]
    assert row["QAFIBERSTATUS"] == 0
    assert row["EFFTIME_SPEC"] == pytest.approx(187.63637, abs=1e-3)


def test_live_fiberqa_table_none_for_pruned_old_exposure():
    exp = Exposure(LIVE_EXPID, night=LIVE_NIGHT)
    assert exp.fiberqa_table is None


def test_live_calibstars():
    exp = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT)
    cs = exp.calibstars
    assert cs is not None
    assert len(cs) == 142
    assert list(cs.columns) == ["RCALIBFRAC", "EBV", "MODEL_COLOR", "DATA_COLOR", "X", "Y", "VALID"]
    assert cs.loc[12, "RCALIBFRAC"] == pytest.approx(0.889768)


def test_live_calibstars_join_to_petal_device_loc():
    """FIBER // 500 == PETAL_LOC always holds; DEVICE_LOC has no formula and needs a real join."""
    exp = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT)
    cs = exp.calibstars
    fiber_loc = exp.fiberqa_table.reset_index().set_index("FIBER")[["PETAL_LOC", "DEVICE_LOC"]]
    joined = cs.join(fiber_loc)
    assert joined["PETAL_LOC"].isna().sum() == 0
    assert (joined["PETAL_LOC"] == joined.index // 500).all()


def test_live_calibstars_older_specprod_via_redux_release_override():
    """calibstars works for other specprods too (e.g. 'matterhorn'), not just 'daily'."""
    import dataclasses

    from telemetry_mining import Config

    cfg = dataclasses.replace(Config.default(), redux_release="matterhorn")
    exp = Exposure(88359, night=20210514, config=cfg)
    cs = exp.calibstars
    assert cs is not None
    assert len(cs) == 84


def test_live_calibstars_none_for_pruned_old_exposure():
    exp = Exposure(LIVE_EXPID, night=LIVE_NIGHT)
    assert exp.calibstars is None


def test_live_fiberassign_table():
    exp = Exposure(DUST_EXAMPLE_EXPID, night=DUST_EXAMPLE_NIGHT)
    ft = exp.fiberassign_table
    assert ft is not None
    assert len(ft) == 5000
    row = ft.loc[(0, 311)]
    assert row["FIBER"] == 0
    assert row["DESI_TARGET"] == 1152921504606846976


def test_live_fiberassign_table_available_for_old_exposure_unlike_redux_sources():
    """fiberassign lives in the raw exposure directory, not the redux tree -- full history
    at NERSC, unlike cframe/calibstars/fiberqa_table/petalqa which are pruned after ~6 months."""
    exp = Exposure(LIVE_EXPID, night=LIVE_NIGHT)
    assert exp.calibstars is None
    assert exp.fiberassign_table is not None
    assert len(exp.fiberassign_table) == 5000
