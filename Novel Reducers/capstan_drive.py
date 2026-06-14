# Capstan / Cable (Tendon) Drive
#
# A small input sheave drives a larger output pulley through a wrapped cable
# (tendon). Two distinct relationships govern such a drive and are commonly
# conflated:
#
#   * Kinematic reduction (pure rolling, no slip):
#         omega_in / omega_out = R_out / r_in
#     so the output turns slower by the radius ratio.
#
#   * Capstan grip (Euler / Eytelwein) — the holding-vs-load tension ratio that
#     the wrap provides through friction, NOT a speed ratio:
#         T2 / T1 = exp(mu * theta_wrap),  theta_wrap = wraps * 2*pi
#
# The cable is drawn as the two external tangents between the sheave and pulley.

from __future__ import annotations

import numpy as np

from novel_demo_common import MechanismDemo, Param, path, circles, dot, segment

_CIRCLE_T = np.linspace(0.0, 2.0 * np.pi, 200)


def _external_tangent_points(c1, r1, c2, r2):
    """External tangent contact points for two circles (same-side tangents).

    Returns ((p1a, p2a), (p1b, p2b)) — the two tangent lines, each a pair of
    contact points (one on circle 1, one on circle 2). Guarded against NaN.
    """
    c1 = np.asarray(c1, dtype=float)
    c2 = np.asarray(c2, dtype=float)
    dx, dy = (c2 - c1)
    dist = float(np.hypot(dx, dy))
    if dist < 1e-9:
        dist = 1e-9
    alpha = np.arctan2(dy, dx)
    # External tangents exist when dist >= |r1 - r2|; clip to stay finite.
    cos_arg = np.clip((r1 - r2) / dist, -1.0, 1.0)
    beta = np.arccos(cos_arg)

    lines = []
    for sign in (+1.0, -1.0):
        ang = alpha + sign * beta
        # Contact point lies perpendicular to the tangent direction; the normal
        # from each centre points at angle `ang` (same side for an external tangent).
        n = np.array([np.cos(ang), np.sin(ang)])
        p1 = c1 + r1 * n
        p2 = c2 + r2 * n
        lines.append((p1, p2))
    return lines[0], lines[1]


def compute(v, phase):
    r_in = float(v["r_in"])
    R_out = float(v["R_out"])
    D = float(v["D"])
    wraps = max(int(v["wraps"]), 1)

    O_in = np.array([-D / 2.0, 0.0])
    O_out = np.array([+D / 2.0, 0.0])

    items = []

    # --- pulleys (fixed circle outlines) ----------------------------------
    items.append(path(O_in[0] + r_in * np.cos(_CIRCLE_T),
                      O_in[1] + r_in * np.sin(_CIRCLE_T),
                      color="#1f77b4", lw=1.8, closed=True, dxf_layer="INPUT_SHEAVE"))
    items.append(path(O_out[0] + R_out * np.cos(_CIRCLE_T),
                      O_out[1] + R_out * np.sin(_CIRCLE_T),
                      color="#2ca02c", lw=1.8, closed=True, dxf_layer="OUTPUT_PULLEY"))

    # --- cable: two external tangent lines --------------------------------
    try:
        (p1a, p2a), (p1b, p2b) = _external_tangent_points(O_in, r_in, O_out, R_out)
        items.append(segment(p1a, p2a, color="#d62728", lw=2.2,
                             dxf=True, dxf_layer="CABLE"))
        items.append(segment(p1b, p2b, color="#d62728", lw=2.2,
                             dxf=True, dxf_layer="CABLE"))

        # Small arcs hugging the back of each pulley between the two contacts.
        ang_in_a = np.arctan2(p1a[1] - O_in[1], p1a[0] - O_in[0])
        ang_in_b = np.arctan2(p1b[1] - O_in[1], p1b[0] - O_in[0])
        ang_out_a = np.arctan2(p2a[1] - O_out[1], p2a[0] - O_out[0])
        ang_out_b = np.arctan2(p2b[1] - O_out[1], p2b[0] - O_out[0])

        # Input sheave: wrap arc on the far (left) side (the long way around).
        a0, a1 = sorted((ang_in_a, ang_in_b))
        t_in = np.linspace(a1, a0 + 2 * np.pi, 40)
        items.append(path(O_in[0] + r_in * np.cos(t_in), O_in[1] + r_in * np.sin(t_in),
                          color="#d62728", lw=2.2, closed=False, dxf=False, dxf_layer="CABLE"))

        # Output pulley: wrap arc on the far (right) side.
        b0, b1 = sorted((ang_out_a, ang_out_b))
        t_out = np.linspace(b0, b1, 40)
        items.append(path(O_out[0] + R_out * np.cos(t_out), O_out[1] + R_out * np.sin(t_out),
                          color="#d62728", lw=2.2, closed=False, dxf=False, dxf_layer="CABLE"))
    except Exception:
        pass

    # --- rotating reference spokes ----------------------------------------
    ang_in = phase
    ang_out = phase * r_in / R_out
    items.append(segment(O_in, O_in + r_in * np.array([np.cos(ang_in), np.sin(ang_in)]),
                        color="#1f77b4", lw=2.0, dxf=False))
    items.append(segment(O_out, O_out + R_out * np.array([np.cos(ang_out), np.sin(ang_out)]),
                        color="#2ca02c", lw=2.0, dxf=False))

    # --- centre markers ---------------------------------------------------
    items.append(dot(O_in[0], O_in[1], color="#1f77b4", ms=5))
    items.append(dot(O_out[0], O_out[1], color="#2ca02c", ms=5))

    return items


def readout(v, phase):
    r_in = float(v["r_in"])
    R_out = float(v["R_out"])
    wraps = max(int(v["wraps"]), 1)
    mu = float(v["mu"])

    kin = R_out / r_in if r_in > 1e-9 else float("inf")
    theta_wrap = wraps * 2.0 * np.pi
    grip = np.exp(mu * theta_wrap)
    return (f"Kinematic reduction omega_in/omega_out = R/r = {kin:.3f}:1    "
            f"Capstan grip (Euler) T2/T1 = exp(mu*theta) = {grip:.2f}  "
            f"[mu={mu:.2f}, wrap={wraps}x2pi={theta_wrap:.2f} rad]")


PARAMS = [
    Param("r_in", "Input Sheave Radius", 3.0, 20.0, 6.0, step=0.5),
    Param("R_out", "Output Pulley Radius", 10.0, 60.0, 30.0, step=0.5),
    Param("D", "Center Distance", 40.0, 140.0, 80.0, step=1.0),
    Param("wraps", "Cable Wraps", 1, 6, 3, step=1, integer=True, fmt="%0.0f"),
    Param("mu", "Friction Coeff", 0.05, 0.5, 0.1, step=0.01),
]

demo = MechanismDemo(
    title="Capstan / Cable (Tendon) Drive",
    subtitle="Small sheave drives a larger pulley via a wrapped cable. Kinematic reduction (R/r) and Euler capstan grip (exp(mu*theta)) are distinct.",
    params=PARAMS,
    compute=compute,
    readout=readout,
    export_name="capstan-drive",
)

_has_custom_layout = True
demo.build()
fig = demo.fig

if __name__ == "__main__":
    demo.show()
