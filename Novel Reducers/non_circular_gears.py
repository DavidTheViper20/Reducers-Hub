# Non-Circular (Elliptical) Gears — variable-ratio drive
#
# A matched pair of identical ellipses, each pinned at a focus, rolling without
# slipping. A classic theorem: two identical ellipses rolling about their foci
# keep a constant centre distance C = 2a, so they mesh perfectly while the
# instantaneous ratio swings through the cycle.
#
#   Pitch curve (focus-polar):   r(theta) = a(1 - e^2) / (1 + e*cos theta)
#   Contact pitch radii:         p1 + p2 = C = 2a   (always)
#   Instantaneous ratio:         i = p1 / p2 = p1 / (2a - p1)
#   Follower body rotation:      Phi2(phi1) = -integral_0^phi1 p1/(2a - p1) dphi
#
# Over one driver revolution the follower also turns exactly once (mean ratio 1),
# so the pair closes. Extremes of the ratio are (1+e)/(1-e) and its reciprocal.

from __future__ import annotations

import numpy as np

from novel_demo_common import MechanismDemo, Param, path, dot, segment

_GRID = np.linspace(0.0, 2 * np.pi, 1441)
_CACHE: dict = {}


def _rot(x, y, a):
    c, s = np.cos(a), np.sin(a)
    return x * c - y * s, x * s + y * c


def _pitch(theta, a, e):
    return a * (1.0 - e * e) / (1.0 + e * np.cos(theta))


def _follower_integral(a, e):
    """Cumulative integral of p1/(2a - p1) over [0, 2pi] on _GRID (cached)."""
    key = (round(a, 4), round(e, 4))
    if key in _CACHE:
        return _CACHE[key]
    p1 = _pitch(_GRID, a, e)
    integrand = p1 / (2.0 * a - p1)
    cum = np.concatenate(([0.0], np.cumsum(0.5 * (integrand[1:] + integrand[:-1]) * np.diff(_GRID))))
    _CACHE[key] = cum
    return cum


def _follower_rotation(phi1, a, e):
    cum = _follower_integral(a, e)
    total = cum[-1]                         # ~= 2*pi for identical ellipses
    n_full, frac = divmod(phi1, 2.0 * np.pi)
    return -(n_full * total + np.interp(frac, _GRID, cum))


def compute(v, phase):
    a = v["a"]
    e = float(np.clip(v["ecc"], 0.02, 0.7))
    C = 2.0 * a
    phi1 = phase

    items = []
    theta = _GRID

    # Driver gear (focus at origin O1), rotated by phi1
    r1 = _pitch(theta, a, e)
    lx, ly = r1 * np.cos(theta), r1 * np.sin(theta)
    dx, dy = _rot(lx, ly, phi1)
    items.append(path(dx, dy, color="#1f77b4", lw=2.0, closed=True, dxf_layer="DRIVER_PITCH"))

    # Follower gear (focus at O2=(C,0)), rotated by Phi2 (opposite sense)
    phi2 = _follower_rotation(phi1, a, e)
    fx0, fy0 = _rot(lx, ly, phi2)
    items.append(path(C + fx0, fy0, color="#2ca02c", lw=2.0, closed=True, dxf_layer="FOLLOWER_PITCH"))

    # Contact point on the line of centres
    p1_contact = _pitch(-phi1, a, e)        # driver pitch radius pointing toward O2
    items.append(dot(p1_contact, 0.0, color="#d62728", ms=7))

    # Centre spokes (show the differing rotation rates) + hub dots
    sp_d = _rot(0.9 * a, 0.0, phi1)
    items.append(segment((0, 0), sp_d, color="#1f77b4", lw=1.4))
    sp_f = _rot(0.9 * a, 0.0, phi2)
    items.append(segment((C, 0), (C + sp_f[0], sp_f[1]), color="#2ca02c", lw=1.4))
    items.append(dot(0.0, 0.0, color="#1f77b4", ms=5))
    items.append(dot(C, 0.0, color="#2ca02c", ms=5))
    return items


def readout(v, phase):
    a = v["a"]
    e = float(np.clip(v["ecc"], 0.02, 0.7))
    p1 = _pitch(-phase, a, e)
    i_now = p1 / (2.0 * a - p1)
    i_max = (1.0 + e) / (1.0 - e)
    return (f"Ellipse e={e:.2f}   center dist C=2a={2 * a:.1f}   "
            f"instant ratio i={i_now:.3f}   swings {1 / i_max:.3f}..{i_max:.3f}  (mean 1.000)")


PARAMS = [
    Param("a", "Semi-Major Axis (a)", 12.0, 45.0, 25.0, step=0.5),
    Param("ecc", "Ellipse Eccentricity", 0.05, 0.65, 0.35, step=0.01),
]

demo = MechanismDemo(
    title="Non-Circular (Elliptical) Gears",
    subtitle="Twin identical ellipses rolling about their foci — a continuously varying ratio with a constant center distance C = 2a.",
    params=PARAMS,
    compute=compute,
    readout=readout,
    export_name="elliptical-gears",
)

_has_custom_layout = True
demo.build()
fig = demo.fig

if __name__ == "__main__":
    demo.show()
