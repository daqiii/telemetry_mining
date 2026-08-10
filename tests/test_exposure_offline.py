import json

import numpy as np
import pytest

fitsio = pytest.importorskip("fitsio")

from telemetry_mining import db, gfa, telemetry
from telemetry_mining.config import Config
from telemetry_mining.exceptions import DatabaseUnavailableError, DataSourceUnavailableError, ExposureNotFoundError
from telemetry_mining.exposure import Exposure
from telemetry_mining.tables import TableSource
from telemetry_mining.telemetry import TelemetryField


def build_exposure_dir(tmp_path, night=20240925, expid=255020, extra_header=None):
    cfg = Config(site="test", exposures_root=tmp_path / "exposures", redux_root=tmp_path / "redux")
    directory = cfg.exposures_root / str(night) / f"{expid:08d}"
    directory.mkdir(parents=True)

    main_fits = directory / f"desi-{expid:08d}.fits.fz"
    with fitsio.FITS(str(main_fits), "rw", clobber=True) as f:
        f.write(None)
        data = np.array([(1.0,)], dtype=[("X", "f8")])
        header = {
            "DATE-OBS": "2024-09-26T12:21:46.076987",
            "EXPTIME": 579.8482,
            "AIRMASS": 1.794142,
            "SEQUENCE": "DESI",
        }
        header.update(extra_header or {})
        f.write(data, extname="SPEC", header=header)

    coords_fits = directory / f"coordinates-{expid:08d}.fits"
    coords_data = np.array(
        [(1, 10, 100.0, 200.0)],
        dtype=[("PETAL_LOC", "i4"), ("DEVICE_LOC", "i4"), ("POS_X", "f8"), ("POS_Y", "f8")],
    )
    stat_data = np.array([(1, 999, 1)], dtype=[("PETAL_LOC", "i4"), ("DEVICE_LOC", "i4"), ("FIDUCIAL", "i4")])
    with fitsio.FITS(str(coords_fits), "rw", clobber=True) as f:
        f.write(coords_data, extname="DATA")
        f.write(stat_data, extname="STATIONARY")

    etc_json = directory / f"etc-{expid:08d}.json"
    etc_json.write_text(
        json.dumps(
            {
                "header": {"ETCTEFF": 16.4, "ETCREAL": 582.7},
                "accum": {"mjd0": 60579.5, "efftime": [1.0, 2.0, 3.0]},
            }
        )
    )

    centroids_json = directory / f"centroids-{expid:08d}.json"
    centroids_json.write_text(json.dumps({"frame0": {"x": 1.0}}))

    redux_dir = cfg.redux_root / "daily"
    redux_dir.mkdir(parents=True)
    cfg.exposures_daily_csv.write_text(f"NIGHT,EXPID,TILEID,EXPTIME\n{night},{expid},22258,579.8\n")

    return cfg, directory


def test_exposure_file_accessors_need_no_db(tmp_path):
    cfg, directory = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)

    assert exp.night == 20240925
    assert exp.directory == directory
    assert exp.header_value("AIRMASS") == pytest.approx(1.794142)
    assert exp.coords.shape == (1, 2)
    assert exp.etc_summary["ETCTEFF"] == pytest.approx(16.4)
    df = exp.etc_timeseries("accum")
    assert list(df["efftime"]) == [1.0, 2.0, 3.0]
    assert df.attrs["mjd0"] == pytest.approx(60579.5)
    assert exp.centroids == {"frame0": {"x": 1.0}}
    assert exp.redux_row is not None
    assert int(exp.redux_row["TILEID"]) == 22258


def test_exposure_repr_and_summary_never_touch_guider(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)
    # no guide-*.fits.fz files were created; repr/summary must not try to read them
    repr(exp)
    summary = exp.summary()
    assert summary["expid"] == 255020
    assert summary["in_redux_daily"] is True


def test_exposure_db_methods_raise_without_db_config(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)
    with pytest.raises(DatabaseUnavailableError):
        _ = exp.db_row


def test_time_window_falls_back_to_header_without_db(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)
    start, end = exp.time_window
    assert (start.year, start.month, start.day) == (2024, 9, 26)
    assert (end - start).total_seconds() == pytest.approx(579.8482)


