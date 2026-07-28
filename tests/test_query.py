from pathlib import Path

import pandas as pd
import pytest

from telemetry_mining import db
from telemetry_mining import paths as paths_mod
from telemetry_mining.config import Config
from telemetry_mining.query import harvest, resolve_spec, select_exposures


class _FakeExposure:
    """Stand-in for Exposure: exercises resolve_spec's path-walking without real files/DB."""

    def __init__(self, header=None, db_row=None, gfa_row=None, telemetry_values=None):
        self.header = header if header is not None else {}
        self.db_row = db_row if db_row is not None else {}
        self.gfa_row = gfa_row
        self._telemetry_values = telemetry_values or {}

    def telemetry_field(self, name):
        return self._telemetry_values[name]


def _config(tmp_path=None):
    return Config(site="nersc", exposures_root=Path(tmp_path or "/nonexistent"), redux_root=None)


# ---- resolve_spec ----


def test_resolve_spec_callable():
    exp = _FakeExposure()
    assert resolve_spec(exp, lambda e: 42) == 42


def test_resolve_spec_plain_header_key():
    exp = _FakeExposure(header={"ETCFRACB": 0.134257})
    assert resolve_spec(exp, "header.ETCFRACB") == pytest.approx(0.134257)


def test_resolve_spec_series_member():
    exp = _FakeExposure(gfa_row=pd.Series({"FWHM_ASEC": 1.53}))
    assert resolve_spec(exp, "gfa_row.FWHM_ASEC") == pytest.approx(1.53)


def test_resolve_spec_telemetry_field():
    exp = _FakeExposure(telemetry_values={"mirror_avg_temp": 18.9})
    assert resolve_spec(exp, "telemetry.mirror_avg_temp") == pytest.approx(18.9)


def test_resolve_spec_list_index_on_base_value():
    exp = _FakeExposure(header={"HEXPOS": [1347.3, -187.7, -1309.6, -18.4, 32.3, -33.0]})
    assert resolve_spec(exp, "header.HEXPOS[2]") == pytest.approx(-1309.6)


def test_resolve_spec_nested_dict_then_list_index():
    exp = _FakeExposure(db_row={"hexapod": {"hex_trim": [0.0, 0.0, 1.5, 0.0, 0.0, 0.0]}})
    assert resolve_spec(exp, "db_row.hexapod['hex_trim'][2]") == pytest.approx(1.5)


def test_resolve_spec_nested_dict_key():
    exp = _FakeExposure(db_row={"astrometry": {"astro_fwhm": 2.3}})
    assert resolve_spec(exp, "db_row.astrometry['astro_fwhm']") == pytest.approx(2.3)


def test_resolve_spec_rejects_non_string_non_callable():
    exp = _FakeExposure()
    with pytest.raises(TypeError):
        resolve_spec(exp, 123)


def test_resolve_spec_rejects_malformed_token():
    exp = _FakeExposure(header={})
    with pytest.raises(ValueError):
        resolve_spec(exp, "header.")


# ---- select_exposures ----


def test_select_exposures_pulls_db_columns_for_free(monkeypatch):
    calls = []

    def fake_fetch_all(config, query, params=None):
        calls.append((query, params))
        return [
            {"id": 100, "night": 20260101, "exptime": 900.0, "program": "dark"},
            {"id": 101, "night": 20260101, "exptime": 300.0, "program": "dark"},
        ]

    monkeypatch.setattr(db, "fetch_all", fake_fetch_all)

    table = select_exposures(
        "program = %s",
        columns={"exptime": "db_row.exptime", "doubled": lambda exp: exp.db_row["exptime"] * 2},
        config=_config(),
        params=("dark",),
    )

    assert list(table["EXPID"]) == [100, 101]
    assert list(table["NIGHT"]) == [20260101, 20260101]
    assert list(table["exptime"]) == [900.0, 300.0]
    assert list(table["doubled"]) == [1800.0, 600.0]
    assert len(calls) == 1  # one bulk query -- no per-exposure db_row re-fetch


def test_select_exposures_orders_by_id_by_default(monkeypatch):
    calls = []

    def fake_fetch_all(config, query, params=None):
        calls.append(query)
        return []

    monkeypatch.setattr(db, "fetch_all", fake_fetch_all)
    select_exposures("program = %s", config=_config(), params=("dark",))
    assert calls[0].rstrip().endswith("ORDER BY id")


