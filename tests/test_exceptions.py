"""Pickling round-trips for the custom exception hierarchy.

Each of these has a custom __init__ requiring extra positional args beyond
just the message. Python's default Exception pickling replays
__init__(*self.args), but self.args only holds what was passed to
Exception.__init__() (the formatted message) -- not the original
constructor args -- so without an explicit __reduce__, unpickling any of
these raises a fresh TypeError instead of reconstructing the original
error. This matters concretely for ProcessPoolExecutor (see
Exposure.cframe_tables): an error raised in a worker process must survive
being pickled back to the parent, or the whole pool aborts instead of
surfacing a normal per-task exception.
"""

import pickle

from telemetry_mining.exceptions import (
    DatabaseUnavailableError,
    DataSourceUnavailableError,
    ExposureNotFoundError,
    MissingDependencyError,
)


def test_exposure_not_found_error_pickles():
    original = ExposureNotFoundError(255020, "no such file")
    restored = pickle.loads(pickle.dumps(original))
    assert restored.expid == 255020
    assert restored.detail == "no such file"
    assert str(restored) == str(original)


def test_missing_dependency_error_pickles():
    original = MissingDependencyError("fitsio", ValueError("boom"))
    restored = pickle.loads(pickle.dumps(original))
    assert restored.module_name == "fitsio"
    assert isinstance(restored.original_error, ValueError)
    assert str(restored) == str(original)


def test_database_unavailable_error_pickles():
    original = DatabaseUnavailableError(ConnectionError("no route to host"))
    restored = pickle.loads(pickle.dumps(original))
    assert isinstance(restored.original_error, ConnectionError)
    assert str(restored) == str(original)


def test_data_source_unavailable_error_pickles():
    """No custom __init__ on this one -- default Exception pickling already works."""
    original = DataSourceUnavailableError("no redux pipeline at this site")
    restored = pickle.loads(pickle.dumps(original))
    assert str(restored) == str(original)
