"""Shared dipole/quadrupole affine-fit machinery, factored out of `fit_dipole_quadrupole.py` so
later tests (e.g. `flat_to_psf_dipole_test.py`) reuse the exact validated logic instead of
retyping it -- this investigation has been bitten by retyped-fit-logic bugs before.

Model: y_i (per star, per exposure) ~ radial + fixed-dipole(X,Y) + rotating-dipole(up,vp) +
fixed-quadrupole(X^2-Y^2, 2XY) + rotating-quadrupole(up^2-vp^2, 2*up*vp), fit jointly after
per-exposure demeaning of both y and the design columns (so any per-exposure absolute-level
offset -- e.g. RCALIBFRAC's own median-normalization -- is automatically absorbed and doesn't
bias the spatial terms). up/vp are the position rotated into the zenith frame by the exposure's
parallactic angle q: up = X*cos(q)+Y*sin(q), vp = -X*sin(q)+Y*cos(q).
"""
import numpy as np
import pandas as pd

NAMES = ['rad', 'fdipx', 'fdipy', 'rdipx', 'rdipy', 'fq1', 'fq2', 'rq1', 'rq2']


def design_matrix(X, Y, q):
    u, v = X, Y
    c, s = np.cos(q), np.sin(q)
    up, vp = u * c + v * s, -u * s + v * c
    cols = {
        'rad': u * u + v * v,
        'fdipx': u, 'fdipy': v,
        'rdipx': up, 'rdipy': vp,
        'fq1': u * u - v * v, 'fq2': 2 * u * v,
        'rq1': up * up - vp * vp, 'rq2': 2 * up * vp,
    }
    return np.column_stack([cols[k] for k in NAMES])


def within_demean(M, y, eid):
    dfm = pd.DataFrame(M, columns=NAMES)
    dfm['y'] = y
    dfm['e'] = eid
    gm = dfm.groupby('e')[NAMES + ['y']].transform('mean')
    Xd = (dfm[NAMES] - gm[NAMES]).values
    yd = (dfm['y'] - gm['y']).values
    return Xd, yd, eid


def per_exp_normal(Xd, yd, e):
    order = np.argsort(e, kind='stable')
    Xd, yd, e = Xd[order], yd[order], e[order]
    uniq, start = np.unique(e, return_index=True)
    ends = np.r_[start[1:], len(e)]
    p = Xd.shape[1]
    XtX = np.empty((len(uniq), p, p))
    Xty = np.empty((len(uniq), p))
    yty = np.empty(len(uniq))
    for i, (a, b) in enumerate(zip(start, ends)):
        Xi, yi = Xd[a:b], yd[a:b]
        XtX[i] = Xi.T @ Xi
        Xty[i] = Xi.T @ yi
        yty[i] = yi @ yi
    return XtX, Xty, yty, uniq


def solve(XtX, Xty):
    A, b = XtX.sum(0), Xty.sum(0)
    return np.linalg.solve(A, b)


def amps(beta):
    d = dict(zip(NAMES, beta))
    return (np.hypot(d['rdipx'], d['rdipy']), np.hypot(d['rq1'], d['rq2']),
            np.hypot(d['fdipx'], d['fdipy']), np.hypot(d['fq1'], d['fq2']))


def fit_and_bootstrap(X, Y, q, y, eid, n_boot=300, seed=0):
    """Full pipeline: design matrix -> within-exposure demean -> per-exposure normal eqs ->
    joint solve -> exposure-level bootstrap. Returns dict with point estimates, R^2, n_exp,
    n_star, and bootstrap 16/50/84 percentiles for D_rot, Q_rot, D_fix, Q_fix."""
    M = design_matrix(X, Y, q)
    Xd, yd, e = within_demean(M, y, eid)
    XtX, Xty, yty, uniq = per_exp_normal(Xd, yd, e)
    beta = solve(XtX, Xty)
    Drot, Qrot, Dfix, Qfix = amps(beta)
    ss_tot = yty.sum()
    A, b = XtX.sum(0), Xty.sum(0)
    r2 = 1 - (ss_tot - beta @ b) / ss_tot

    rng = np.random.default_rng(seed)
    n = len(uniq)
    boots = {'D_rot': [], 'Q_rot': [], 'D_fix': [], 'Q_fix': []}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        bt = solve(XtX[idx], Xty[idx])
        dr, qr, df_, qf = amps(bt)
        boots['D_rot'].append(dr)
        boots['Q_rot'].append(qr)
        boots['D_fix'].append(df_)
        boots['Q_fix'].append(qf)

    out = dict(n_exp=n, n_star=len(y), R2=r2, D_rot=Drot, Q_rot=Qrot, D_fix=Dfix, Q_fix=Qfix, beta=beta)
    for k, v in boots.items():
        lo, med, hi = np.percentile(v, [16, 50, 84])
        out[f'{k}_ci'] = (lo, hi)
    return out
