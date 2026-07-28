from telemetry_mining import db, paths
from telemetry_mining.config import Config
from telemetry_mining.exceptions import ExposureNotFoundError


def make_config(tmp_path):
    return Config(
        site="test",
        exposures_root=tmp_path / "exposures",
        redux_root=tmp_path / "redux",
    )


def test_exposure_directory_pure(tmp_path):
    cfg = make_config(tmp_path)
    directory = paths.exposure_directory(255020, 20240925, cfg)
    assert directory == tmp_path / "exposures" / "20240925" / "00255020"


def test_resolve_night_uses_db(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)

    def fake_fetch_one(config, query, params=None):
        assert params == (255020,)
        return {"night": 20240925}

    monkeypatch.setattr(db, "fetch_one", fake_fetch_one)
    assert paths.resolve_night(255020, cfg) == 20240925


def test_resolve_night_missing_raises(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    monkeypatch.setattr(db, "fetch_one", lambda config, query, params=None: None)
    try:
        paths.resolve_night(999999, cfg)
        assert False, "expected ExposureNotFoundError"
    except ExposureNotFoundError as exc:
        assert exc.expid == 999999


def test_exposure_paths_naming(tmp_path):
    directory = tmp_path / "20240925" / "00255020"
    p = paths.ExposurePaths(directory, 255020)
    assert p.main_fits == directory / "desi-00255020.fits.fz"
    assert p.coordinates == directory / "coordinates-00255020.fits"
    assert p.etc_json == directory / "etc-00255020.json"
    assert p.guide_frame0 == directory / "guide-00255020-0000.fits.fz"
    assert p.guide_rois == directory / "guide-rois-00255020.fits.fz"
    assert p.fiberassign(22258) == directory / "fiberassign-022258.fits.gz"


def test_cframe_path(tmp_path):
    directory = tmp_path / "exposures" / "20240925" / "00255020"
    p = paths.ExposurePaths(directory, 255020)
    redux_root = tmp_path / "redux"
    cframe = p.cframe(redux_root, 20240925, "z3")
    assert cframe == redux_root / "daily" / "exposures" / "20240925" / "00255020" / "cframe-z3-00255020.fits.gz"


def test_find_exposures_requires_a_filter(tmp_path):
    cfg = make_config(tmp_path)
    try:
        paths.find_exposures(cfg)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_find_exposures_builds_query_and_refs(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    captured = {}

    def fake_fetch_all(config, query, params=None):
        captured["query"] = query
        captured["params"] = params
        return [
            {"id": 255020, "night": 20240925, "sequence": "DESI"},
            {"id": 255021, "night": 20240925, "sequence": "DESI"},
        ]

    monkeypatch.setattr(db, "fetch_all", fake_fetch_all)
    refs = paths.find_exposures(cfg, sequence="DESI", night=20240925, limit=5)

    assert "sequence = %s" in captured["query"]
    assert "night = %s" in captured["query"]
    assert captured["params"] == ("DESI", 20240925, 5)
    assert len(refs) == 2
    assert refs[0] == paths.ExposureRef(
        expid=255020,
        night=20240925,
        sequence="DESI",
        directory=cfg.exposures_root / "20240925" / "00255020",
    )


def test_find_exposures_night_range(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    captured = {}

    def fake_fetch_all(config, query, params=None):
        captured["query"] = query
        captured["params"] = params
        return []

    monkeypatch.setattr(db, "fetch_all", fake_fetch_all)
    paths.find_exposures(cfg, night_range=(20240901, 20240930))

    assert "night >= %s AND night <= %s" in captured["query"]
    assert captured["params"] == (20240901, 20240930, 2000)


def test_find_last_exposure_returns_first_match(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)

    def fake_fetch_all(config, query, params=None):
        assert params == ("DESI",)
        return [{"id": 255021, "night": 20240925, "sequence": "DESI"}]

    monkeypatch.setattr(db, "fetch_all", fake_fetch_all)
    ref = paths.find_last_exposure(cfg, sequence="DESI")
    assert ref.expid == 255021


def test_find_last_exposure_skips_without_coords_when_required(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)

    def fake_fetch_all(config, query, params=None):
        return [
            {"id": 255022, "night": 20240925, "sequence": "DESI"},
            {"id": 255021, "night": 20240925, "sequence": "DESI"},
        ]

    monkeypatch.setattr(db, "fetch_all", fake_fetch_all)

    # give 255021 a real coordinates file, leave 255022 without one
    directory = paths.exposure_directory(255021, 20240925, cfg)
    directory.mkdir(parents=True)
    (directory / "coordinates-00255021.fits").write_text("fake")

    ref = paths.find_last_exposure(cfg, sequence="DESI", require_coords=True)
    assert ref.expid == 255021


def test_find_last_exposure_none_when_no_match(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    monkeypatch.setattr(db, "fetch_all", lambda config, query, params=None: [])
    assert paths.find_last_exposure(cfg, sequence="DESI") is None