def test_missing_expid_dir_raises(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(999999, night=20240925, config=cfg)
    with pytest.raises(Exception):
        _ = exp.directory


def test_n_guide_frames_prefers_header_and_skips_db(monkeypatch, tmp_path):
    cfg, _ = build_exposure_dir(tmp_path, extra_header={"GFRAMES": 72})
    exp = Exposure(255020, night=20240925, config=cfg)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("should not query the DB when GFRAMES is in the header")

    monkeypatch.setattr(db, "fetch_df", fail_if_called)
    assert exp.n_guide_frames == 72


def test_n_guide_frames_falls_back_to_guider_centroids(monkeypatch, tmp_path):
    import pandas as pd

    cfg, _ = build_exposure_dir(tmp_path)  # no GFRAMES in header
    exp = Exposure(255020, night=20240925, config=cfg)

    fake_rows = pd.DataFrame({"frame": [1, 2, 3]})
    monkeypatch.setattr(db, "fetch_df", lambda config, query, params=None: fake_rows)
    assert exp.n_guide_frames == 3


def test_n_guide_frames_falls_back_when_fits_file_is_missing(monkeypatch, tmp_path):
    """Simulates KPNO: the exposure's FITS files were purged, but the DB record survives."""
    import pandas as pd

    cfg, directory = build_exposure_dir(tmp_path)
    (directory / "desi-00255020.fits.fz").unlink()
    exp = Exposure(255020, night=20240925, config=cfg)

    fake_rows = pd.DataFrame({"frame": [1, 2]})
    monkeypatch.setattr(db, "fetch_df", lambda config, query, params=None: fake_rows)
    assert exp.n_guide_frames == 2


def test_time_window_raises_clean_error_when_db_and_header_both_unavailable(tmp_path):
    """Simulates KPNO: purged FITS file, and (for this test) no DB connection either."""
    cfg, directory = build_exposure_dir(tmp_path)
    (directory / "desi-00255020.fits.fz").unlink()
    exp = Exposure(255020, night=20240925, config=cfg)  # cfg has no db_host -> db_row raises

    with pytest.raises(ExposureNotFoundError):
        _ = exp.time_window


def test_alarms_queries_alarms_schema_over_the_time_window(monkeypatch, tmp_path):
    import pandas as pd

    cfg, _ = build_exposure_dir(tmp_path)  # time_window resolves from the FITS header
    exp = Exposure(255020, night=20240925, config=cfg)

    captured = {}

    def fake_query_window(config, table, start, end, *, pad_seconds=0.0, columns=None,
                          time_column="time_recorded", schema="telemetry", limit=None):
        captured.update(table=table, schema=schema, columns=columns,
                        pad_seconds=pad_seconds, window=(start, end))
        return pd.DataFrame([
            {"id": 1, "time_recorded": start, "level": "WARNING", "component": "gfa",
             "instance": "gfa0", "message": "w"},
            {"id": 2, "time_recorded": end, "level": "CRITICAL", "component": "tcs",
             "instance": "tcs", "message": "c"},
        ])

    monkeypatch.setattr(telemetry, "query_window", fake_query_window)

    df = exp.alarms(pad_seconds=5)
    # queries the alarms schema/table over the exposure's window, with the default columns
    assert captured["schema"] == "alarms" and captured["table"] == "alarms"
    assert captured["pad_seconds"] == 5
    assert captured["window"] == exp.time_window
    assert list(captured["columns"]) == ["id", "time_recorded", "level", "component", "instance", "message"]
    assert len(df) == 2

    # `level` post-filters by severity
    assert list(exp.alarms(level="CRITICAL")["level"]) == ["CRITICAL"]
    assert len(exp.alarms(level=["CRITICAL", "ALERT"])) == 1

    # `columns` overrides the default set (e.g. to add alarm_id)
    exp.alarms(columns=["id", "alarm_id"])
    assert captured["columns"] == ["id", "alarm_id"]


def test_at_time_returns_the_exposure_open_at_when(monkeypatch, tmp_path):
    import datetime as dt

    cfg, _ = build_exposure_dir(tmp_path)
    row = {"id": 255020, "night": 20240925,
           "date_obs": dt.datetime(2024, 9, 26, 12, 0, 0, tzinfo=dt.timezone.utc),
           "exptime": 600.0, "tcs": {"mount_ha": 1.2}}
    captured = {}

    def fake_fetch_one(config, query, params=None):
        captured["query"], captured["params"] = query, params
        return row

    monkeypatch.setattr(db, "fetch_one", fake_fetch_one)
    when = dt.datetime(2024, 9, 26, 12, 5, 0, tzinfo=dt.timezone.utc)
    exp = Exposure.at_time(when, config=cfg)

    assert exp is not None and exp.expid == 255020
    assert "date_obs <= %s" in captured["query"] and "ORDER BY date_obs DESC LIMIT 1" in captured["query"]
    assert captured["params"] == (when,)
    assert exp.db_row is row  # primed by at_time -> no extra query on access

    # None when there is no exposure at or before `when`
    monkeypatch.setattr(db, "fetch_one", lambda config, query, params=None: None)
    assert Exposure.at_time(dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc), config=cfg) is None


