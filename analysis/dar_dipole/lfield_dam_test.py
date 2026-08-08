"""L_field vs intra-exposure |Δairmass| -- the DAR analog of the mirror-ΔT L_see example
(from_mac_to_nersc.md, 2026-08-07 'Next example -- L_field vs intra-exposure |Δairmass|' entry).

Physical idea: L_field is built from the INTRA-EXPOSURE drift, so it should track how much airmass
CHANGES during the exposure (|Δairmass|, driven by transit proximity and exposure length), not just
the airmass level itself. Off-transit / long exposures at high airmass drift more, accumulating more
DAR loss -- an actionable scheduling lever, and a clean validation since L_field comes from GFA drift
while |Δairmass| comes from the ephemeris (independent quantities).

Built via the Exposure.L_field ATTRIBUTE (per Klaus/Mac), not the lower-level fiber_loss functions
directly, on the FULL exposure_pointing population (all airmass, not just am>1.4) -- this gives full
airmass coverage, unlike the precomputed am>1.4-only drift table used for the validation-preview
sanity check (see the memory / from_nersc_to_mac.md entry: the preview numbers reproduced exactly on
the am>1.4 subset before this full run).

|Δairmass| formula (Mac's spec, standard spherical-trig airmass from hour angle/dec/latitude):
  LAT = 31.9634 deg (Mayall latitude), SID = 15.041 arcsec/sec (sidereal rate)
  ha0 = mountha (deg), dec = skydec (deg), dHA = exptime * SID
  am(h) = 1 / (sin(LAT)sin(dec) + cos(LAT)cos(dec)cos(h))
  dam = |am(ha0+dHA) - am(ha0)|

Perf note: each Exposure(...).L_field call reads an ETC JSON + does a live affine fit (~69 ms/exposure
measured on this account's login-node container, which only exposes 1 CPU -- multiprocessing wouldn't
help here). ~28 min single-threaded for the full ~24.6k-exposure population; run this in the
background, it's not hung.
"""
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, '/global/u1/k/klaushon/telemetry_mining-trunk/src')
from telemetry_mining.config import Config
from telemetry_mining.exposure import Exposure

DATA_DIR = '/global/u1/k/klaushon/telemetry_mining-trunk/data'
LAT = np.deg2rad(31.9634)
SID = 15.041 / 3600.0  # deg/sec


def compute_dam(mountha, skydec, exptime):
    ha0 = np.deg2rad(mountha)
    dec = np.deg2rad(skydec)
    dHA = np.deg2rad(exptime * SID)

    def am(h):
        return 1.0 / (np.sin(LAT) * np.sin(dec) + np.cos(LAT) * np.cos(dec) * np.cos(h))

    return np.abs(am(ha0 + dHA) - am(ha0))


def main():
    cfg = Config.default()
    pt = pd.read_csv(f'{DATA_DIR}/dar_exposure_pointing.csv')
    pt['dam'] = compute_dam(pt.mountha.values, pt.skydec.values, pt.exptime.values)
    print(f'{len(pt)} exposures in the full pointing sample (all airmass)')

    t0 = time.time()
    l_see, l_field = [], []
    n = len(pt)
    for i, eid in enumerate(pt.EXPID):
        exp = Exposure(int(eid), config=cfg)
        l_see.append(exp.L_see)
        l_field.append(exp.L_field)
        if (i + 1) % 2000 == 0:
            elapsed = time.time() - t0
            print(f'  {i+1}/{n}  elapsed={elapsed:.0f}s  ~{elapsed/(i+1)*n:.0f}s total est.', flush=True)
    pt['L_see'] = l_see
    pt['L_field'] = l_field

    print(f'[done] {time.time()-t0:.0f}s total')
    print(f'L_see: {pt.L_see.notna().sum()}/{n}   L_field: {pt.L_field.notna().sum()}/{n}')

    out = f'{DATA_DIR}/dar_lfield_dam_full.parquet'
    pt.to_parquet(out)
    print(f'[out] {out}')


if __name__ == '__main__':
    main()