def test_select_exposures_order_by_none_skips_ordering(monkeypatch):
    calls = []

    def fake_fetch_all(config, query, params=None):
        calls.append(query)
        return []

    monkeypatch.setattr(db, "fetch_all", fake_fetch_all)
    select_exposures("program = %s", config=_config(), params=("dark",), order_by=None)
    assert "ORDER BY" not in calls[0]


def test_select_exposures_custom_order_by(monkeypatch):
    calls = []

    def fake_fetch_all(config, query, params=None):
        calls.append(query)
        return []

    monkeypatch.setattr(db, "fetch_all", fake_fetch_all)
    select_exposures("program = %s", config=_config(), params=("dark",), order_by="night, id")
    assert calls[0].rstrip().endswith("ORDER BY night, id")


def test_select_exposures_raises_by_default_on_spec_failure(monkeypatch):
    monkeypatch.setattr(
        db, "fetch_all", lambda config, query, params=None: [{"id": 100, "night": 20260101}]
    )

    def boom(exp):
        raise FileNotFoundError("no such file")

    with pytest.raises(FileNotFoundError):
        select_exposures("night = %s", columns={"x": boom}, config=_config(), params=(20260101,))


def test_select_exposures_skip_drops_failing_row_and_records_it(monkeypatch):
    monkeypatch.setattr(
        db,
        "fetch_all",
        lambda config, query, params=None: [
            {"id": 100, "night": 20260101},
            {"id": 101, "night": 20260101},
        ],
    )

    def maybe_boom(exp):
        if exp.expid == 100:
            raise FileNotFoundError("no such file")
        return 42

    table = select_exposures(
        "night = %s", columns={"x": maybe_boom}, config=_config(), params=(20260101,), on_error="skip"
    )

    assert list(table["EXPID"]) == [101]
    assert list(table["x"]) == [42]
    assert set(table.attrs["skipped"]) == {100}
    assert isinstance(table.attrs["skipped"][100], FileNotFoundError)


def test_select_exposures_skip_drops_whole_row_not_just_failing_column(monkeypatch):
    """If any column spec fails for an exposure, the whole row is dropped -- even
    columns that would have resolved fine (e.g. a free db_row.* column)."""
    monkeypatch.setattr(
        db, "fetch_all", lambda config, query, params=None: [{"id": 100, "night": 20260101, "exptime": 900.0}]
    )

    def boom(exp):
        raise FileNotFoundError("no such file")

    table = select_exposures(
        "night = %s",
        columns={"exptime": "db_row.exptime", "x": boom},
        config=_config(),
        params=(20260101,),
        on_error="skip",
    )
    assert table.empty
    assert set(table.attrs["skipped"]) == {100}


def test_select_exposures_skipped_attrs_empty_dict_when_nothing_fails(monkeypatch):
    monkeypatch.setattr(
        db, "fetch_all", lambda config, query, params=None: [{"id": 100, "night": 20260101}]
    )
    table = select_exposures("night = %s", columns={"x": lambda exp: 1}, config=_config(), params=(20260101,))
    assert table.attrs["skipped"] == {}


def test_select_exposures_rejects_invalid_on_error(monkeypatch):
    monkeypatch.setattr(db, "fetch_all", lambda config, query, params=None: [])
    with pytest.raises(ValueError):
        select_exposures("night = %s", config=_config(), params=(20260101,), on_error="bogus")


def test_select_exposures_empty_result(monkeypatch):
    monkeypatch.setattr(db, "fetch_all", lambda config, query, params=None: [])
    table = select_exposures("night = %s", columns={"exptime": "db_row.exptime"}, config=_config(), params=(1,))
    assert table.empty


def test_select_exposures_max_workers_matches_sequential(monkeypatch):
    rows = [{"id": 100 + i, "night": 20260101} for i in range(20)]
    monkeypatch.setattr(db, "fetch_all", lambda config, query, params=None: rows)

    def double(exp):
        return exp.expid * 2

    sequential = select_exposures("1=1", columns={"x": double}, config=_config())
    threaded = select_exposures("1=1", columns={"x": double}, config=_config(), max_workers=4)

    assert list(threaded["EXPID"]) == list(sequential["EXPID"])
    assert list(threaded["x"]) == list(sequential["x"])


def test_select_exposures_max_workers_skip_still_records_all_errors(monkeypatch):
    rows = [{"id": 100 + i, "night": 20260101} for i in range(10)]
    monkeypatch.setattr(db, "fetch_all", lambda config, query, params=None: rows)

    def maybe_boom(exp):
        if exp.expid % 2 == 0:
            raise FileNotFoundError(f"no such file for {exp.expid}")
        return exp.expid

    table = select_exposures(
        "1=1", columns={"x": maybe_boom}, config=_config(), on_error="skip", max_workers=4
    )

    assert set(table["EXPID"]) == {expid for expid in range(100, 110) if expid % 2 == 1}
    assert set(table.attrs["skipped"]) == {expid for expid in range(100, 110) if expid % 2 == 0}


