from pathlib import Path

import pytest

fitsio = pytest.importorskip("fitsio")

import numpy as np
import pandas as pd

from telemetry_mining.tables import TableSource, load_table, table_source_row


def test_requires_exactly_one_source():
    with pytest.raises(ValueError):
        TableSource(name="bad")
    with pytest.raises(ValueError):
        TableSource(name="bad", dataframe=pd.DataFrame({"EXPID": [1]}), path="x")


def test_dataframe_source_does_not_mutate_original():
    df = pd.DataFrame({"EXPID": [1, 2, 3], "MYVAL": [10, 20, 30]})
    source = TableSource(name="mine", dataframe=df)

    row = table_source_row(source, 2)
    assert row["MYVAL"] == 20
    assert df.index.name is None  # original untouched


def test_dataframe_source_missing_expid_is_none():
    df = pd.DataFrame({"EXPID": [1, 2, 3], "MYVAL": [10, 20, 30]})
    source = TableSource(name="mine", dataframe=df)
    assert table_source_row(source, 999) is None


def test_custom_index_column():
    df = pd.DataFrame({"expid_custom": [7, 8], "V": ["a", "b"]})
    source = TableSource(name="mine", dataframe=df, index_column="expid_custom")
    row = table_source_row(source, 8)
    assert row["V"] == "b"


def test_bad_index_column_raises():
    df = pd.DataFrame({"NOT_EXPID": [1, 2]})
    source = TableSource(name="mine", dataframe=df)
    with pytest.raises(ValueError):
        table_source_row(source, 1)


def test_loader_source():
    calls = []

    def make_df():
        calls.append(1)
        return pd.DataFrame({"EXPID": [5], "X": [42]})

    source = TableSource(name="mine", loader=make_df)
    row = table_source_row(source, 5)
    assert row["X"] == 42


def test_csv_path_source_and_cache(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("EXPID,VAL\n1,100\n2,200\n")
    source = TableSource(name="mine", path=path)

    row = table_source_row(source, 2)
    assert row["VAL"] == 200

    first = load_table(source)
    second = load_table(source)
    assert first is second  # cached, unchanged mtime/size


def test_parquet_path_source_and_cache(tmp_path):
    path = tmp_path / "data.parquet"
    pd.DataFrame({"EXPID": [1, 2], "VAL": [100, 200]}).to_parquet(path)
    source = TableSource(name="mine", path=path)

    row = table_source_row(source, 2)
    assert row["VAL"] == 200

    first = load_table(source)
    second = load_table(source)
    assert first is second  # cached, unchanged mtime/size


def test_csv_path_source_accepts_string_path(tmp_path):
    # `path=` given as a plain string (as the docs show) must work, not just a Path
    path = tmp_path / "data.csv"
    path.write_text("EXPID,VAL\n1,100\n2,200\n")
    source = TableSource(name="mine", path=str(path))

    assert isinstance(source.path, Path)  # coerced at construction
    assert table_source_row(source, 2)["VAL"] == 200


def test_csv_path_source_cache_invalidated_on_change(tmp_path):
    import time

    path = tmp_path / "data.csv"
    path.write_text("EXPID,VAL\n1,100\n")
    source = TableSource(name="mine", path=path)
    first = load_table(source)
    assert len(first) == 1

    time.sleep(0.01)
    path.write_text("EXPID,VAL\n1,100\n2,200\n")
    second = load_table(source)
    assert len(second) == 2


def test_fits_path_source(tmp_path):
    path = tmp_path / "data.fits"
    data = np.array([(1, 10.0), (2, 20.0)], dtype=[("EXPID", "i8"), ("VAL", "f8")])
    with fitsio.FITS(str(path), "rw", clobber=True) as f:
        f.write(None)
        f.write(data, extname="MYEXT")

    source = TableSource(name="mine", path=path, extension="MYEXT")
    row = table_source_row(source, 2)
    assert row["VAL"] == 20.0
