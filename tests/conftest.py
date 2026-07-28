"""Shared pytest configuration.

Tests marked `live` touch the real NERSC filesystem and/or the replicator DB
and are skipped unless explicitly requested with --run-live (or `-m live`).
"""

import pytest

from telemetry_mining import db, tables, telemetry


@pytest.fixture(autouse=True)
def _reset_telemetry_mining_state():
    """Isolate tests from module-level shared state.

    db._connection_cache() is a thread-local connection cache keyed by
    (host, port, dbname, user, password); tests that use the same fake host
    string would otherwise silently reuse another test's fake connection
    object (within the same thread -- pytest runs all tests on the main
    thread, so this still matters here).
    telemetry.DEFAULT_TELEMETRY_FIELDS and tables.DEFAULT_TABLE_SOURCES are
    mutable registries tests may append to; restore both so one test's
    additions don't leak into the next.
    """
    db.close_all_connections()
    saved_default_fields = list(telemetry.DEFAULT_TELEMETRY_FIELDS)
    saved_default_sources = list(tables.DEFAULT_TABLE_SOURCES)
    yield
    db.close_all_connections()
    telemetry.DEFAULT_TELEMETRY_FIELDS[:] = saved_default_fields
    tables.DEFAULT_TABLE_SOURCES[:] = saved_default_sources


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="run tests marked 'live' (require NERSC filesystem + DB access)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live"):
        return
    if "live" in (config.getoption("-m") or ""):
        return
    skip_live = pytest.mark.skip(reason="use --run-live or -m live to run tests that need NERSC/DB access")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
