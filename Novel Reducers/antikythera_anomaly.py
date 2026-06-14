# Antikythera Mechanism — Pin-and-Slot Lunar Anomaly Device
#
# The ancient Greek Antikythera mechanism modeled the Moon's varying apparent
# speed (faster near perigee, slower near apogee) using two gears mounted on
# slightly OFFSET centres and coupled by a pin riding in a radial slot.
#
#   * Gear k1 (driver) carries a PIN at radius rp, turning at the constant input
#     rate: pin angle = phase.
#   * Gear k2 (output) has a radial SLOT. The pin slides in the slot, so the
#     slot always points toward the pin and k2's angle theta2 advances
#     NON-uniformly because the two centres are offset by delta.
#
# Over one full input revolution the output also completes one revolution (mean
# ratio = 1) but its instantaneous speed varies through the cycle — exactly the
# Moon's anomalistic speed variation.

from __future__ import annotations

import numpy as np

from novel_demo_common import MechanismDemo, Param, path, circles, dot, segment


def _theta2(phase, rp, delta):
    """Output (slot) angle: direction from O2 to the pin P."""
    o1x = -0.5 * delta
    o2x = 0.5 * delta
    px = o1x + rp * np.cos(phase)
    py = rp * np.sin(phase)
    return np.arctan2(py - 0.0, px - o2x)


def compute(v, phase):
    rp = max(float(v["rp"]), 1.0)
    delta = max(float(v["delta"]), 1e-3)
    # Keep the pin reachable by the slot: delta must stay below rp.
    delta = min(delta, rp - 0.5)

    o1 = (-0.5 * delta, 0.0)
    o2 = (0.5 * delta, 0.0)

    # Pin on the driver
    px = o1[0] + rp * np.cos(phase)
    py = o1[1] + rp * np.sin(phase)

    # Output slot angle and the pin's reach measured from O2
    theta2 = _theta2(phase, rp, delta)
    s = float(np.hypot(px - o2[0], py - o2[1]))

    items = []

    # k1 driver disc + hub
    r1 = rp * 1.15
    t = np.linspace(0.0, 2.0 * np.pi, 200)
    items.append(path(o1[0] + r1 * np.cos(t), o1[1] + r1 * np.sin(t),
                      color="#1f77b4", lw=1.8, closed=True, dxf_layer="DRIVER_DISC"))
    items.append(dot(o1[0], o1[1], color="#1f77b4", ms=5))

    # k2 output disc + hub
    r2 = (rp + delta) * 1.1
    items.append(path(o2[0] + r2 * np.cos(t), o2[1] + r2 * np.sin(t),
                      color="#2ca02c", lw=1.8, closed=True, dxf_layer="OUTPUT_DISC"))
    items.append(dot(o2[0], o2[1], color="#2ca02c", ms=5))

    # Radial SLOT on k2: a narrow channel from O2 outward along theta2, long
    # enough to cover the pin's full reach (s swings between rp-delta and rp+delta).
    slot_inner = max(rp - delta - 0.5 * rp, 0.5)
    slot_outer = rp + delta + 0.15 * rp
    c, sn = np.cos(theta2), np.sin(theta2)
    nx, ny = -sn, c                      # unit normal to the slot direction
    half_w = max(0.16 * rp, 0.6)         # half-width of the slot channel
    inner_pt = (o2[0] + slot_inner * c, o2[1] + slot_inner * sn)
    outer_pt = (o2[0] + slot_outer * c, o2[1] + slot_outer * sn)
    # Two parallel rails forming the slot
    for sign in (1.0, -1.0):
        a = (inner_pt[0] + sign * half_w * nx, inner_pt[1] + sign * half_w * ny)
        b = (outer_pt[0] + sign * half_w * nx, outer_pt[1] + sign * half_w * ny)
        items.append(segment(a, b, color="#2ca02c", lw=1.4, dxf=True, dxf_layer="SLOT"))
    # Close the slot ends so the channel reads as a slot
    items.append(segment((inner_pt[0] + half_w * nx, inner_pt[1] + half_w * ny),
                         (inner_pt[0] - half_w * nx, inner_pt[1] - half_w * ny),
                         color="#2ca02c", lw=1.4, dxf=True, dxf_layer="SLOT"))
    items.append(segment((outer_pt[0] + half_w * nx, outer_pt[1] + half_w * ny),
                         (outer_pt[0] - half_w * nx, outer_pt[1] - half_w * ny),
                         color="#2ca02c", lw=1.4, dxf=True, dxf_layer="SLOT"))

    # OUTPUT POINTER: from O2 along theta2 to the disc rim
    items.append(segment(o2, (o2[0] + r2 * c, o2[1] + r2 * sn),
                         color="#9467bd", lw=2.2, dxf=False, dxf_layer="POINTER"))

    # Crank on the driver: O1 -> P
    items.append(segment(o1, (px, py), color="#d62728", lw=1.4, dxf=False))

    # The PIN itself (rides in the slot)
    items.append(circles([(px, py)], rp * 0.12, color="#d62728", lw=1.6,
                         dxf=False, dxf_layer="PIN"))
    items.append(dot(px, py, color="#d62728", ms=4))

    return items


def _ratio(phase, rp, delta, h=1e-4):
    """Instantaneous omega_out/omega_in via central finite difference."""
    a = _theta2(phase + h, rp, delta)
    b = _theta2(phase - h, rp, delta)
    d = a - b
    # unwrap across the +/-pi branch cut
    d = (d + np.pi) % (2.0 * np.pi) - np.pi
    return d / (2.0 * h)


def readout(v, phase):
    rp = max(float(v["rp"]), 1.0)
    delta = max(float(v["delta"]), 1e-3)
    delta = min(delta, rp - 0.5)
    ecc = delta / rp

    ratio = _ratio(phase, rp, delta)

    # Theoretical extremes over a full cycle (scan numerically)
    scan = np.array([_ratio(p, rp, delta) for p in np.linspace(0.0, 2.0 * np.pi, 361)])
    scan = scan[np.isfinite(scan)]
    rmin, rmax = (float(scan.min()), float(scan.max())) if scan.size else (1.0, 1.0)

    return (f"Center offset delta={delta:.2f}  Pin radius rp={rp:.2f}  "
            f"Eccentricity delta/rp={ecc:.3f}\n"
            f"omega_out/omega_in = {ratio:+.3f}  (swings {rmin:.3f}..{rmax:.3f}, "
            f"mean 1) — models the Moon's anomalistic speed variation")


PARAMS = [
    Param("rp", "Pin Radius on Driver", 8.0, 30.0, 18.0, step=0.5),
    Param("delta", "Center Offset", 1.0, 12.0, 6.0, step=0.1),
]

demo = MechanismDemo(
    title="Antikythera Pin-and-Slot Lunar Anomaly",
    subtitle="Two offset gears coupled by a pin in a radial slot reproduce the Moon's varying speed (faster at perigee, slower at apogee).",
    params=PARAMS,
    compute=compute,
    readout=readout,
    export_name="antikythera-anomaly",
)

_has_custom_layout = True
demo.build()
fig = demo.fig

if __name__ == "__main__":
    demo.show()
