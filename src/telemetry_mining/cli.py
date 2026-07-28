"""python -m telemetry_mining <expid> [<night>] -- print an exposure summary."""

from __future__ import annotations

import sys

from .exposure import Exposure


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: python -m telemetry_mining <expid> [<night>]", file=sys.stderr)
        return 2
    expid = int(argv[0])
    night = int(argv[1]) if len(argv) > 1 else None
    exp = Exposure(expid, night=night)
    for key, value in exp.summary().items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
