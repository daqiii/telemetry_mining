import numpy as np
import pytest

fitsio = pytest.importorskip("fitsio")

from telemetry_mining import gfa
from telemetry_mining.config import Config
from telemetry_mining.exceptions import DataSourceUnavailableError


def make_config(tmp_path):
    gfa_dir = tmp_path / "gfa"
    gfa_dir.mkdir(parents=True)
    return Config(site="test", exposures_root=tmp_path / "exposures", redux_root=None, gfa_root=gfa_dir)


def write_summary_file(cfg, date_suffix, rows):
    path = cfg.gfa_root / f"offline_matched_coadd_ccds_main-thru_{date_suffix}.fits"
    data = np.array(rows, dtype=[("EXPID", "i8"), ("FWHM_ASEC", "f8"), ("MOON_ILLUMINATION", "f8")])
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(None)
        f.write(np.zeros(1, dtype=[("X", "i4")]), extname="CAMERA_SUMMARY")
        f.write(np.zeros(1, dtype=[("X", "i4")]), extname="EXPOSURE_SUMMARY")
        f.write(data, extname="EXPOSURE_SUMMARY_STRICT")
    return path


def test_resolves_most_recent_file_by_glob(tmp_path):
    cfg = make_config(tmp_path)
    write_summary_file(cfg, "20260101", [(1, 1.0, 0.1)])
    newest = write_summary_file(cfg, "20260714", [(2, 2.0, 0.2)])
    assert gfa._gfa_summary_path(cfg) == newest


def test_gfa_summary_row_found(tmp_path):
    gfa._cache.clear()
    cfg = make_config(tmp_path)
    write_summary_file(cfg, "20260714", [(359483, 1.53, 0.91)])
    row = gfa.gfa_summary_row(359483, cfg)
    assert row is not None
    assert row["FWHM_ASEC"] == pytest.approx(1.53)


def test_gfa_summary_row_missing_expid_is_none(tmp_path):
    gfa._cache.clear()
    cfg = make_config(tmp_path)
    write_summary_file(cfg, "20260714", [(359483, 1.53, 0.91)])
    assert gfa.gfa_summary_row(1, cfg) is None


def test_gfa_summary_row_none_without_gfa_root(tmp_path):
    cfg = Config(site="kpno", exposures_root=tmp_path / "exposures", redux_root=None, gfa_root=None)
    assert gfa.gfa_summary_row(359483, cfg) is None


def test_gfa_summary_row_none_when_no_file_found(tmp_path):
    cfg = make_config(tmp_path)  # gfa_root exists but is empty
    assert gfa.gfa_summary_row(359483, cfg) is None


def test_load_gfa_summary_raises_without_gfa_root(tmp_path):
    cfg = Config(site="kpno", exposures_root=tmp_path / "exposures", redux_root=None, gfa_root=None)
    with pytest.raises(DataSourceUnavailableError):
        gfa.load_gfa_summary(cfg)


def test_load_gfa_summary_raises_when_no_file_found(tmp_path):
    cfg = make_config(tmp_path)
    with pytest.raises(DataSourceUnavailableError):
        gfa.load_gfa_summary(cfg)


def test_cache_invalidated_on_file_change(tmp_path):
    import time

    gfa._cache.clear()
    cfg = make_config(tmp_path)
    path = write_summary_file(cfg, "20260714", [(1, 1.0, 0.1)])
    first = gfa.load_gfa_summary(cfg)
    assert len(first) == 1

    time.sleep(0.01)
    data = np.array([(1, 1.0, 0.1), (2, 2.0, 0.2)], dtype=[("EXPID", "i8"), ("FWHM_ASEC", "f8"), ("MOON_ILLUMINATION", "f8")])
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(None)
        f.write(data, extname="EXPOSURE_SUMMARY_STRICT")
    second = gfa.load_gfa_summary(cfg)
    assert len(second) == 2
