"""Global search over the `alarms.alarms` table.

`Exposure.alarms()` answers *"what alarms fired during this exposure"*; `find_alarms`
answers the complementary global question *"every alarm matching these filters, across
the whole log"* — e.g. `find_alarms(alarm_id=9200)` to pull one alarm type over the
years. Column names are validated against an identifier pattern; all filter *values* are
parameterized (`%s`), never string-interpolated.
"""

from __future__ import annotations

from typing import Any, Sequence

from . import db
from .config import Config
from .telemetry import _validate_identifier


def find_alarms(
    config: Config | None = None,
    *,
    alarm_id: int | None = None,
    level: str | Sequence[str] | None = None,
    component: str | None = None,
    since=None,
    until=None,
    message_like: str | None = None,
    columns: Sequence[str] | None = None,
    limit: int | None = None,
):
    """Alarms from `alarms.alarms` matching the given filters, ordered by `time_recorded`.

    All filters are optional and ANDed together:

    - `alarm_id` — the alarm *type* id (distinct from the row primary key `id`).
    - `level` — a severity string, or a list of them (`CRITICAL`/`ALERT`/`WARNING`/`EVENT`).
    - `component` — the raising subsystem/component.
    - `since` / `until` — tz-aware datetimes bounding `time_recorded` (inclusive).
    - `message_like` — a SQL `LIKE` pattern on the message text.
    - `columns` — which columns to return (default all); each validated against an
      identifier pattern.
    - `limit` — cap the number of rows.

    Returns a pandas DataFrame ordered by `time_recorded` ascending.
    """
    config = config or Config.default()
    cols = ", ".join(_validate_identifier(c) for c in columns) if columns else "*"

    conds: list[str] = []
    params: list[Any] = []
    if alarm_id is not None:
        conds.append("alarm_id = %s")
        params.append(int(alarm_id))
    if level is not None:
        if isinstance(level, str):
            conds.append("level = %s")
            params.append(level)
        else:
            conds.append("level = ANY(%s)")
            params.append(list(level))
    if component is not None:
        conds.append("component = %s")
        params.append(component)
    if since is not None:
        conds.append("time_recorded >= %s")
        params.append(since)
    if until is not None:
        conds.append("time_recorded <= %s")
        params.append(until)
    if message_like is not None:
        conds.append("message LIKE %s")
        params.append(message_like)

    query = f"SELECT {cols} FROM alarms.alarms"
    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += " ORDER BY time_recorded ASC"
    if limit is not None:
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(f"limit must be a positive int, got {limit!r}")
        query += f" LIMIT {int(limit)}"

    return db.fetch_df(config, query, params or None)
