# External Geneva Drive (Maltese Cross)
#
# An intermittent-motion mechanism: a continuously rotating driver carries a
# single crank pin that engages the radial slots of a slotted "Maltese cross"
# wheel. Each driver revolution advances the wheel by exactly one slot
# (360/n degrees) and then the wheel DWELLS, locked by a circular locking disc
# on the driver, until the pin engages the next slot.
#
# For an external Geneva drive with n slots:
#   center distance  C = a / sin(pi/n)
#   locking radius   b = C * cos(pi/n)
#   motion fraction  = (180 - 360/n) / 360   (e.g. n=4 -> 90 deg motion / 270 dwell)

from __future__ import annotations

import numpy as np

from novel_demo_common import MechanismDemo, Param, path, circles, dot, segment


def _rot(x, y, a):
    c, s = np.cos(a), np.sin(a)
    return x * c - y * s, x * s + y * c


def driven_angle(theta_drv, n, a, C):
    """Absolute rotation of the driven wheel for a given driver angle.

    theta_drv is the driver crank angle (rad), with theta_drv=0 placing the pin
    on the line of centres (mid-engagement of slot 0). Each full driver
    revolution advances the wheel by exactly one slot = 2*pi/n. Within the
    engagement window the slot angle follows
        phi = atan2(a*sin(theta), C - a*cos(theta))
    and outside it the wheel dwells at the last indexed multiple of 2*pi/n.
    """
    slot = 2.0 * np.pi / n
    # Which driver revolution / index are we in?
    k = np.floor((theta_drv + np.pi) / (2.0 * np.pi))     # index count
    theta = theta_drv - k * 2.0 * np.pi                   # local angle in (-pi, pi]
    theta_engage = np.pi / 2.0 - np.pi / n                # half engagement window
    if -theta_engage <= theta <= theta_engage:
        phi = np.arctan2(a * np.sin(theta), C - a * np.cos(theta))
    elif theta > theta_engage:
        # already handed off this slot -> sit at the next index (advanced)
        phi = 0.5 * slot
    else:  # theta < -theta_engage : not yet engaged -> previous index
        phi = -0.5 * slot
    # Note: at theta = +/-theta_engage the entry/exit is tangential and
    # phi = +/- slot/2 exactly, so the hand-off to the dwell value is continuous.
    return k * slot + phi


