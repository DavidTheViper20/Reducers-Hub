# Gerotor / Trochoidal Pump
#
# Internal positive-displacement pump and the geometric cousin of the cycloidal
# drive: the inner rotor has N lobes, the outer rotor has exactly N+1 circular
# teeth, and they co-rotate about offset centres so sealed chambers expand and
# contract. The inner rotor profile is generated here as the exact inner
# envelope of the outer circular teeth, so the pair always seals.
#
# Speed relationship: omega_inner / omega_outer = (N+1) / N.

from __future__ import annotations

import numpy as np

from novel_demo_common import MechanismDemo, Param, path, circles, dot

_CACHE: dict = {}


def _rot(x, y, a):
    c, s = np.cos(a), np.sin(a)
    return x * c - y * s, x * s + y * c


def _inner_profile(N, e, Rc, Rt, samples=720, steps=240):
    """Inner rotor boundary as the inner envelope of the N+1 outer teeth.

    Returns the profile in the inner rotor's own frame at zero rotation.
    """
    key = (N, round(e, 4), round(Rc, 4), round(Rt, 4))
    if key in _CACHE:
        return _CACHE[key]

    No = N + 1
    alpha = np.linspace(0.0, 2 * np.pi, samples)
    ux, uy = np.cos(alpha), np.sin(alpha)
    rho = np.full(samples, np.inf)

    for m in range(steps):
        phi = 2 * np.pi * m / steps          # inner rotation (world)
        psi = phi * N / No                   # outer rotation (world)
        # Outer centre O2 = (e, 0) in world; in the inner frame (rotated -phi):
        o2x, o2y = _rot(e, 0.0, -phi)
        for k in range(No):
            ang = 2 * np.pi * k / No + psi
            twx, twy = e + Rc * np.cos(ang), Rc * np.sin(ang)   # tooth centre, world
            cx, cy = _rot(twx, twy, -phi)                        # into inner frame
            # nearest intersection of ray (u) from origin with circle (c, Rt)
            b = ux * cx + uy * cy
            disc = b * b - (cx * cx + cy * cy - Rt * Rt)
            valid = disc >= 0
            t = np.full(samples, np.inf)
            sq = np.sqrt(np.where(valid, disc, 0.0))
            t_hit = b - sq
            t = np.where(valid & (t_hit > 0), t_hit, np.inf)
            rho = np.minimum(rho, t)

    finite = np.isfinite(rho)
    if not finite.all():                       # fill any gaps by interpolation
        rho = np.interp(alpha, alpha[finite], rho[finite], period=2 * np.pi)

    x = rho * ux
    y = rho * uy
    _CACHE[key] = (x, y)
    return x, y


def compute(v, phase):
    N = max(int(v["N"]), 2)
    e = v["e"]
    Rc = v["Rc"]
    Rt = v["Rt"]
    No = N + 1

    phi = phase                       # inner rotor rotation
    psi = phi * N / No                # outer rotor rotation

    items = []

    # Outer rotor: N+1 circular teeth about O2 = (e, 0), plus the bounding ring
    tooth_centers = []
    for k in range(No):
        ang = 2 * np.pi * k / No + psi
        tooth_centers.append((e + Rc * np.cos(ang), Rc * np.sin(ang)))
    ring_t = np.linspace(0, 2 * np.pi, 240)
    items.append(path(e + (Rc + Rt) * np.cos(ring_t), (Rc + Rt) * np.sin(ring_t),
                      color="#1f77b4", lw=1.6, closed=False, dxf_layer="OUTER_RING"))
    items.append(circles(tooth_centers, Rt, color="#1f77b4", lw=1.4, dxf_layer="OUTER_TEETH"))

    # Inner rotor: envelope profile rotated by phi about O1 (origin)
    ix, iy = _inner_profile(N, e, Rc, Rt)
    rx, ry = _rot(ix, iy, phi)
    items.append(path(rx, ry, color="#2ca02c", lw=2.0, closed=True, dxf_layer="INNER_ROTOR"))

    # Centre markers
    items.append(dot(0.0, 0.0, color="#2ca02c", ms=5))
    items.append(dot(e, 0.0, color="#1f77b4", ms=5))
    return items


def readout(v, phase):
    N = max(int(v["N"]), 2)
    return (f"Inner lobes N={N}   Outer teeth N+1={N + 1}   "
            f"Speed ratio omega_in/omega_out = {N + 1}/{N} = {(N + 1) / N:.4f}")


PARAMS = [
    Param("N", "Inner Lobes (N)", 3, 12, 6, step=1, integer=True, fmt="%0.0f"),
    Param("e", "Eccentricity", 1.0, 8.0, 4.0, step=0.1),
    Param("Rc", "Tooth-Center Radius", 10.0, 60.0, 34.0, step=0.5),
    Param("Rt", "Tooth Radius", 3.0, 18.0, 8.0, step=0.1),
]

demo = MechanismDemo(
    title="Gerotor / Trochoidal Pump",
    subtitle="Inner N-lobe rotor enveloping N+1 outer circular teeth. The geometric cousin of the cycloidal drive.",
    params=PARAMS,
    compute=compute,
    readout=readout,
    export_name="gerotor-pump",
)

_has_custom_layout = True
demo.build()
fig = demo.fig

if __name__ == "__main__":
    demo.show()
