from telemetry_mining.config import Config, _detect_site


def test_detect_site_nersc():
    assert _detect_site("nersc-db-host.lbl.gov") == "nersc"


def test_detect_site_kpno():
    assert _detect_site("some-mountain-host") == "kpno"


def test_detect_site_unknown():
    assert _detect_site("") == "unknown"


def test_default_reads_env(monkeypatch):
    monkeypatch.setenv("DOS_DB_HOST", "nersc-db-host.lbl.gov")
    monkeypatch.setenv("DOS_DB_NAME", "desi_dev")
    monkeypatch.setenv("DOS_DB_PORT", "5432")
    monkeypatch.setenv("DOS_DB_READER", "desi_reader")
    monkeypatch.setenv("DOS_DB_READER_PASSWORD", "reader")

    cfg = Config.default()

    assert cfg.site == "nersc"
    assert str(cfg.exposures_root) == "/global/cfs/cdirs/desi/spectro/data"
    assert cfg.db_name == "desi_dev"
    assert cfg.db_port == 5432


def test_config_fields_overridable(tmp_path):
    cfg = Config(
        site="test",
        exposures_root=tmp_path / "exposures",
        redux_root=tmp_path / "redux",
        redux_release="test-release",
    )
    assert cfg.redux_daily_dir == tmp_path / "redux" / "test-release"
    assert cfg.exposures_daily_csv == tmp_path / "redux" / "test-release" / "exposures-daily.csv"


def test_default_at_kpno_has_no_redux_root(monkeypatch):
    """KPNO has no offline/redux pipeline at all -- not just a different path for it."""
    monkeypatch.setenv("DOS_DB_HOST", "kpno-db-host.example")
    monkeypatch.setenv("DOS_DB_NAME", "desi_dev")

    cfg = Config.default()

    assert cfg.site == "kpno"
    assert str(cfg.exposures_root) == "/exposures/desi"
    assert cfg.redux_root is None


def test_redux_root_none_propagates_to_derived_paths(tmp_path):
    cfg = Config(site="kpno", exposures_root=tmp_path / "exposures", redux_root=None)
    assert cfg.redux_daily_dir is None
    assert cfg.exposures_daily_csv is None
