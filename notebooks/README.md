# Notebooks

Companion analysis notebooks for `telemetry_mining`, each rewriting a real analysis
against the package. See each notebook's own intro cell for what it does and why.

## Importing `telemetry_mining`

None of the standard Jupyter kernels reliably have `telemetry_mining` importable --
it isn't installed anywhere central (see `API.md`'s "Installation / environment"
section for the full story: even the "DESI master" kernel only works via a
fragile, per-user, per-Python-version editable install). Every notebook here
starts with the same explicit `sys.path` bootstrap instead of relying on that:

```python
import sys
sys.path.insert(0, "/global/homes/k/klaushon/telemetry_mining/src")
from telemetry_mining import Exposure
```

Copy this into any new notebook before importing `telemetry_mining` -- don't
assume it'll just work from whatever kernel you happen to be using.

## Running headlessly (no live Jupyter session needed)

Useful for anything broad/slow -- e.g. a `select_exposures` query over a wide
`NIGHT_RANGE` (see `calibstars_linphi.ipynb`) -- since a live Jupyter session at
NERSC is subject to session time limits, and if the notebook is open in a browser
tab while this runs, Jupyter won't notice the file changed underneath it. Close
the notebook in your browser first if it's open, and don't save over it from the
browser until the run finishes.

```
source /global/common/software/desi/desi_environment.sh master
jupyter nbconvert --to notebook --execute --inplace notebooks/<name>.ipynb
```

This runs the notebook top to bottom as a plain Python process -- no live
kernel/browser connection involved, so no Jupyter-session timeout applies -- and
writes the executed notebook (printed output, matplotlib figures, everything)
back into the same `.ipynb` file. Open it normally in Jupyter afterward to see
the results.

Run it in the background (`... &`, or under `tmux`/`screen`) for anything that'll
take a while.
