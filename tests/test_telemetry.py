import datetime as dt

import pytest

from telemetry_mining import db, telemetry
from telemetry_mining.config import Config


def make_config(tmp_path):
    return Config(site="test", exposures_root=tmp_path / "exposures", redux_root=tmp_path / "redux")


def test_query_nearest_picks_closer_candidate(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    when = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    before_row = {"value": 1, "time_recorded": when - dt.timedelta(seconds=100)}
    after_row = {"value": 2, "time_recorded": when + dt.timedelta(seconds=10)}
    calls = []

    def fake_fetch_one(config, query, params=None):
        calls.append(params)
        return before_row if len(calls) == 1 else after_row

    monkeypatch.setattr(db, "fetch_one", fake_fetch_one)
    result = telemetry.query_nearest(cfg, "some_table", when, columns=["value"])

    assert len(calls) == 2  # one bounded query each direction, not a window scan
    assert result["value"] == 2
    assert result["delta_seconds"] == pytest.approx(10.0)


def test_query_nearest_picks_before_when_closer(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    when = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    before_row = {"value": 1, "time_recorded": when - dt.timedelta(seconds=5)}
    after_row = {"value": 2, "time_recorded": when + dt.timedelta(seconds=500)}
    calls = []

    def fake_fetch_one(config, query, params=None):
        calls.append(params)
        return before_row if len(calls) == 1 else after_row

    monkeypatch.setattr(db, "fetch_one", fake_fetch_one)
    result = telemetry.query_nearest(cfg, "some_table", when)
    assert result["value"] == 1
    assert result["delta_seconds"] == pytest.approx(-5.0)


def test_query_nearest_returns_none_when_table_empty(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    monkeypatch.setattr(db, "fetch_one", lambda config, query, params=None: None)
    when = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    assert telemetry.query_nearest(cfg, "some_table", when) is None


def test_query_nearest_only_before_candidate_exists(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    when = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    before_row = {"time_recorded": when - dt.timedelta(seconds=42)}
    calls = []

    def fake_fetch_one(config, query, params=None):
        calls.append(1)
        return before_row if len(calls) == 1 else None

    monkeypatch.setattr(db, "fetch_one", fake_fetch_one)
    result = telemetry.query_nearest(cfg, "some_table", when)
    assert result["delta_seconds"] == pytest.approx(-42.0)


def test_query_nearest_respects_max_delta_seconds(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    when = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    far_row = {"time_recorded": when + dt.timedelta(days=400)}
    monkeypatch.setattr(db, "fetch_one", lambda config, query, params=None: far_row)

    assert telemetry.query_nearest(cfg, "some_table", when, max_delta_seconds=3600) is None
    result = telemetry.query_nearest(cfg, "some_table", when, max_delta_seconds=None)
    assert result is not None


def test_query_nearest_rejects_bad_identifiers(tmp_path):
    cfg = make_config(tmp_path)
    when = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    with pytest.raises(ValueError):
        telemetry.query_nearest(cfg, "bad; drop table x;", when)


def test_telemetry_field_validates_kind_and_when():
    telemetry.TelemetryField(name="ok", table="t")  # defaults are valid
    with pytest.raises(ValueError):
        telemetry.TelemetryField(name="bad_kind", table="t", kind="sideways")
    with pytest.raises(ValueError):
        telemetry.TelemetryField(name="bad_when", table="t", when="whenever")