def test_select_exposures_max_workers_raise_still_propagates(monkeypatch):
    rows = [{"id": 100 + i, "night": 20260101} for i in range(10)]
    monkeypatch.setattr(db, "fetch_all", lambda config, query, params=None: rows)

    def boom_on_105(exp):
        if exp.expid == 105:
            raise FileNotFoundError("no such file")
        return exp.expid

    with pytest.raises(FileNotFoundError):
        select_exposures("1=1", columns={"x": boom_on_105}, config=_config(), max_workers=4)


# ---- harvest ----


def test_harvest_dict_mode_bulk_resolves_night(monkeypatch):
    def fake_fetch_all(config, query, params=None):
        return [{"id": 100, "night": 20260101}, {"id": 101, "night": 20260102}]

    monkeypatch.setattr(db, "fetch_all", fake_fetch_all)

    def fail_resolve_night(expid, config):
        raise AssertionError("resolve_night should not be called -- night was bulk-primed by harvest")

    monkeypatch.setattr(paths_mod, "resolve_night", fail_resolve_night)

    results = harvest([100, 101], lambda exp: exp.night, config=_config())
    assert results == {100: 20260101, 101: 20260102}


def test_harvest_falls_back_when_expid_missing_from_bulk_lookup(monkeypatch):
    monkeypatch.setattr(db, "fetch_all", lambda config, query, params=None: [])

    def fake_resolve_night(expid, config):
        return 20260101

    monkeypatch.setattr(paths_mod, "resolve_night", fake_resolve_night)

    results = harvest([999], lambda exp: exp.night, config=_config())
    assert results == {999: 20260101}


def test_harvest_concat_pools_rows_and_preserves_named_index(monkeypatch):
    monkeypatch.setattr(
        db, "fetch_all", lambda config, query, params=None: [{"id": 100, "night": 1}, {"id": 101, "night": 1}]
    )

    def fn(exp):
        return pd.DataFrame({"PETAL_LOC": [0, 1], "VAL": [exp.expid, exp.expid * 2]}).set_index("PETAL_LOC")

    pooled = harvest([100, 101], fn, config=_config(), concat=True)

    assert list(pooled["EXPID"]) == [100, 100, 101, 101]
    assert "PETAL_LOC" in pooled.columns
    assert list(pooled["VAL"]) == [100, 200, 101, 202]


def test_harvest_concat_skips_none_results(monkeypatch):
    monkeypatch.setattr(db, "fetch_all", lambda config, query, params=None: [{"id": 100, "night": 1}, {"id": 101, "night": 1}])

    def fn(exp):
        return None if exp.expid == 100 else pd.DataFrame({"X": [1]})

    pooled = harvest([100, 101], fn, config=_config(), concat=True)
    assert list(pooled["EXPID"]) == [101]


def test_harvest_empty_expids(monkeypatch):
    calls = []
    monkeypatch.setattr(db, "fetch_all", lambda config, query, params=None: calls.append(1))
    assert harvest([], lambda exp: exp.night, config=_config()) == {}
    assert harvest([], lambda exp: exp.night, config=_config(), concat=True).empty
    assert not calls  # no bulk query for an empty expid list


def test_harvest_max_workers_matches_sequential(monkeypatch):
    expids = list(range(100, 120))
    monkeypatch.setattr(db, "fetch_all", lambda config, query, params=None: [{"id": e, "night": 1} for e in expids])

    sequential = harvest(expids, lambda exp: exp.expid * 2, config=_config())
    threaded = harvest(expids, lambda exp: exp.expid * 2, config=_config(), max_workers=4)

    assert threaded == sequential


def test_harvest_max_workers_concat_matches_sequential(monkeypatch):
    expids = [100, 101, 102]
    monkeypatch.setattr(db, "fetch_all", lambda config, query, params=None: [{"id": e, "night": 1} for e in expids])

    def fn(exp):
        return pd.DataFrame({"PETAL_LOC": [0, 1], "VAL": [exp.expid, exp.expid * 2]}).set_index("PETAL_LOC")

    sequential = harvest(expids, fn, config=_config(), concat=True)
    threaded = harvest(expids, fn, config=_config(), concat=True, max_workers=4)

    pd.testing.assert_frame_equal(threaded, sequential)
