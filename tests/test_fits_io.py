import numpy as np
import pytest

fitsio = pytest.importorskip("fitsio")

from telemetry_mining import fits_io


def test_read_header(tmp_path):
    path = tmp_path / "desi-00000001.fits.fz"
    data = np.array([(1.0, 2.0)], dtype=[("X", "f8"), ("Y", "f8")])
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(None)  # primary HDU
        header = {"SKYRA": 40.5, "AIRMASS": 1.2, "SEQUENCE": "DESI"}
        f.write(data, extname="SPEC", header=header)

    header = fits_io.read_header(path)
    assert header["SKYRA"] == pytest.approx(40.5)
    assert header["AIRMASS"] == pytest.approx(1.2)
    assert header["SEQUENCE"] == "DESI"


def test_read_header_falls_back_to_primary(tmp_path):
    path = tmp_path / "no-spec.fits"
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(None, header={"FOO": "BAR"})

    header = fits_io.read_header(path, extension="SPEC")
    assert header["FOO"] == "BAR"


def test_read_coordinates(tmp_path):
    path = tmp_path / "coordinates-00000001.fits"
    data = np.array(
        [(1, 10, 100.0, 200.0), (1, 11, 101.0, 201.0), (2, 20, 102.0, 202.0)],
        dtype=[("PETAL_LOC", "i4"), ("DEVICE_LOC", "i4"), ("POS_X", "f8"), ("POS_Y", "f8")],
    )
    stationary = np.array(
        [(1, 999, 1)],
        dtype=[("PETAL_LOC", "i4"), ("DEVICE_LOC", "i4"), ("FIDUCIAL", "i4")],
    )
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(data, extname="DATA")
        f.write(stationary, extname="STATIONARY")

    coords = fits_io.read_coordinates(path)
    assert coords.shape == (3, 2)
    assert list(coords.index.names) == ["PETAL_LOC", "DEVICE_LOC"]
    assert coords.loc[(1, 10), "POS_X"] == pytest.approx(100.0)

    stat = fits_io.read_stationary(path)
    assert stat.shape == (1, 1)
    assert stat.loc[(1, 999), "FIDUCIAL"] == 1