def test_guider_centroids_queries_by_expid(monkeypatch, tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)
    captured = {}

    def fake_fetch_df(config, query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "sentinel-dataframe"

    monkeypatch.setattr(db, "fetch_df", fake_fetch_df)
    result = exp.guider_centroids

    assert result == "sentinel-dataframe"
    assert captured["params"] == (255020,)
    assert "telemetry.guider_centroids" in captured["query"]
    assert "WHERE expid = %s" in captured["query"]
    for col in ["seeing", "nstars", "ngfas", "combined_x", "combined_y",
                "tcs_correction_ra", "tcs_correction_dec", "frame"]:
        assert col in captured["query"]


def test_telemetry_field_dispatches_nearest(monkeypatch, tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    field = TelemetryField(name="dust", table="environmentmonitor_dust", columns=["mayall_particle_1_micron_5"])
    exp = Exposure(255020, night=20240925, config=cfg, telemetry_fields=[field])
    captured = {}

    def fake_query_nearest(config, table, when, **kwargs):
        captured["table"] = table
        captured["when"] = when
        captured["kwargs"] = kwargs
        return {"mayall_particle_1_micron_5": 3, "delta_seconds": 1.5}

    monkeypatch.setattr(telemetry, "query_nearest", fake_query_nearest)
    result = exp.telemetry_field("dust")

    assert result == {"mayall_particle_1_micron_5": 3, "delta_seconds": 1.5}
    assert captured["table"] == "environmentmonitor_dust"
    assert captured["when"] == exp.time_window[0]  # 'start' by default
    assert captured["kwargs"]["columns"] == ["mayall_particle_1_micron_5"]


def test_telemetry_field_nearest_returns_none_when_time_unavailable(monkeypatch, tmp_path):
    """A nearest lookup must not crash when the exposure's time can't be found.

    Simulates KPNO: purged FITS file and no DB connection, so neither the DB
    row nor the header can supply a start time. A nearest-in-time field should
    resolve to None (treated as "no match") rather than raising and aborting a
    whole sweep -- and it must not attempt the telemetry query at all.
    """
    cfg, directory = build_exposure_dir(tmp_path)
    (directory / "desi-00255020.fits.fz").unlink()  # purged; cfg has no db_host
    field = TelemetryField(name="dust", table="environmentmonitor_dust", columns=["mayall_particle_1_micron_5"])
    exp = Exposure(255020, night=20240925, config=cfg, telemetry_fields=[field])

    def fail_if_called(*args, **kwargs):
        raise AssertionError("query_nearest must not run when the time is unavailable")

    monkeypatch.setattr(telemetry, "query_nearest", fail_if_called)

    assert exp.start_time is None
    assert exp.telemetry_field("dust") is None


def test_telemetry_field_dispatches_window(monkeypatch, tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    field = TelemetryField(name="wind", table="environmentmonitor_tower", kind="window", pad_seconds=30.0)
    exp = Exposure(255020, night=20240925, config=cfg, telemetry_fields=[field])
    captured = {}

    def fake_query_window(config, table, start, end, **kwargs):
        captured["table"] = table
        captured["pad_seconds"] = kwargs.get("pad_seconds")
        return "a-dataframe"

    monkeypatch.setattr(telemetry, "query_window", fake_query_window)
    result = exp.telemetry_field("wind")

    assert result == "a-dataframe"
    assert captured["table"] == "environmentmonitor_tower"
    assert captured["pad_seconds"] == 30.0


def test_telemetry_field_caches_by_name(monkeypatch, tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    field = TelemetryField(name="dust", table="environmentmonitor_dust")
    exp = Exposure(255020, night=20240925, config=cfg, telemetry_fields=[field])
    calls = []
    monkeypatch.setattr(telemetry, "query_nearest", lambda *a, **k: calls.append(1) or {"x": 1})

    exp.telemetry_field("dust")
    exp.telemetry_field("dust")
    assert len(calls) == 1


def test_telemetry_field_unknown_name_raises(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg, telemetry_fields=[])
    with pytest.raises(KeyError):
        exp.telemetry_field("nope")


def test_duplicate_telemetry_field_names_raise_at_construction(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    fields = [TelemetryField(name="dust", table="a"), TelemetryField(name="dust", table="b")]
    with pytest.raises(ValueError):
        Exposure(255020, night=20240925, config=cfg, telemetry_fields=fields)


def test_default_telemetry_fields_are_snapshotted_at_construction(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    telemetry.DEFAULT_TELEMETRY_FIELDS.append(TelemetryField(name="global_dust", table="environmentmonitor_dust"))

    exp_before = Exposure(255020, night=20240925, config=cfg)
    assert "global_dust" in exp_before.telemetry_field_names

    telemetry.DEFAULT_TELEMETRY_FIELDS.append(TelemetryField(name="added_later", table="environmentmonitor_dust"))
    assert "added_later" not in exp_before.telemetry_field_names  # snapshot, not a live reference

    exp_after = Exposure(255020, night=20240925, config=cfg)
    assert "added_later" in exp_after.telemetry_field_names


def test_all_telemetry_fields_runs_every_configured_field(monkeypatch, tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    fields = [
        TelemetryField(name="a", table="environmentmonitor_dust"),
        TelemetryField(name="b", table="environmentmonitor_tower", kind="window"),
    ]
    exp = Exposure(255020, night=20240925, config=cfg, telemetry_fields=fields)
    monkeypatch.setattr(telemetry, "query_nearest", lambda *a, **k: {"nearest": True})
    monkeypatch.setattr(telemetry, "query_window", lambda *a, **k: "windowed")

    result = exp.all_telemetry_fields()
    assert result == {"a": {"nearest": True}, "b": "windowed"}


def build_cframe_file(cfg, night, expid, camera="z3"):
    cframe_dir = cfg.redux_root / "daily" / "exposures" / str(night) / f"{expid:08d}"
    cframe_dir.mkdir(parents=True, exist_ok=True)  # multiple cameras share one exposure dir
    path = cframe_dir / f"cframe-{camera}-{expid:08d}.fits.gz"
    fibermap = np.array(
        [(1, 10, 1010, 3010), (1, 20, 1020, 3020)],
        dtype=[("PETAL_LOC", "i2"), ("DEVICE_LOC", "i4"), ("LOCATION", "i4"), ("FIBER", "i8")],
    )
    scores = np.array([(100.0, 5.0), (200.0, 8.0)], dtype=[("MEDIAN_CALIB_COUNT_Z", "f8"), ("MEDIAN_CALIB_SNR_Z", "f8")])
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(None)
        f.write(fibermap, extname="FIBERMAP")
        f.write(scores, extname="SCORES")
    return path


def test_cframe_path_raises_without_redux(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    kpno_cfg = Config(site="kpno", exposures_root=cfg.exposures_root, redux_root=None)
    exp = Exposure(255020, night=20240925, config=kpno_cfg)
    with pytest.raises(DataSourceUnavailableError):
        exp.cframe_path("z3")


def test_cframe_fibermap_and_scores(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    build_cframe_file(cfg, 20240925, 255020, camera="z3")
    exp = Exposure(255020, night=20240925, config=cfg)

    fm = exp.cframe_fibermap("z3")
    assert list(fm["FIBER"]) == [3010, 3020]

    sc = exp.cframe_scores("z3")
    assert list(sc["MEDIAN_CALIB_COUNT_Z"]) == [100.0, 200.0]


def test_cframe_table_combines_and_indexes(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    build_cframe_file(cfg, 20240925, 255020, camera="z3")
    exp = Exposure(255020, night=20240925, config=cfg)

    table = exp.cframe_table("z3")
    assert table.index.names == ["PETAL_LOC", "DEVICE_LOC"]
    assert table.loc[(1, 20), "MEDIAN_CALIB_SNR_Z"] == 8.0


def test_cframe_table_cached_per_camera(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    build_cframe_file(cfg, 20240925, 255020, camera="z3")
    exp = Exposure(255020, night=20240925, config=cfg)

    first = exp.cframe_table("z3")
    second = exp.cframe_table("z3")
    assert first is second


def test_cframe_table_populates_fibermap_and_scores_caches(tmp_path, monkeypatch):
    """cframe_table's combined read must still populate the individual caches, so a
    later standalone cframe_fibermap()/cframe_scores() call is free."""
    cfg, _ = build_exposure_dir(tmp_path)
    build_cframe_file(cfg, 20240925, 255020, camera="z3")
    exp = Exposure(255020, night=20240925, config=cfg)

    exp.cframe_table("z3")
    assert "z3" in exp._cframe_fibermap_cache
    assert "z3" in exp._cframe_scores_cache

    # now standalone calls should hit the cache -- no fresh file read needed. exposure.py
    # imports the name directly (`from .fits_io import read_fibermap_and_scores`), so patch
    # it in the exposure module's namespace, not fits_io's.
    import telemetry_mining.exposure as exposure_mod

    def fail_if_called(*a, **k):
        raise AssertionError("should not re-read -- fibermap/scores were already cached by cframe_table")

    monkeypatch.setattr(exposure_mod, "read_fibermap_and_scores", fail_if_called)
    assert list(exp.cframe_fibermap("z3")["FIBER"]) == [3010, 3020]
    assert list(exp.cframe_scores("z3")["MEDIAN_CALIB_COUNT_Z"]) == [100.0, 200.0]


def test_cframe_table_reuses_individually_cached_fibermap_and_scores(tmp_path, monkeypatch):
    """If cframe_fibermap()/cframe_scores() were already called individually first,
    cframe_table() must not pay for a fresh combined read."""
    cfg, _ = build_exposure_dir(tmp_path)
    build_cframe_file(cfg, 20240925, 255020, camera="z3")
    exp = Exposure(255020, night=20240925, config=cfg)

    exp.cframe_fibermap("z3")
    exp.cframe_scores("z3")

    import telemetry_mining.exposure as exposure_mod

    def fail_if_called(*a, **k):
        raise AssertionError("should not re-read -- both were already individually cached")

    monkeypatch.setattr(exposure_mod, "read_fibermap_and_scores", fail_if_called)
    table = exp.cframe_table("z3")
    assert table.loc[(1, 20), "MEDIAN_CALIB_SNR_Z"] == 8.0


def test_cframe_tables_matches_sequential_and_populates_caches(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    build_cframe_file(cfg, 20240925, 255020, camera="z3")
    build_cframe_file(cfg, 20240925, 255020, camera="z5")
    exp = Exposure(255020, night=20240925, config=cfg)

    tables, errors = exp.cframe_tables(["z3", "z5"])
    assert errors == {}
    assert set(tables) == {"z3", "z5"}
    assert tables["z3"].loc[(1, 20), "MEDIAN_CALIB_SNR_Z"] == 8.0
    assert tables["z5"].loc[(1, 20), "MEDIAN_CALIB_SNR_Z"] == 8.0

    # Populates the same per-camera caches cframe_table itself uses.
    assert "z3" in exp._cframe_table_cache and "z5" in exp._cframe_table_cache
    assert "z3" in exp._cframe_fibermap_cache and "z3" in exp._cframe_scores_cache

    # A plain cframe_table call for an already-fetched camera is then just a cache hit.
    assert exp.cframe_table("z3") is tables["z3"]


def test_cframe_tables_skips_already_cached_cameras(tmp_path, monkeypatch):
    cfg, _ = build_exposure_dir(tmp_path)
    build_cframe_file(cfg, 20240925, 255020, camera="z3")
    exp = Exposure(255020, night=20240925, config=cfg)

    exp.cframe_table("z3")  # pre-populate the cache via the plain (sequential) path

    import telemetry_mining.exposure as exposure_mod

    def fail_if_called(*a, **k):
        raise AssertionError("should not spawn a worker for an already-cached camera")

    monkeypatch.setattr(exposure_mod, "_read_cframe_camera", fail_if_called)
    tables, errors = exp.cframe_tables(["z3"])
    assert errors == {}
    assert tables["z3"] is exp._cframe_table_cache["z3"]


def test_cframe_tables_reports_per_camera_errors_without_raising(tmp_path):
    """A missing/unreadable camera must land in `errors`, not crash the whole batch --
    mirrors the try/except-and-skip pattern used when looping cframe_table one at a time."""
    cfg, _ = build_exposure_dir(tmp_path)
    build_cframe_file(cfg, 20240925, 255020, camera="z3")
    exp = Exposure(255020, night=20240925, config=cfg)

    tables, errors = exp.cframe_tables(["z3", "z9"])  # z9's cframe file was never created
    assert set(tables) == {"z3"}
    assert set(errors) == {"z9"}
    assert isinstance(errors["z9"], Exception)


def test_cframe_never_touched_by_repr_or_summary(tmp_path):
    """No cframe file exists for this exposure at all -- repr()/summary() must not try to read one."""
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)
    repr(exp)
    exp.summary()


def write_exposure_table(cfg, night, rows):
    yyyymm = str(night)[:6]
    table_dir = cfg.redux_root / "daily" / "exposure_tables" / yyyymm
    table_dir.mkdir(parents=True)
    path = table_dir / f"exposure_table_{night}.csv"
    header = ["EXPID", "OBSTYPE", "LASTSTEP", "CAMWORD", "BADCAMWORD", "BADAMPS", "EXPFLAG", "HEADERERR", "COMMENTS"]
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(str(row.get(h, "")) for h in header))
    path.write_text("\n".join(lines) + "\n")
    return path


def test_exposure_table_flags_parses_real_shaped_rows(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    write_exposure_table(cfg, 20240925, [
        {"EXPID": 255020, "OBSTYPE": "science", "LASTSTEP": "all", "CAMWORD": "a123456789",
         "BADCAMWORD": "", "BADAMPS": "", "EXPFLAG": "metadata_missing|", "HEADERERR": "SEQTOT:->1|",
         "COMMENTS": "some human note|"},
        {"EXPID": 255021, "OBSTYPE": "science", "LASTSTEP": "skysub", "CAMWORD": "a123456789",
         "BADCAMWORD": "", "BADAMPS": "", "EXPFLAG": "|", "HEADERERR": "|", "COMMENTS": "|"},
    ])
    exp = Exposure(255020, night=20240925, config=cfg)

    flags = exp.exposure_table_flags
    assert flags["LASTSTEP"] == "all"
    assert flags["CAMWORD"] == "a123456789"
    assert flags["BADCAMWORD"] is None  # blank CSV cell, not the NaN pandas would otherwise give back
    assert flags["EXPFLAG"] == ["metadata_missing"]
    assert flags["HEADERERR"] == ["SEQTOT:->1"]
    assert "COMMENTS" not in flags  # deliberately excluded: free-form human notes, not structured

    exp2 = Exposure(255021, night=20240925, config=cfg)
    assert exp2.exposure_table_flags["EXPFLAG"] == []  # a bare '|' means "no flags", not one flag called '|'
    assert exp2.exposure_table_flags["HEADERERR"] == []


def test_exposure_table_flags_none_when_expid_absent(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    write_exposure_table(cfg, 20240925, [
        {"EXPID": 999999, "OBSTYPE": "science", "LASTSTEP": "all", "CAMWORD": "a123456789",
         "BADCAMWORD": "", "BADAMPS": "", "EXPFLAG": "|", "HEADERERR": "|", "COMMENTS": "|"},
    ])
    exp = Exposure(255020, night=20240925, config=cfg)
    assert exp.exposure_table_flags is None


def test_exposure_table_flags_none_without_redux(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    kpno_cfg = Config(site="kpno", exposures_root=cfg.exposures_root, redux_root=None)
    exp = Exposure(255020, night=20240925, config=kpno_cfg)
    assert exp.exposure_table_flags is None


def test_exposure_table_flags_cached(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    write_exposure_table(cfg, 20240925, [
        {"EXPID": 255020, "OBSTYPE": "science", "LASTSTEP": "all", "CAMWORD": "a123456789",
         "BADCAMWORD": "", "BADAMPS": "", "EXPFLAG": "|", "HEADERERR": "|", "COMMENTS": "|"},
    ])
    exp = Exposure(255020, night=20240925, config=cfg)
    assert exp.exposure_table_flags is exp.exposure_table_flags


def build_gfa_summary_file(cfg, rows):
    gfa_dir = cfg.gfa_root
    gfa_dir.mkdir(parents=True, exist_ok=True)
    path = gfa_dir / "offline_matched_coadd_ccds_main-thru_20260714.fits"
    data = np.array(rows, dtype=[("EXPID", "i8"), ("FWHM_ASEC", "f8"), ("MOON_ILLUMINATION", "f8")])
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(None)
        f.write(data, extname="EXPOSURE_SUMMARY_STRICT")
    return path


def test_exposure_gfa_row(tmp_path):
    from dataclasses import replace

    gfa._cache.clear()
    cfg, _ = build_exposure_dir(tmp_path)
    cfg = replace(cfg, gfa_root=tmp_path / "gfa")
    build_gfa_summary_file(cfg, [(255020, 1.4, 0.5)])

    exp = Exposure(255020, night=20240925, config=cfg)
    assert exp.gfa_row["FWHM_ASEC"] == pytest.approx(1.4)
    assert exp.gfa_row is exp.gfa_row  # cached


def test_exposure_gfa_row_none_without_gfa_root(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)  # cfg.gfa_root defaults to None
    assert exp.gfa_row is None


def build_exposure_qa_file(cfg, night, expid, header):
    qa_dir = cfg.redux_root / "daily" / "exposures" / str(night) / f"{expid:08d}"
    qa_dir.mkdir(parents=True, exist_ok=True)
    path = qa_dir / f"exposure-qa-{expid:08d}.fits"
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(None)
        data = np.array([(1.0,)], dtype=[("X", "f8")])
        f.write(data, extname="FIBERQA", header=header)
    return path


def test_exposure_fiberqa(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    build_exposure_qa_file(cfg, 20240925, 255020, {
        "NGOODFIB": 4719, "NGOODPET": 10, "WORSTRDN": 5.13, "FPRMS2D": 0.0079, "EFFTIME": 164.6,
    })
    exp = Exposure(255020, night=20240925, config=cfg)
    fq = exp.fiberqa
    assert fq["NGOODFIB"] == 4719
    assert fq["NGOODPET"] == 10
    assert fq["WORSTRDN"] == pytest.approx(5.13)
    assert exp.fiberqa is exp.fiberqa  # cached


def test_exposure_fiberqa_none_when_file_missing(tmp_path):
    """Simulates the pruned-old-exposure case: no exposure-qa file at all."""
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)
    assert exp.fiberqa is None


def test_exposure_fiberqa_none_without_redux(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    kpno_cfg = Config(site="kpno", exposures_root=cfg.exposures_root, redux_root=None)
    exp = Exposure(255020, night=20240925, config=kpno_cfg)
    assert exp.fiberqa is None


def test_gfa_and_fiberqa_never_touched_by_repr_or_summary(tmp_path):
    """No GFA/exposure-qa files exist at all -- repr()/summary() must not try to read them."""
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)
    repr(exp)
    exp.summary()


def build_petalqa_file(cfg, night, expid, rows):
    qa_dir = cfg.redux_root / "daily" / "exposures" / str(night) / f"{expid:08d}"
    qa_dir.mkdir(parents=True, exist_ok=True)
    path = qa_dir / f"exposure-qa-{expid:08d}.fits"
    data = np.array(rows, dtype=[("PETAL_LOC", "i2"), ("NGOODPOS", "i4"), ("NGOODFIB", "i4"), ("NSTDSTAR", "i4")])
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(None)
        f.write(data, extname="PETALQA")
    return path


def test_exposure_petalqa(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    build_petalqa_file(cfg, 20240925, 255020, [(0, 471, 464, 10), (1, 468, 460, 9)])
    exp = Exposure(255020, night=20240925, config=cfg)
    pq = exp.petalqa
    assert list(pq.index) == [0, 1]
    assert pq.loc[0, "NGOODPOS"] == 471
    assert pq.loc[1, "NSTDSTAR"] == 9
    assert exp.petalqa is exp.petalqa  # cached


def test_exposure_petalqa_none_when_file_missing(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)
    assert exp.petalqa is None


def test_exposure_petalqa_none_without_redux(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    kpno_cfg = Config(site="kpno", exposures_root=cfg.exposures_root, redux_root=None)
    exp = Exposure(255020, night=20240925, config=kpno_cfg)
    assert exp.petalqa is None


def build_fiberqa_table_file(cfg, night, expid, rows):
    qa_dir = cfg.redux_root / "daily" / "exposures" / str(night) / f"{expid:08d}"
    qa_dir.mkdir(parents=True, exist_ok=True)
    path = qa_dir / f"exposure-qa-{expid:08d}.fits"
    data = np.array(
        rows,
        dtype=[("PETAL_LOC", "i2"), ("DEVICE_LOC", "i4"), ("QAFIBERSTATUS", "i4"), ("EFFTIME_SPEC", "f4")],
    )
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(None)
        f.write(data, extname="FIBERQA")
    return path


def test_exposure_fiberqa_table(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    build_fiberqa_table_file(cfg, 20240925, 255020, [(0, 311, 0, 187.6), (0, 312, 4, 0.0)])
    exp = Exposure(255020, night=20240925, config=cfg)
    ft = exp.fiberqa_table
    assert list(ft.index) == [(0, 311), (0, 312)]
    assert ft.loc[(0, 311), "QAFIBERSTATUS"] == 0
    assert ft.loc[(0, 312), "QAFIBERSTATUS"] == 4
    assert exp.fiberqa_table is exp.fiberqa_table  # cached


def test_exposure_fiberqa_table_none_when_file_missing(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)
    assert exp.fiberqa_table is None


def test_exposure_fiberqa_table_none_without_redux(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    kpno_cfg = Config(site="kpno", exposures_root=cfg.exposures_root, redux_root=None)
    exp = Exposure(255020, night=20240925, config=kpno_cfg)
    assert exp.fiberqa_table is None


def build_calibstars_file(cfg, night, expid, rows):
    qa_dir = cfg.redux_root / "daily" / "exposures" / str(night) / f"{expid:08d}"
    qa_dir.mkdir(parents=True, exist_ok=True)
    path = qa_dir / f"calibstars-{expid:08d}.csv"
    import pandas as pd

    pd.DataFrame(rows, columns=["FIBER", "RCALIBFRAC", "EBV", "VALID"]).to_csv(path, index=False)
    return path


def test_exposure_calibstars(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    build_calibstars_file(cfg, 20240925, 255020, [(201, 0.924257, 0.0198, 1), (398, 1.064943, 0.0194, 1)])
    exp = Exposure(255020, night=20240925, config=cfg)
    cs = exp.calibstars
    assert list(cs.index) == [201, 398]
    assert cs.loc[201, "RCALIBFRAC"] == pytest.approx(0.924257)
    assert exp.calibstars is exp.calibstars  # cached


def test_exposure_calibstars_none_when_file_missing(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)
    assert exp.calibstars is None


def test_exposure_calibstars_none_without_redux(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    kpno_cfg = Config(site="kpno", exposures_root=cfg.exposures_root, redux_root=None)
    exp = Exposure(255020, night=20240925, config=kpno_cfg)
    assert exp.calibstars is None


def test_table_source_dispatches_and_caches(tmp_path):
    import pandas as pd

    cfg, _ = build_exposure_dir(tmp_path)
    df = pd.DataFrame({"EXPID": [255020], "CUSTOM_VAL": [42]})
    source = TableSource(name="my_saved_query", dataframe=df)
    exp = Exposure(255020, night=20240925, config=cfg, table_sources=[source])

    assert exp.table_source_names == ["my_saved_query"]
    row = exp.table_source("my_saved_query")
    assert row["CUSTOM_VAL"] == 42
    assert exp.table_source("my_saved_query") is row  # cached
    assert exp.all_table_sources() == {"my_saved_query": row}


def test_table_source_unknown_name_raises(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg, table_sources=[])
    with pytest.raises(KeyError):
        exp.table_source("nope")


def test_duplicate_table_source_names_raise_at_construction(tmp_path):
    import pandas as pd

    cfg, _ = build_exposure_dir(tmp_path)
    df = pd.DataFrame({"EXPID": [1]})
    sources = [TableSource(name="dup", dataframe=df), TableSource(name="dup", dataframe=df)]
    with pytest.raises(ValueError):
        Exposure(255020, night=20240925, config=cfg, table_sources=sources)


def test_default_table_sources_are_snapshotted_at_construction(tmp_path):
    import pandas as pd

    from telemetry_mining import tables

    cfg, _ = build_exposure_dir(tmp_path)
    df = pd.DataFrame({"EXPID": [255020], "V": [1]})
    tables.DEFAULT_TABLE_SOURCES.append(TableSource(name="global_source", dataframe=df))

    exp_before = Exposure(255020, night=20240925, config=cfg)
    assert "global_source" in exp_before.table_source_names

    tables.DEFAULT_TABLE_SOURCES.append(TableSource(name="added_later", dataframe=df))
    assert "added_later" not in exp_before.table_source_names  # snapshot, not a live reference

    exp_after = Exposure(255020, night=20240925, config=cfg)
    assert "added_later" in exp_after.table_source_names


def build_fiberassign_file(cfg, night, expid, tileid, rows):
    directory = cfg.exposures_root / str(night) / f"{expid:08d}"
    path = directory / f"fiberassign-{tileid:06d}.fits.gz"
    data = np.array(
        rows,
        dtype=[("PETAL_LOC", "i2"), ("DEVICE_LOC", "i4"), ("FIBER", "i4"), ("DESI_TARGET", "i8")],
    )
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(None)
        f.write(data, extname="FIBERASSIGN")
    return path


def test_exposure_fiberassign_table(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path, extra_header={"TILEID": 22258})
    build_fiberassign_file(cfg, 20240925, 255020, 22258, [(0, 311, 0, 42), (0, 312, 1, 43)])
    exp = Exposure(255020, night=20240925, config=cfg)
    ft = exp.fiberassign_table
    assert list(ft.index) == [(0, 311), (0, 312)]
    assert ft.loc[(0, 311), "DESI_TARGET"] == 42
    assert exp.fiberassign_table is exp.fiberassign_table  # cached


def test_exposure_fiberassign_table_none_when_file_missing(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path, extra_header={"TILEID": 22258})
    exp = Exposure(255020, night=20240925, config=cfg)
    assert exp.fiberassign_table is None


def test_exposure_fiberassign_table_none_when_tileid_missing(tmp_path):
    cfg, _ = build_exposure_dir(tmp_path)
    exp = Exposure(255020, night=20240925, config=cfg)
    assert exp.header.get("TILEID") is None
    assert exp.fiberassign_table is None


def test_exposure_fiberassign_table_none_when_main_fits_missing(tmp_path):
    """Real gap, not hypothetical: a DB record can exist for an exposure whose raw
    desi-<expid>.fits.fz was never archived/is gone -- header (which fiberassign_table
    needs, for TILEID) raises by design in that case; fiberassign_table must not."""
    cfg, _ = build_exposure_dir(tmp_path, extra_header={"TILEID": 22258})
    build_fiberassign_file(cfg, 20240925, 255020, 22258, [(0, 311, 0, 42)])
    exp = Exposure(255020, night=20240925, config=cfg)

    main_fits = cfg.exposures_root / "20240925" / "00255020" / "desi-00255020.fits.fz"
    main_fits.unlink()

    with pytest.raises(Exception):
        _ = exp.header
    assert exp.fiberassign_table is None
