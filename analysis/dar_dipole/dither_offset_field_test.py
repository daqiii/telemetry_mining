"""Independent-of-RCALIBFRAC test of whether D_rot is physically real (Mac Claude proposal):
fit the SAME 6-parameter affine decomposition (translation=dipole, rotation+scale+shear=
quadrupole-equivalent) used throughout this investigation's Test 4/5/6 work, but on the
per-star R-camera dither-fit offset field from Segev BenZvi's dither sequences
(`dither-<date>-<expid>-R.fits`) -- a completely different data source and measurement
technique (geometric flux-vs-dither-position fitting, not a flux-ratio/model-comparison
construction like RCALIBFRAC).

Per exposure: dRA_i = (fiber_ditherfit_ra_i - target_ra_i)*cos(dec)*3600 [arcsec], similarly
dDec_i, paired with that exposure's own xfocal_i/yfocal_i (per-star focal-plane position,
genuinely varies per exposure due to the known commanded dither pattern). Validated on one
exposure before scaling: re-derived translation (tx,ty) matches the file's own xtel/ytel to
~0.006", condition number 1.46 (2535 stars/exposure, far better constrained than the ~20-30
PMGSTARS guide stars used in Test 6).

Prerequisite confirmed from the dither paper (arXiv:2403.05688) text: dither exposures are
taken with guiding ON for the full 3 minutes "to allow the telescope tracking and guiding to
fully engage" and to match normal observing -- so the fitted per-exposure translation is
genuinely the guide-loop residual, the D_rot-relevant quantity, not an uncorrected pointing
error the guider would otherwise remove.

Translation (dipole) decomposed into zenith-tied/fixed via the same q-rotation as
fit_dipole_quadrupole.py; shear (e1,e2, quadrupole-equivalent) decomposed via 2q (spin-2)
the same way as pmgstars_quadrupole_test.py. Compare directly to D_rot/Q_rot -- no sigma_eff
or platescale conversion needed, since this is a direct astrometric measurement in arcsec.
"""
import glob
import os
import re
import sys

import fitsio
import numpy as np
import pandas as pd

sys.path.insert(0, '/global/u1/k/klaushon/telemetry_mining-trunk/src')
from telemetry_mining import db
from telemetry_mining.config import Config

ROOT = '/global/cfs/cdirs/desi/users/sybenzvi/dither'
FIELD_R = 410.0  # mm, same normalization as elsewhere in this investigation


def pick_r_file(night):
    d = os.path.join(ROOT, night)
    files = os.listdir(d)
    cands = [f for f in files if re.match(rf'^dither-{night}-\d+.*-R\.fits$', f)]
    redux = [f for f in cands if 'redux' in f]
    data = [f for f in cands if 'data' in f and 'redux' not in f]
    plain = [f for f in cands if 'data' not in f and 'redux' not in f]
    chosen = redux or data or plain
    return os.path.join(d, chosen[0]) if chosen else None


def fit_sequence(path):
    # FIX (2026-08-05): fiber_ditherfit_ra/dec were confirmed from the real
    # solvedither.py source (github.com/desihub/desicmx/analysis/dither) to be
    # DEFINED as target_ra + (delta_x_arcsec + xfiboff + xtel), i.e.
    # (fiber_ditherfit_ra - target_ra) is NOT a residual -- it's contaminated by
    # delta_x_arcsec, the deliberately-commanded per-star per-exposure dither
    # offset (the whole point of the dither technique, by-design varying, and
    # NOT astrophysical signal). Use xfiboff+xtel / yfiboff+ytel directly instead
    # -- both are already separate arcsec-valued columns, no reconstruction
    # needed, and the source confirms the model has no DAR/refraction term to
    # worry about pre-subtracting.
    ext1 = fitsio.read(path, ext=1, columns=['xfiboff', 'yfiboff', 'xtel', 'ytel', 'expid'])
    ext2 = fitsio.read(path, ext=2, columns=['target_ra', 'target_dec', 'xfocal', 'yfocal'])
    n_exp = ext1['expid'].shape[1]
    results = []
    for i in range(n_exp):
        dra = ext1['xfiboff'][:, i] + ext1['xtel'][:, i]
        ddec = ext1['yfiboff'][:, i] + ext1['ytel'][:, i]
        xfocal = ext2['xfocal'][:, i]
        yfocal = ext2['yfocal'][:, i]
        expid = int(ext1['expid'][0, i])

        good = np.isfinite(dra) & np.isfinite(ddec) & np.isfinite(xfocal) & np.isfinite(yfocal)
        dra, ddec, xfocal_g, yfocal_g = dra[good], ddec[good], xfocal[good], yfocal[good]
        n = len(dra)
        if n < 50:
            continue
        X = xfocal_g / FIELD_R
        Y = yfocal_g / FIELD_R
        rows = []
        for xi, yi in zip(X, Y):
            rows.append([1, 0, xi, -yi, xi, yi])
            rows.append([0, 1, yi, xi, -yi, xi])
        A = np.array(rows, dtype=float)
        b = np.empty(2 * n)
        b[0::2] = dra
        b[1::2] = ddec
        try:
            params, *_ = np.linalg.lstsq(A, b, rcond=None)
        except Exception:
            continue
        resid = A @ params - b
        tx, ty, s, theta, e1, e2 = params
        results.append(dict(
            expid=expid, n_stars=n, tx=tx, ty=ty, scale=s, theta=theta, e1=e1, e2=e2,
            resid_rms=np.sqrt(np.mean(resid ** 2)), cond=np.linalg.cond(A),
        ))
    return results


def main():
    cfg = Config.default()
    nights = sorted(n for n in os.listdir(ROOT) if re.match(r'^\d{8}$', n))
    all_results = []
    for night in nights:
        path = pick_r_file(night)
        if path is None:
            print(f'{night}: no R file found, skip')
            continue
        try:
            res = fit_sequence(path)
        except Exception as e:
            print(f'{night}: error {e}')
            continue
        for r in res:
            r['night'] = night
        all_results.extend(res)
        print(f'{night}: {len(res)} exposures fit')

    df = pd.DataFrame(all_results)
    print(f'\ntotal: {len(df)} exposures across {df.night.nunique()} nights')

    expids = df.expid.tolist()
    rows = db.fetch_all(cfg, "SELECT id, airmass, parallactic FROM exposure.exposure WHERE id = ANY(%s)",
                         (expids,))
    meta = pd.DataFrame(rows).rename(columns={'id': 'expid'})
    df = df.merge(meta, on='expid', how='left')
    print(f'matched airmass/parallactic: {df.airmass.notna().sum()}/{len(df)}')

    out = '/global/u1/k/klaushon/telemetry_mining-trunk/data/dar_dither_offset_field.parquet'
    df.to_parquet(out)
    print(f'[out] {out}')


if __name__ == '__main__':
    main()
