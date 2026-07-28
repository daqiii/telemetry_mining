"""Generic queries over any telemetry.<table>: time-windows and nearest-value.

There are 93 tables in the `telemetry` schema. A handful (like
`guider_centroids`) carry an `expid` column and are queried directly by
exposure (see `exposure.py`). Most are pure time series with no per-exposure
key at all, keyed only by a `time_recorded` timestamp column -- for those,
the useful question is "what was this table's value closest to the
exposure's start time", not a window. This module offers both query shapes
generically rather than one hand-written method per table. Table/column/schema
names are validated against an identifier pattern and safely quoted via
psycopg2.sql.Identifier -- never string-interpolated directly into SQL.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Sequence

from . import db
from .config import Config

_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return name


def _build_column_sql(columns: Sequence[str] | None, *, require: str | None = None):
    """Validate and build a SELECT column-list fragment (or '*' if none given).

    `require`, if given and not already in `columns`, is appended -- used by
    query_nearest to guarantee the timestamp column comes back even if the
    caller only asked for other columns, since it's needed to compute
    delta_seconds.
    """
    if not columns:
        return db.sql_text("*")
    cols = list(columns)
    for c in cols:
        _validate_identifier(c)
    if require is not None and require not in cols:
        cols.append(require)
    return db.sql_text(", ").join(db.identifier(c) for c in cols)


def query_window(
    config: Config,
    table: str,
    start: dt.datetime,
    end: dt.datetime,
    *,
    pad_seconds: float = 0.0,
    columns: Sequence[str] | None = None,
    time_column: str = "time_recorded",
    schema: str = "telemetry",
    limit: int | None = None,
):
    """Rows from schema.table between start and end (inclusive), widened by pad_seconds.

    Returns a pandas DataFrame ordered by time_column ascending.
    """
    _validate_identifier(schema)
    _validate_identifier(table)
    _validate_identifier(time_column)
    col_sql = _build_column_sql(columns)

    pad = dt.timedelta(seconds=pad_seconds)
    window_start = start - pad
    window_end = end + pad

    query = db.sql_text(
        "SELECT {cols} FROM {schema}.{table} WHERE {time_col} BETWEEN %s AND %s "
        "ORDER BY {time_col} ASC"
    ).format(
        cols=col_sql,
        schema=db.identifier(schema),
        table=db.identifier(table),
        time_col=db.identifier(time_column),
    )
    if limit is not None:
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(f"limit must be a positive int, got {limit!r}")
        query = db.sql_text("{q} LIMIT {n}").format(q=query, n=db.sql_text(str(limit)))

    return db.fetch_df(config, query, (window_start, window_end))


def query_nearest(
    config: Config,
    table: str,
    when: dt.datetime,
    *,
    columns: Sequence[str] | None = None,
    time_column: str = "time_recorded",
    schema: str = "telemetry",
    max_delta_seconds: float | None = None,
) -> dict | None:
    """The single row of schema.table closest to `when` in time.

    Runs two bounded, index-friendly queries -- nearest row at-or-before
    `when`, and nearest row at-or-after -- rather than scanning a window and
    sorting by distance; both halves use time_column's index (verified via
    EXPLAIN against a real telemetry table: 'Index Only Scan', not a
    sequential scan). This is the standard shape for attaching a pure
    time-series table (no per-exposure key) to an exposure: "the value
    recorded closest to the exposure's start time".

    Returns None if the table has no rows at all, or if the nearest row is
    farther than max_delta_seconds away (when given). The result dict always
    includes 'delta_seconds': how many seconds after `when` the row's
    time_column falls (negative if the row is from before `when`).
    """
    _validate_identifier(schema)
    _validate_identifier(table)
    _validate_identifier(time_column)
    col_sql = _build_column_sql(columns, require=time_column)

    schema_id = db.identifier(schema)
    table_id = db.identifier(table)
    time_col_id = db.identifier(time_column)

    before_query = db.sql_text(
        "SELECT {cols} FROM {schema}.{table} WHERE {time_col} <= %s ORDER BY {time_col} DESC LIMIT 1"
    ).format(cols=col_sql, schema=schema_id, table=table_id, time_col=time_col_id)
    after_query = db.sql_text(
        "SELECT {cols} FROM {schema}.{table} WHERE {time_col} >= %s ORDER BY {time_col} ASC LIMIT 1"
    ).format(cols=col_sql, schema=schema_id, table=table_id, time_col=time_col_id)

    before = db.fetch_one(config, before_query, (when,))
    after = db.fetch_one(config, after_query, (when,))

    best_row = None
    best_delta = None
    for row in (before, after):
        if row is None:
            continue
        delta = (row[time_column] - when).total_seconds()
        if best_delta is None or abs(delta) < abs(best_delta):
            best_delta = delta
            best_row = row

    if best_row is None:
        return None
    if max_delta_seconds is not None and abs(best_delta) > max_delta_seconds:
        return None

    result = dict(best_row)
    result["delta_seconds"] = best_delta
    return result


@dataclass(frozen=True)
class TelemetryField:
    """One named telemetry lookup an Exposure can run on demand.

    `kind='nearest'` (default) uses query_nearest against the exposure's
    start or end time (`when`); `kind='window'` uses query_window across the
    exposure's full time span (widened by `pad_seconds`).

    Attach a list of these dynamically via `Exposure(expid, telemetry_fields=[...])`,
    or register process-wide defaults once by appending to
    DEFAULT_TELEMETRY_FIELDS -- either way, nothing is queried until
    `Exposure.telemetry_field(name)` is actually called, so having many
    fields configured costs nothing until they're used.
    """

    name: str
    table: str
    kind: str = "nearest"
    columns: Sequence[str] | None = None
    time_column: str = "time_recorded"
    schema: str = "telemetry"
    when: str = "start"  # 'nearest' kind only: 'start' or 'end'
    pad_seconds: float = 0.0  # 'window' kind only
    max_delta_seconds: float | None = None  # 'nearest' kind only

    def __post_init__(self):
        if self.kind not in ("nearest", "window"):
            raise ValueError(f"kind must be 'nearest' or 'window', got {self.kind!r}")
        if self.when not in ("start", "end"):
            raise ValueError(f"when must be 'start' or 'end', got {self.when!r}")


DEFAULT_TELEMETRY_FIELDS: list[TelemetryField] = []
