"""Verify `original_rot_rate.dfieldrotdt` is bit-for-bit identical to the
real `desimeter.fieldmodel.dfieldrotdt`, across a wide grid of inputs plus
edge cases (Dec=+-90, HA wrap-around, the +-1.5 arcsec/min saturation clip).

Requires a `desimeter` checkout on the path (only needed to run this
comparison -- `original_rot_rate.py` itself has no such dependency).
Usage: python compare_rot_rate_models.py /path/to/desimeter-main/py
"""

import itertools
import sys

import numpy as np

from original_rot_rate import dfieldrotdt as standalone_dfieldrotdt


def main(desimeter_py_path):
    sys.path.insert(0, desimeter_py_path)
    from desimeter.fieldmodel import dfieldrotdt as desimeter_dfieldrotdt

    mjd = 60000.0  # arbitrary -- both functions ignore it

    # 1) scalar-by-scalar comparison over a grid spanning the full domain
    ra_vals = np.arange(0, 360, 30.0)
    dec_vals = np.array([-89, -60, -30, 0, 30, 60, 89], dtype=float)
    lst_vals = np.arange(0, 360, 45.0)

    max_diff = 0.0
    n = 0
    for ra, dec, lst in itertools.product(ra_vals, dec_vals, lst_vals):
        a = desimeter_dfieldrotdt(ra, dec, mjd, lst)
        b = standalone_dfieldrotdt(ra, dec, mjd, lst)
        max_diff = max(max_diff, abs(a - b))
        n += 1
    print(f"Scalar grid: {n} combinations, max abs difference = {max_diff:.3e}")
    assert max_diff == 0.0, "standalone reimplementation diverged from desimeter"

    # 2) vectorized array-input comparison
    rng_ra, rng_dec, rng_lst = np.random.RandomState(0), np.random.RandomState(1), np.random.RandomState(2)
    ra_arr = rng_ra.uniform(0, 360, 2000)
    dec_arr = rng_dec.uniform(-89, 89, 2000)
    lst_arr = rng_lst.uniform(0, 360, 2000)
    mjd_arr = np.full(2000, mjd)

    a_arr = np.asarray(desimeter_dfieldrotdt(ra_arr, dec_arr, mjd_arr, lst_arr))
    b_arr = np.asarray(standalone_dfieldrotdt(ra_arr, dec_arr, mjd_arr, lst_arr))
    print(f"Array comparison (n=2000 random points): exactly equal = {np.array_equal(a_arr, b_arr)}")
    assert np.array_equal(a_arr, b_arr)

    # 3) edge cases: Dec near +-90, HA wrap boundary at exactly 180, saturation clip
    edge_cases = [(0, 90, 0), (0, -90, 0), (350, 0, 10), (10, 0, 350), (0, 0, 180), (0, 0, 180.0001)]
    for ra, dec, lst in edge_cases:
        a = desimeter_dfieldrotdt(ra, dec, mjd, lst)
        b = standalone_dfieldrotdt(ra, dec, mjd, lst)
        print(f"  ra={ra:>7} dec={dec:>5} lst={lst:>10}: desimeter={a:.6f} standalone={b:.6f} diff={abs(a - b):.2e}")
        assert a == b

    print("\nAll checks passed -- standalone reimplementation is bit-for-bit identical to desimeter's.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
