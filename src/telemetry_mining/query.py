"""Bulk exposure selection and per-exposure harvesting.

Two primitives for correlation studies across many exposures, so the same
loop over `Exposure` objects doesn't get hand-rolled every time:

- `select_exposures`: filter `exposure.exposure` with a raw SQL WHERE
  clause, then build one row per matching exposure. Column specs that only
  need `exposure.exposure` are free (pulled from the single bulk query
  already needed for the filter); anything else (a FITS header, the GFA
  summary, a telemetry lookup, ...) costs one touch per matching exposure.
- `harvest`: run a function per exposure across an explicit list of
  expids, collecting results either as `{expid: result}` (the default --
  for results that aren't row-comparable across exposures, like a guider
  time series of varying length) or, with `concat=True`, pooled into one
  DataFrame with an EXPID column (for per-fiber/per-petal tables you want
  to group/join across exposures).

Both batch-resolve `night` up front in a single query rather than paying
one DB round-trip per exposure just to resolve it (the one per-exposure
cost that's independent of what the caller actually wants) -- everything
past that is still one round-trip per exposure per data source touched,
since that can't be generically collapsed without knowing what's being
asked for. Column/value specs are either a plain `callable(Exposure)`, or
a dotted "source.path[index]" string -- see `resolve_spec`.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Mapping, Sequence, Union

from . import db
from .config import Config
from .exposure import Exposure

Spec = Union[str, Callable[[Exposure], Any]]


def _run_maybe_threaded(items: Sequence[Any], worker: Callable[[Any], Any], max_workers: int | None):
    """Run `worker(item)` for each item, sequentially or via a thread pool.

    Threads, not processes: the per-exposure cost this is meant to overlap
    (a DB round-trip, a FITS read, ...) is I/O-bound, and psycopg2 releases
    the GIL during a blocking network call -- unlike `Exposure.cframe_tables`'s
    process pool, needed there because `fitsio`'s C-level gzip decompression
    does not release the GIL (confirmed by testing, see exposure.py). Safe to
    share `Exposure`/`Config` objects read-only across threads this way
    because `db.py`'s connection cache is thread-local (2026-07-20) -- each
    pool thread gets its own DB connection, not a shared one.

    Preserves `items`' order in the returned list regardless of completion
    order (`ThreadPoolExecutor.map` guarantees this).

    `max_workers=None` means sequential (unlike `cframe_tables`, which picks
    a default worker count even when `None`) -- `harvest`/`select_exposures`
    already had established, widely-used default behavior before this option
    existed, so the default must stay backward-compatible. Also, each worker
    opens a real connection to the shared production replicator DB, unlike
    `cframe_tables`'s workers (each just reads a local file) -- auto-scaling
    that up without the caller opting in isn't appropriate here.
    """
    if not max_workers or max_workers <= 1 or len(items) <= 1:
        return [worker(item) for item in items]
    workers = min(max_workers, len(items))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(worker, items))

_TOKEN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)((?:\[[^\]]+\])*)$")
_INDEX_RE = re.compile(r"\[([^\]]+)\]")


def _apply_index(value, raw_index: str):
    raw_index = raw_index.strip()
    if len(raw_index) >= 2 and raw_index[0] in "'\"" and raw_index[-1] == raw_index[0]:
        return value[raw_index[1:-1]]
    return value[int(raw_index)]


def _get_member(value, name: str):
    """Look up `name` on `value`: mapping/sequence-style access first, attribute access as fallback.

    Covers plain dicts (headers, db_row, jsonb blobs), pandas Series
    (gfa_row), and plain attributes -- in that order, since the values a
    column spec walks through are almost always dict- or Series-shaped.
    """
    if isinstance(value, dict):
        return value[name]
    if hasattr(value, "__getitem__") and not isinstance(value, (str, bytes)):
        try:
            return value[name]
        except (KeyError, TypeError, IndexError):
            pass
    return getattr(value, name)


def _resolve_token(value, token: str):
    match = _TOKEN_RE.match(token)
    if not match:
        raise ValueError(f"Invalid column spec token: {token!r}")
    name, subscripts = match.groups()
    value = _get_member(value, name)
    for raw_index in _INDEX_RE.findall(subscripts):
        value = _apply_index(value, raw_index)
    return value


def resolve_spec(exp: Exposure, spec: Spec):
    """Resolve one column spec against an Exposure.

    `spec` is either a callable `(Exposure) -> value`, or a dotted path
    string naming an Exposure accessor and how to walk into it:

        "header.ETCFRACB"                    # dict key
        "gfa_row.FWHM_ASEC"                   # pandas Series member
        "telemetry.mirror_avg_temp"           # exp.telemetry_field('mirror_avg_temp')
        "db_row.hexapod['hex_trim'][2]"       # jsonb dict -> list -> index
        "header.HEXPOS[2]"                    # bracket indexing on the base value itself

    `[n]` indexes a list/array; `['key']`/`["key"]` indexes a dict. Anything
    that needs real parsing (e.g. HEXPOS is actually a comma-joined string
    in the header, not a real list) should be a callable instead -- this
    mini-language deliberately does not guess at implicit reinterpretation.
    """
    if callable(spec):
        return spec(exp)
    if not isinstance(spec, str):
        raise TypeError(f"Column spec must be a callable or a string, got {type(spec)!r}")

    tokens = spec.split(".")
    match = _TOKEN_RE.match(tokens[0])
    if not match:
        raise ValueError(f"Invalid column spec: {spec!r}")
    source_name, subscripts = match.groups()

    if source_name == "telemetry":
        if len(tokens) < 2:
            raise ValueError(f"'telemetry.<field_name>' spec is missing a field name: {spec!r}")
        field_match = _TOKEN_RE.match(tokens[1])
        if not field_match:
            raise ValueError(f"Invalid column spec token: {tokens[1]!r}")
        field_name, field_subscripts = field_match.groups()
        value = exp.telemetry_field(field_name)
        for raw_index in _INDEX_RE.findall(field_subscripts):
            value = _apply_index(value, raw_index)
        remaining = tokens[2:]
    else:
        value = getattr(exp, source_name)
        for raw_index in _INDEX_RE.findall(subscripts):
            value = _apply_index(value, raw_index)
        remaining = tokens[1:]

    for token in remaining:
        value = _resolve_token(value, token)
    return value


def _bulk_resolve_nights(expids: Sequence[int], config: Config) -> dict[int, int]:
    rows = db.fetch_all(
        config,
        "SELECT id, night FROM exposure.exposure WHERE id = ANY(%s)",
        (list(expids),),
    )
    return {int(row["id"]): int(row["night"]) for row in rows if row.get("night") is not None}


def select_exposures(
    where: str,
    columns: Mapping[str, Spec] | None = None,
    config: Config | None = None,
    params: Sequence[Any] | Mapping[str, Any] | None = None,
    order_by: str | None = "id",
    on_error: str = "raise",
    max_workers: int | None = None,
):
    """One row per exposure matching `where`, columns from `columns`.

    `where` is a raw SQL WHERE-clause fragment against `exposure.exposure`
    (parameterize any actual values via `params`, e.g.
    `where="night between %s and %s", params=(20260101, 20260701)"` --
    exactly like `telemetry_mining.db.fetch_all`). Required (no default) to
    avoid an accidental full-table scan.

    `columns` maps an output column name to a spec (see `resolve_spec`).
    Every matching row's full `exposure.exposure` columns are fetched by
    the one bulk query this function already needs for the WHERE filter,
    so a `"db_row.<column>"` spec costs nothing extra; specs touching any
    other source (header, gfa_row, telemetry, table_source, a callable)
    open/query that source once per matching exposure.

    `order_by` is a raw SQL `ORDER BY` fragment (default `"id"`, i.e.
    ascending EXPID) -- without it, SQL makes no row-order guarantee at
    all, and results come back in whatever order the query planner finds
    convenient (typically following whichever index served the `WHERE`,
    not EXPID). Pass `order_by=None` to skip ordering entirely (fine if you
    don't care and want to avoid an extra sort step), or e.g.
    `order_by="night, id"` for a different order.

    `on_error` controls what happens when resolving a spec fails for a given
    exposure (e.g. its FITS file has been purged -- a real, common gap, not
    an edge case: one bulk scan hit 28 missing files out of 831 exposures in
    a recent 6-week window):
    - `"raise"` (default): the first failure propagates immediately,
      unchanged from prior behavior -- filter your own expid list first if
      you expect gaps and want to fail fast.
    - `"skip"`: an exposure with a failing spec is left out of the result
      entirely (matches the skipped.append(exp)/continue pattern already
      used by hand throughout notebooks/ -- if *any* column fails for an
      exposure, the whole exposure is dropped, not just that one cell).
      What was skipped and why is recorded in the returned DataFrame's
      `.attrs["skipped"]` (a `{expid: exception}` dict, always present and
      just empty under `"raise"`) -- not printed. Report it yourself if you
      want: `print(f'{len(selection.attrs["skipped"])} skipped')`.

    `max_workers` (default `None`, i.e. sequential -- unchanged prior
    behavior) resolves each matching row's `columns` concurrently via a
    thread pool when set. Worth it once a spec costs a real per-exposure
    round-trip (a callable that queries `telemetry.guider_centroids` and
    fits a line, say) and there are enough matching exposures for the wait
    to matter -- a pure `"db_row.*"` selection is already one bulk query and
    gets no benefit. With `on_error="raise"`, an exception still propagates
    out of this call, but other in-flight lookups may finish first (threads
    already dispatched keep running) rather than stopping at the exact
    first failure the way the sequential path does.

    Returns a pandas DataFrame with an `EXPID`/`NIGHT` column plus one
    column per `columns` entry.
    """
    import pandas as pd

    if on_error not in ("raise", "skip"):
        raise ValueError(f"on_error must be 'raise' or 'skip', got {on_error!r}")

    config = config or Config.default()
    columns = columns or {}
    query = f"SELECT * FROM exposure.exposure WHERE {where}"
    if order_by:
        query += f" ORDER BY {order_by}"
    rows = db.fetch_all(config, query, params)

    def _resolve_row(row):
        expid = int(row["id"])
        night = int(row["night"]) if row.get("night") is not None else None
        exp = Exposure(expid, night=night, config=config)
        exp.__dict__["db_row"] = row  # already fetched above -- avoid a redundant per-exposure query
        record = {"EXPID": expid, "NIGHT": night}
        try:
            for out_name, spec in columns.items():
                record[out_name] = resolve_spec(exp, spec)
        except Exception as exc:
            if on_error == "raise":
                raise
            return None, (expid, exc)
        return record, None

    records = []
    skipped: dict[int, Exception] = {}
    for record, skip in _run_maybe_threaded(rows, _resolve_row, max_workers):
        if record is not None:
            records.append(record)
        else:
            expid, exc = skip
            skipped[expid] = exc

    result = pd.DataFrame(records)
    result.attrs["skipped"] = skipped
    return result


def harvest(
    expids: Sequence[int],
    fn: Callable[[Exposure], Any],
    config: Config | None = None,
    concat: bool = False,
    max_workers: int | None = None,
):
    """Run `fn(Exposure)` for each of `expids`, collecting the results.

    `night` for every expid is resolved in a single bulk query up front
    (rather than one round-trip per exposure just to resolve it) -- the one
    per-exposure cost `harvest` can remove without knowing what `fn` does.
    Whatever `fn` itself touches is still one round-trip per exposure per
    source; that's inherent, not something this function can batch away.

    With `concat=False` (default): returns `{expid: fn(Exposure(expid))}` --
    use this when results aren't row-comparable across exposures (e.g. a
    guider time series of varying length per exposure).

    With `concat=True`: `fn` must return a DataFrame; results are pooled
    into one DataFrame with an `EXPID` column inserted (a named index, if
    any, is preserved as a column first) -- use this for per-fiber/per-petal
    tables you want to group/join across exposures. Exposures where `fn`
    returned `None` are skipped.

    `max_workers` (default `None`, i.e. sequential -- unchanged prior
    behavior) runs `fn` for different expids concurrently via a thread pool
    when set -- see `select_exposures`'s `max_workers` docstring for why
    threads (not processes) and why the default stays sequential.
    """
    import pandas as pd

    config = config or Config.default()
    expids = [int(e) for e in expids]
    if not expids:
        return pd.DataFrame() if concat else {}

    nights = _bulk_resolve_nights(expids, config)

    def _run_one(expid):
        return expid, fn(Exposure(expid, night=nights.get(expid), config=config))

    results = dict(_run_maybe_threaded(expids, _run_one, max_workers))

    if not concat:
        return results

    frames = []
    for expid, result in results.items():
        if result is None:
            continue
        has_named_index = result.index.name is not None or any(
            name is not None for name in getattr(result.index, "names", [])
        )
        frame = result.reset_index() if has_named_index else result.copy()
        frame.insert(0, "EXPID", expid)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
