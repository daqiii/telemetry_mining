import datetime as dt

import pandas as pd
import pytest

from telemetry_mining import db, find_alarms
from telemetry_mining.config import Config


def make_config(tmp_path):
    return Config(site="test", exposures_root=tmp_path / "e", redux_root=tmp_path / "r")


def _capture(monkeypatch):
    cap = {}
    monkeypatch.setattr(
        db, "fetch_df",
        lambda config, query, params=None: (cap.update(q=query, p=params), pd.DataFrame())[1],
    )
    return cap


def test_find_alarms_alarm_id_only(monkeypatch, tmp_path):
    cap = _capture(monkeypatch)
    find_alarms(make_config(tmp_path), alarm_id=9200)
    assert cap["q"] == "SELECT * FROM alarms.alarms WHERE alarm_id = %s ORDER BY time_recorded ASC"
    assert cap["p"] == [9200]


def test_find_alarms_all_filters_and_limit(monkeypatch, tmp_path):
    cap = _capture(monkeypatch)
    since = dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc)
    until = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    find_alarms(make_config(tmp_path), alarm_id=9200, level=["CRITICAL", "ALERT"],
                component="OCS", since=since, until=until, message_like="%offset%",
                columns=["id", "time_recorded", "message"], limit=5)
    q = cap["q"]
    assert q.startswith("SELECT id, time_recorded, message FROM alarms.alarms WHERE ")
    for frag in ("alarm_id = %s", "level = ANY(%s)", "component = %s",
                 "time_recorded >= %s", "time_recorded <= %s", "message LIKE %s"):
        assert frag in q
    assert q.endswith("ORDER BY time_recorded ASC LIMIT 5")
    assert cap["p"] == [9200, ["CRITICAL", "ALERT"], "OCS", since, until, "%offset%"]


def test_find_alarms_single_level_is_scalar(monkeypatch, tmp_path):
    cap = _capture(monkeypatch)
    find_alarms(make_config(tmp_path), level="WARNING")
    assert "level = %s" in cap["q"] and "ANY" not in cap["q"]
    assert cap["p"] == ["WARNING"]


def test_find_alarms_no_filters_selects_all(monkeypatch, tmp_path):
    cap = _capture(monkeypatch)
    find_alarms(make_config(tmp_path))
    assert cap["q"] == "SELECT * FROM alarms.alarms ORDER BY time_recorded ASC"
    assert cap["p"] is None  # no WHERE params -> None, not []


def test_find_alarms_rejects_bad_column_identifier(tmp_path):
    with pytest.raises(ValueError):
        find_alarms(make_config(tmp_path), columns=["id; drop table alarms"])


def test_find_alarms_rejects_nonpositive_limit(tmp_path):
    with pytest.raises(ValueError):
        find_alarms(make_config(tmp_path), limit=0)
