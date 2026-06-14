# Friction Wheel-on-Disc CVT (Variable-Ratio Traction Drive)
#
# A classic continuously variable transmission: a large input DISC spins about
# its centre, and a small friction WHEEL rolls on the disc face at a contact
# radius ``x`` measured out along the radial track. Because the wheel rolls
# without slipping at that radius, its angular speed is set by the rim speed it
# sees:
#
#     omega_out = omega_in * (x / rw)
#
# Sliding the wheel toward the centre lowers the ratio (more reduction);
# sliding it outward raises it (overdrive). Crossing the centre flips the rim
# velocity direction, so the OUTPUT REVERSES, and at x = 0 the wheel sees zero
# surface speed: a geared neutral.

from __future__ import annotations

import numpy as np

from novel_demo_common import MechanismDemo, Param, path, circles, dot, segment


def compute(v, phase):
    Rd = v["Rd"]
    rw = v["rw"]
    # Keep the contact point on the disc even if Rd is lowered below x.
    x = float(np.clip(v["x"], -Rd, Rd))

    items = []

    t = np.linspace(0.0, 2.0 * np.pi, 240)

    # Input disc (large), centred at the origin.
    items.append(path(Rd * np.cos(t), Rd * np.sin(t),
                      color="#1f77b4", lw=1.8, closed=False, dxf=True,
                      dxf_layer="DISC"))

    # Faint radial track along +/- Y showing where the wheel can sit.
    items.append(segment((0.0, -Rd), (0.0, Rd), color="#cccccc", lw=1.0,
                         dxf=True, dxf_layer="TRACK"))

    # Friction wheel: tangent to the radial track at the contact point (0, x),
    # with its centre offset to +X by rw.
    wcx, wcy = rw, x
    items.append(path(wcx + rw * np.cos(t), wcy + rw * np.sin(t),
                      color="#2ca02c", lw=1.8, closed=False, dxf=True,
                      dxf_layer="WHEEL"))

    # Disc reference spoke (centre -> rim) showing the input rotation.
    items.append(segment((0.0, 0.0), (Rd * np.cos(phase), Rd * np.sin(phase)),
                         color="#1f77b4", lw=1.6, dxf=False))
    items.append(dot(Rd * np.cos(phase), Rd * np.sin(phase), color="#1f77b4", ms=5))

    # Output (wheel) spoke: rotates by phase * x / rw, so it reverses with x.
    out_ang = phase * x / rw if rw > 1e-9 else 0.0
    items.append(segment((wcx, wcy),
                         (wcx + rw * np.cos(out_ang), wcy + rw * np.sin(out_ang)),
                         color="#2ca02c", lw=1.6, dxf=False))

    # Contact point and centre markers.
    items.append(dot(0.0, x, color="#d62728", ms=6))
    items.append(dot(0.0, 0.0, color="#1f77b4", ms=4))
    items.append(dot(wcx, wcy, color="#2ca02c", ms=4))

    return items


def readout(v, phase):
    Rd = v["Rd"]
    rw = v["rw"]
    x = float(np.clip(v["x"], -Rd, Rd))
    ratio = x / rw if rw > 1e-9 else 0.0

    if abs(x) < 1e-6:
        direction = "NEUTRAL"
    elif x > 0:
        direction = "FORWARD"
    else:
        direction = "REVERSE"

    if abs(x) < 1e-6:
        mode = "neutral"
    elif abs(x) > rw:
        mode = "overdrive"
    else:
        mode = "reduction"

    return (f"Contact x={x:+.1f}   Wheel rw={rw:.1f}   "
            f"Ratio omega_out/omega_in = x/rw = {ratio:+.3f} ({mode})   "
            f"{direction}")


PARAMS = [
    Param("Rd", "Disc Radius", 20.0, 80.0, 50.0, step=0.5),
    Param("rw", "Friction Wheel Radius", 3.0, 20.0, 8.0, step=0.1),
    Param("x", "Contact Radius", -50.0, 50.0, 25.0, step=0.5),
]

demo = MechanismDemo(
    title="Friction Wheel-on-Disc CVT",
    subtitle="Wheel rolls on a spinning disc at contact radius x; output speed = input * x/rw. Slide through the centre to reverse.",
    params=PARAMS,
    compute=compute,
    readout=readout,
    export_name="friction-disc-cvt",
)

_has_custom_layout = True
demo.build()
fig = demo.fig

if __name__ == "__main__":
    demo.show()
