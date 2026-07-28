"""Loader for etc-<expid>.json (Exposure Time Calculator summary) files.

The file is a nested JSON: scalar summary blocks (``expinfo``, ``fassign``,
``header``) plus several time-series blocks (``shutter``, ``thru``, ``sky``,
``accum``) whose entries are parallel lists, occasionally alongside a scalar
like ``mjd0``.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_etc(path: Path) -> dict:
    """Parse the full etc-<expid>.json file."""
    with open(path) as f:
        return json.load(f)


def etc_summary(etc: dict) -> dict:
    """The scalar 'header' block (ETCTEFF, ETCREAL, ETCTRANS, ETCSKY, ...)."""
    return etc.get("header", {})


def etc_timeseries(etc: dict, key: str):
    """Turn a time-series block (e.g. 'shutter', 'thru', 'sky', 'accum') into a DataFrame.

    List-valued entries become columns; any scalar entries in the same block
    (e.g. 'mjd0') are attached as DataFrame.attrs rather than dropped, since
    the required behavior varies with which block is loaded.
    """
    import pandas as pd

    block = etc.get(key)
    if block is None:
        raise KeyError(f"No {key!r} block in ETC data (available: {sorted(etc.keys())})")
    list_cols = {k: v for k, v in block.items() if isinstance(v, list)}
    scalar_cols = {k: v for k, v in block.items() if not isinstance(v, list)}
    df = pd.DataFrame(list_cols)
    df.attrs.update(scalar_cols)
    return df
