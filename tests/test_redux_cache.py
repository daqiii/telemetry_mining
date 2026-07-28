import time

import pytest

from telemetry_mining import redux
from telemetry_mining.config import Config
from telemetry_mining.exceptions import DataSourceUnavailableError


def make_config(tmp_path):
    redux_dir = tmp_path / "redux" / "daily"
    redux_dir.mkdir(parents=True)
    return Config(site="test", exposures_root=tmp_path / "exposures", redux_root=tmp_path / "redux")


def write_csv(cfg, rows):
    lines = ["NIGHT,EXPID,TILEID,EXPTIME"]
    lines += [",".join(str(v) for v in row) for row in rows]
    cfg.exposures_daily_csv.write_text("\n".join(lines) + "\n")


def test_redux_row_found(tmp_path):
    cfg = make_config(tmp_path)
    write_csv(cfg, [(20240925, 255020, 22258, 579.8)])
    row = redux.redux_row(255020, cfg)
    assert row is not None
    assert int(row["TILEID"]) == 22258


def test_redux_row_missing_is_none(tmp_path):
    cfg = make_config(tmp_path)
    write_csv(cfg, [(20240925, 255020, 22258, 579.8)])
    assert redux.redux_row(1, cfg) is None


def test_cache_invalidated_on_file_change(tmp_path):
    redux._cache.clear()
    cfg = make_config(tmp_path)
    write_csv(cfg, [(20240925, 255020, 22258, 579.8)])
    first = redux.load_exposures_daily(cfg)
    assert len(first) == 1

    # ensure a distinct mtime, then rewrite with an extra row
    time.sleep(0.01)
    write_csv(cfg, [(20240925, 255020, 22258, 579.8), (20240925, 255021, 22258, 300.0)])
    second = redux.load_exposures_daily(cfg)
    assert len(second) == 2


def test_cache_reused_when_unchanged(tmp_path):
    redux._cache.clear()
    cfg = make_config(tmp_path)
    write_csv(cfg, [(20240925, 255020, 22258, 579.8)])
    first = redux.load_exposures_daily(cfg)
    second = redux.load_exposures_daily(cfg)
    assert first is second


def test_redux_row_none_when_site_has_no_redux(tmp_path):
    """Simulates KPNO: Config.redux_root is None, not just a missing/wrong file."""
    cfg = Config(site="kpno", exposures_root=tmp_path / "exposures", redux_root=None)
    assert redux.redux_row(255020, cfg) is None


def test_load_exposures_daily_raises_clearly_when_site_has_no_redux(tmp_path):
    cfg = Config(site="kpno", exposures_root=tmp_path / "exposures", redux_root=None)
    with pytest.raises(DataSourceUnavailableError):
        redux.load_exposures_daily(cfg)
