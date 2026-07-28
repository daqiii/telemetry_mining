"""PostgreSQL connection and query helpers for the DESI replicator DB.

Unlike DOSlib.util (which builds queries with raw ``%``-string
interpolation), everything here goes through parameterized queries or
``psycopg2.sql.Identifier`` for anything that must be interpolated as an
identifier (schema/table/column names), to avoid SQL injection.

``fetch_all``/``fetch_one``/``fetch_df`` reuse a cached connection per
(host, port, dbname, user, password) rather than opening a fresh TCP
connection and re-authenticating on every call -- this matters once a single
``Exposure`` can trigger half a dozen queries and a bulk analysis loops over
hundreds of exposures. The cache is **thread-local** (added 2026-07-20, for
``query.harvest``/``select_exposures``'s ``max_workers`` option): each thread
gets its own connection per DB identity, since a single psycopg2 connection
is not safe for concurrent queries from multiple threads at once. A plain
single-threaded script/notebook still gets exactly the old behavior (one
connection, reused for the process's lifetime, since it only ever has one
thread touching the cache).
"""

from __future__ import annotations

import contextlib
import threading
from typing import Any, Mapping, Sequence

from .config import Config
from .exceptions import DatabaseUnavailableError, MissingDependencyError


def _import_psycopg2():
    try:
        import psycopg2  # noqa: F401
        import psycopg2.extras  # noqa: F401
        import psycopg2.sql  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment dependent
        raise MissingDependencyError("psycopg2", exc) from exc
    import psycopg2

    return psycopg2


_local = threading.local()


def _connection_cache() -> dict[tuple, Any]:
    """Return (creating if needed) the calling thread's connection cache.

    A separate dict per thread, not one shared module-level dict -- a single
    psycopg2 connection can't safely be queried from multiple threads at
    once. A single-threaded script/notebook only ever touches its own dict,
    so this is behaviorally identical to the old process-wide cache there.
    """
    cache = getattr(_local, "connections", None)
    if cache is None:
        cache = {}
        _local.connections = cache
    return cache


def _connection_key(config: Config) -> tuple:
    return (config.db_host, config.db_port, config.db_name, config.db_user, config.db_password)


def _open_connection(config: Config):
    psycopg2 = _import_psycopg2()
    if not config.db_host or not config.db_name:
        raise DatabaseUnavailableError(
            RuntimeError("no DB host/name configured (DOS_DB_HOST/DOS_DB_NAME unset)")
        )
    try:
        conn = psycopg2.connect(
            dbname=config.db_name,
            host=config.db_host,
            port=config.db_port,
            user=config.db_user,
            password=config.db_password,
        )
        conn.autocommit = True
    except Exception as exc:
        raise DatabaseUnavailableError(exc) from exc
    return conn


def _get_connection(config: Config):
    """Return this thread's cached connection for this config's DB identity, opening one if needed."""
    cache = _connection_cache()
    key = _connection_key(config)
    conn = cache.get(key)
    if conn is not None and conn.closed == 0:
        return conn
    conn = _open_connection(config)
    cache[key] = conn
    return conn


def _discard_connection(config: Config) -> None:
    key = _connection_key(config)
    conn = _connection_cache().pop(key, None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def close_all_connections() -> None:
    """Close and forget every cached DB connection **for the calling thread**.

    Mostly useful for tests/cleanup on the main thread. Worker threads
    spawned by `query.harvest`/`select_exposures`'s `max_workers` option
    each hold their own connections in their own thread-local cache, not
    reachable from here -- they're released when those (short-lived,
    pool-managed) threads exit, not something a caller needs to manage.
    """
    cache = _connection_cache()
    for conn in cache.values():
        try:
            conn.close()
        except Exception:
            pass
    cache.clear()


@contextlib.contextmanager
def connect(config: Config):
    """Open a brand-new, one-off psycopg2 connection as a context manager.

    Most callers should use fetch_all/fetch_one/fetch_df instead, which reuse
    a cached connection rather than paying a fresh TCP+auth handshake per
    call. This is for advanced/manual use (e.g. explicit transaction control).
    """
    conn = _open_connection(config)
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(
    config: Config,
    query: str,
    params: Sequence[Any] | Mapping[str, Any] | None = None,
) -> list[dict]:
    """Run a parameterized query, return rows as a list of plain dicts.

    Reuses a cached connection; if it turns out to be stale (e.g. the server
    dropped an idle connection), discards it and retries once with a fresh one.
    """
    psycopg2 = _import_psycopg2()
    from psycopg2.extras import RealDictCursor

    last_exc: Exception | None = None
    for attempt in range(2):
        conn = _get_connection(config)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
        except psycopg2.OperationalError as exc:
            _discard_connection(config)
            last_exc = exc
        except psycopg2.Error as exc:
            raise DatabaseUnavailableError(exc) from exc
    raise DatabaseUnavailableError(last_exc)


def fetch_one(
    config: Config,
    query: str,
    params: Sequence[Any] | Mapping[str, Any] | None = None,
) -> dict | None:
    """Run a parameterized query, return the first row as a dict, or None."""
    rows = fetch_all(config, query, params)
    return rows[0] if rows else None


def fetch_df(
    config: Config,
    query: str,
    params: Sequence[Any] | Mapping[str, Any] | None = None,
):
    """Run a parameterized query, return the results as a pandas DataFrame."""
    import pandas as pd

    rows = fetch_all(config, query, params)
    return pd.DataFrame(rows)


def identifier(name: str):
    """Safely wrap a schema/table/column name for interpolation into SQL."""
    psycopg2 = _import_psycopg2()
    return psycopg2.sql.Identifier(name)


def sql_text(query: str):
    """Wrap a raw SQL fragment (e.g. built from Identifiers) as psycopg2.sql.SQL."""
    psycopg2 = _import_psycopg2()
    return psycopg2.sql.SQL(query)