def compute(v, phase):
    n = max(int(v["n"]), 3)
    a = float(v["a"])
    sin_pn = np.sin(np.pi / n)
    cos_pn = np.cos(np.pi / n)
    C = a / sin_pn                      # center distance
    b = C * cos_pn                      # locking radius (root of slot)
    slot = 2.0 * np.pi / n

    Od = (0.0, 0.0)
    Ow = (C, 0.0)

    # The wheel is set up so slot 0 points back toward the driver (i.e. along
    # -x from Ow) at mid-engagement; we measure driven rotation about that.
    phi_w = driven_angle(phase, n, a, C)

    # Driver crank: theta_drv measured from the line of centres pointing from Od
    # toward Ow (+x). Pin sits at angle (pi + theta_drv) seen from Od? No: the
    # pin must reach toward the wheel. At theta=0 the pin is closest to the
    # wheel, i.e. on the +x side at radius a from Od.
    theta_drv = phase
    pin = (Od[0] + a * np.cos(theta_drv), Od[1] + a * np.sin(theta_drv))

    items = []

    # ---- Driver -------------------------------------------------------------
    # Locking disc: an arc of radius (b - small) centred on Od, with a cut-out
    # around the crank-pin side so it does not collide with the slot during
    # engagement. Drawn as an open arc spanning the dwell-locking sector.
    lock_r = b - 0.06 * a
    # The locking arc covers the angles where the wheel must be held; it is
    # absent over the engagement sector. The mouth (cut-out) half-angle:
    mouth = np.pi / 2.0 - np.pi / n + 0.15      # a touch wider than engagement
    arc_t = np.linspace(mouth, 2.0 * np.pi - mouth, 120)
    items.append(path(Od[0] + lock_r * np.cos(arc_t), Od[1] + lock_r * np.sin(arc_t),
                      color="#1f77b4", lw=1.4, closed=False,
                      dxf=True, dxf_layer="DRIVER_LOCK"))

    # Driver hub
    hub_r = 0.5 * a
    hub_t = np.linspace(0.0, 2.0 * np.pi, 120)
    items.append(path(Od[0] + hub_r * np.cos(hub_t), Od[1] + hub_r * np.sin(hub_t),
                      color="#1f77b4", lw=1.8, closed=True,
                      dxf=True, dxf_layer="DRIVER_HUB"))

    # Crank arm + pin
    items.append(segment(Od, pin, color="#1f77b4", lw=2.2, dxf=False))
    items.append(circles([pin], 0.12 * a, color="#d62728", lw=1.8,
                         dxf=False, dxf_layer="PIN"))

    # ---- Driven wheel (Maltese cross) --------------------------------------
    wheel_r = C - 0.2 * a
    body_t = np.linspace(0.0, 2.0 * np.pi, 200)
    items.append(path(Ow[0] + wheel_r * np.cos(body_t), Ow[1] + wheel_r * np.sin(body_t),
                      color="#2ca02c", lw=1.8, closed=True,
                      dxf=True, dxf_layer="WHEEL_BODY"))

    # Slots: radial open channels. Slot 0 points toward the driver (-x from Ow)
    # at mid-engagement. Each slot is a narrow channel (two parallel segments)
    # from the rim inward to depth (wheel_r - b) + a bit.
    half_w = 0.14 * a                      # half slot width (to clear the pin)
    slot_depth = (wheel_r - b) + 0.20 * a  # how far the slot cuts inward
    inner_r = wheel_r - slot_depth
    for i in range(n):
        # base direction of slot i in the wheel frame, with slot 0 toward -x
        ang = np.pi + phi_w + i * slot
        d = np.array([np.cos(ang), np.sin(ang)])         # outward radial dir
        p = np.array([-np.sin(ang), np.cos(ang)])        # perpendicular
        outer = np.array(Ow) + wheel_r * d
        inner = np.array(Ow) + inner_r * d
        for sgn in (+1.0, -1.0):
            o = outer + sgn * half_w * p
            ii = inner + sgn * half_w * p
            items.append(segment(tuple(o), tuple(ii), color="#2ca02c", lw=1.6,
                                 dxf=True, dxf_layer="WHEEL_SLOTS"))
        # closing cap at the bottom of the slot
        b0 = inner + half_w * p
        b1 = inner - half_w * p
        items.append(segment(tuple(b0), tuple(b1), color="#2ca02c", lw=1.6,
                             dxf=True, dxf_layer="WHEEL_SLOTS"))

    # Centre markers
    items.append(dot(Od[0], Od[1], color="#1f77b4", ms=5))
    items.append(dot(Ow[0], Ow[1], color="#2ca02c", ms=5))
    return items


def readout(v, phase):
    n = max(int(v["n"]), 3)
    a = float(v["a"])
    C = a / np.sin(np.pi / n)
    index_deg = 360.0 / n
    motion_deg = 180.0 - 360.0 / n
    dwell_deg = 360.0 - motion_deg
    motion_frac = motion_deg / 360.0
    return (f"n={n} slots   index={index_deg:.1f} deg/rev   C={C:.2f} mm   "
            f"motion {motion_deg:.0f} / dwell {dwell_deg:.0f} deg "
            f"(motion frac {motion_frac:.3f})")


PARAMS = [
    Param("n", "Number of Slots", 3, 8, 4, step=1, integer=True, fmt="%0.0f"),
    Param("a", "Crank Pin Radius", 8.0, 40.0, 20.0, step=0.5),
]

demo = MechanismDemo(
    title="External Geneva Drive (Maltese Cross)",
    subtitle="Intermittent indexing: each driver revolution advances the slotted wheel by one slot (360/n deg), then the locking disc holds it through the dwell.",
    params=PARAMS,
    compute=compute,
    readout=readout,
    export_name="geneva-drive",
)

_has_custom_layout = True
demo.build()
fig = demo.fig

if __name__ == "__main__":
    demo.show()
