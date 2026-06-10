# Wolfrom Cycloidal Planetary Generator
# Two-stage Wolfrom-style differential cycloidal planetary drive animation.
# Stage 1 blue outer ring is fixed. Stage 2 blue outer ring rotates as the output.
# Both green/lobed bodies are mechanically locked as one rigid compound member.
# Based on demo_14.py from Cycloidal-Drive-Animation.

from dataclasses import dataclass
from itertools import count
from pathlib import Path
import subprocess
import sys

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider, Button, TextBox, CheckButtons, RadioButtons

# --- shared utilities path (export_naming) ---------------------------------
_SHARED_UTILS_DIR = str(Path(__file__).resolve().parents[1])
if _SHARED_UTILS_DIR not in sys.path:
    sys.path.insert(0, _SHARED_UTILS_DIR)

from export_naming import prompt_single_export_name

from cycloidal_drive import default_export_directory, reveal_in_finder

try:
    import ezdxf
except ImportError:
    ezdxf = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EPS = 1e-9
MAX_PINS = 96
SAMPLE_COUNT = 2000
INTERVAL_MS = 50
AXCOLOR = "lightgoldenrodyellow"
OUTPUT_VISUAL_SIGN = -1.0  # flips Stage 2 output ring visual direction
DXF_UNITS_LABEL = "DXF units: millimeters (mm)."
DEFAULT_EXPORT_FOLDER = "Cycloidal Drive Exports"

# Shared theta array for all geometry functions
_T = np.linspace(0, 2 * np.pi, SAMPLE_COUNT)

# ---------------------------------------------------------------------------
# Stage geometry dataclass
# ---------------------------------------------------------------------------
@dataclass
class StageGeometry:
    fm: float = 50.0
    Rd: float = 34.0
    rd: float = 4.0
    e: float = 1.5
    N: int = 14
    d: float = 12.0
    D: float = 89.0

# ---------------------------------------------------------------------------
# Wolfrom ratio model
# ---------------------------------------------------------------------------
def base_planetary_ratio(g1: StageGeometry) -> float:
    """Base ratio of one cycloidal-planetary stage."""
    if abs(g1.Rd) < EPS:
        return float("inf")
    return 1.0 + (g1.D / 2.0) / g1.Rd


def wolfrom_total_ratio(g1: StageGeometry, g2: StageGeometry) -> float:
    """Signed Wolfrom-style differential total ratio."""
    base = base_planetary_ratio(g1)
    if abs(g2.D) < EPS:
        return float("inf")
    denominator = 1.0 - (g1.D / g2.D)
    if abs(denominator) < EPS:
        return float("inf")
    return base / denominator


def solve_stage2_pcd_for_target(
    g1: StageGeometry,
    target_ratio: float,
    larger_output_ring: bool = True,
) -> float:
    """Calculate Stage 2 PCD required to hit a desired absolute reduction ratio."""
    target = abs(float(target_ratio))
    base = base_planetary_ratio(g1)
    if target <= base:
        raise ValueError(
            f"Target ratio must be greater than base ratio. "
            f"Target={target:.3f}, base={base:.3f}"
        )
    if larger_output_ring:
        denominator = 1.0 - base / target
    else:
        denominator = 1.0 + base / target
    if abs(denominator) < EPS:
        raise ValueError("Invalid target ratio produced near-zero denominator.")
    return g1.D / denominator

# ---------------------------------------------------------------------------
# Geometry helpers (used by both plotting and DXF export)
# ---------------------------------------------------------------------------
def rotate_xy(x, y, angle):
    """Rotate 2D points by angle (radians)."""
    ca = np.cos(angle)
    sa = np.sin(angle)
    return x * ca - y * sa, x * sa + y * ca


def get_inner_curve_points(g: StageGeometry, phi=0.0, extra_world_angle=0.0):
    """Red hypocycloid — green/lobed compound member profile.
    Uses original demo_14.py phasing: -phi/(n-1) - phi/(n+1) + pi/(n-1).
    Returns (x, y) arrays.
    """
    e, n, D, d = g.e, int(g.N), g.D, g.d
    RD = D / 2.0
    rd = d / 2.0
    rc = (n - 1) * (RD / n)
    rm = RD / n

    xa = (rc + rm) * np.cos(_T) - e * np.cos((rc + rm) / rm * _T)
    ya = (rc + rm) * np.sin(_T) - e * np.sin((rc + rm) / rm * _T)

    dxa = (rc + rm) * (-np.sin(_T) + (e / rm) * np.sin((rc + rm) / rm * _T))
    dya = (rc + rm) * (np.cos(_T) - (e / rm) * np.cos((rc + rm) / rm * _T))

    denom = np.sqrt(dxa ** 2 + dya ** 2)
    denom = np.where(denom < EPS, EPS, denom)

    x_local = xa + rd * (-dya) / denom
    y_local = ya + rd * dxa / denom

    # Original demo_14.py red curve angle
    local_angle = -phi / (n - 1) - phi / (n + 1) + np.pi / (n - 1)

    x, y = rotate_xy(x_local, y_local, local_angle)
    if abs(extra_world_angle) > EPS:
        x, y = rotate_xy(x, y, extra_world_angle)
    return x, y


def get_outer_curve_points(g: StageGeometry, phi=0.0, output_ring_angle=0.0):
    """Blue epicycloid — outer ring profile.
    Original demo_14.py has NO local rotation on the blue curve.
    Only applies output_ring_angle (Stage 2 output rotation).
    Returns (x, y) arrays.
    """
    e, n, D, d = g.e, int(g.N), g.D, g.d
    RD = D / 2.0
    rd = d / 2.0
    rc = (n + 1) * (RD / n)
    rm = RD / n

    xa = (rc - rm) * np.cos(_T) + e * np.cos((rc - rm) / rm * _T)
    ya = (rc - rm) * np.sin(_T) - e * np.sin((rc - rm) / rm * _T)

    dxa = (rc - rm) * (-np.sin(_T) - (e / rm) * np.sin((rc - rm) / rm * _T))
    dya = (rc - rm) * (np.cos(_T) - (e / rm) * np.cos((rc - rm) / rm * _T))

    denom = np.sqrt(dxa ** 2 + dya ** 2)
    denom = np.where(denom < EPS, EPS, denom)

    x_local = xa - rd * (-dya) / denom
    y_local = ya - rd * dxa / denom

    return rotate_xy(x_local, y_local, output_ring_angle)


def get_outer_pin_centers(g: StageGeometry, phi=0.0):
    """Return list of (x, y) centers for outer ring pin circles.
    Uses original demo_14.py phasing: -phi/(n+1).
    """
    n = int(g.N)
    D, e = g.D, g.e
    local_angle = -phi / (n + 1)

    centers = []
    for i in range(n):
        angle_i = 2 * i * np.pi / n
        cx = D / 2.0 * np.cos(angle_i) + e * np.cos(phi)
        cy = D / 2.0 * np.sin(angle_i) + e * np.sin(phi)
        rx, ry = rotate_xy(cx, cy, local_angle)
        centers.append((float(rx), float(ry)))
    return centers


def get_drive_pin_centers(g: StageGeometry, phi=0.0):
    """Return list of (x, y) centers for drive pin circles.
    Uses original demo_14.py phasing: -phi/(n+1).
    """
    n = int(g.N)
    D = g.D
    local_angle = -phi / (n + 1)

    centers = []
    for i in range(n):
        angle_i = 2 * i * np.pi / n
        cx = D / 2.0 * np.cos(angle_i)
        cy = D / 2.0 * np.sin(angle_i)
        rx, ry = rotate_xy(cx, cy, local_angle)
        centers.append((float(rx), float(ry)))
    return centers


# ---------------------------------------------------------------------------
# CycloidalStageArtist — draws one stage on a given axis
#
# Phasing rules (matching original demo_14.py):
#   • Outer ring pins (green):   local_angle = -phi / (n + 1)
#   • Drive pins (black):         local_angle = -phi / (n + 1)
#   • Inner curve (red):          local_angle = -phi/(n-1) - phi/(n+1) + pi/(n-1)
#   • Outer curve (blue):         NO local rotation, only output_ring_angle
# ---------------------------------------------------------------------------
class CycloidalStageArtist:
    def __init__(self, ax, title, max_pins=MAX_PINS):
        self.ax = ax
        self.ax.set_aspect("equal")
        self.ax.set_title(title, fontsize=11, pad=6)
        self.max_pins = max_pins

        # Outer ring pins (green circles)
        self.pins = [ax.plot([], [], "g-", lw=1.2)[0] for _ in range(max_pins)]
        self.pin_dot, = ax.plot([], [], "go", ms=4)

        # Drive pins (black circles)
        self.drive_pins = [ax.plot([], [], "k-", lw=1.0)[0] for _ in range(max_pins)]

        # Center circle (red)
        self.center_circle, = ax.plot([], [], "r-", lw=1.5)

        # Inner curve = red hypocycloid (green/lobed compound member)
        self.inner_curve, = ax.plot([], [], "r-", lw=1.8)
        self.inner_dot, = ax.plot([], [], "ro", ms=5)

        # Outer curve = blue epicycloid (outer ring)
        self.outer_curve, = ax.plot([], [], "b-", lw=1.8)
        self.outer_dot, = ax.plot([], [], "bo", ms=5)

        # Status text inside plot
        self.status_text = ax.text(
            0.02, 0.98, "",
            transform=ax.transAxes, va="top", ha="left", fontsize=8,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.75),
        )

    # -- helpers --
    def _hide_unused(self, lines, used):
        for i, line in enumerate(lines):
            if i >= used:
                line.set_data([], [])

    # -- drawing methods --
    def draw_center_circle(self, r, ring_world_angle=0.0):
        x = r * np.sin(_T)
        y = r * np.cos(_T)
        x, y = rotate_xy(x, y, ring_world_angle)
        self.center_circle.set_data(x, y)

    def update_pins(self, g: StageGeometry, phi, ring_world_angle=0.0):
        """Green outer ring pins. Original demo_14.py angle: -phi/(n+1)."""
        n = int(g.N)
        d, D, e = g.d, g.D, g.e
        local_angle = -phi / (n + 1)

        for i in range(n):
            xd = (d / 2 * np.cos(_T) + D / 2 * np.cos(2 * i * np.pi / n)) + e * np.cos(phi)
            yd = (d / 2 * np.sin(_T) + D / 2 * np.sin(2 * i * np.pi / n)) + e * np.sin(phi)
            x, y = rotate_xy(xd, yd, local_angle)
            x, y = rotate_xy(x, y, ring_world_angle)
            self.pins[i].set_data(x, y)

        self._hide_unused(self.pins, n)

        # Pin dot (eccentricity tracker)
        xd1 = (d / 2 * np.cos(phi) + D / 2) + e * np.cos(phi)
        yd1 = (d / 2 * np.sin(phi)) + e * np.sin(phi)
        x1, y1 = rotate_xy(xd1, yd1, local_angle)
        x1, y1 = rotate_xy(x1, y1, ring_world_angle)
        self.pin_dot.set_data([x1], [y1])

    def update_drive_pins(self, g: StageGeometry, phi, ring_world_angle=0.0):
        """Black drive pins. Original demo_14.py angle: -phi/(n+1)."""
        n = int(g.N)
        r, D = g.rd, g.D
        local_angle = -phi / (n + 1)

        for i in range(n):
            xd = r * np.sin(_T) + D / 2 * np.cos(2 * i * np.pi / n)
            yd = r * np.cos(_T) + D / 2 * np.sin(2 * i * np.pi / n)
            x, y = rotate_xy(xd, yd, local_angle)
            x, y = rotate_xy(x, y, ring_world_angle)
            self.drive_pins[i].set_data(x, y)

        self._hide_unused(self.drive_pins, n)

    def update_inner_curve(self, g: StageGeometry, phi, ring_world_angle=0.0):
        """Red hypocycloid. Original demo_14.py local angle, then ring_world_angle."""
        x, y = get_inner_curve_points(g, phi=phi, extra_world_angle=0.0)
        x, y = rotate_xy(x, y, ring_world_angle)
        self.inner_curve.set_data(x, y)
        self.inner_dot.set_data([x[0]], [y[0]])

    def update_outer_curve(self, g: StageGeometry, phi, ring_world_angle=0.0):
        """Blue epicycloid. Original NO local rotation — ring_world_angle applied after."""
        x, y = get_outer_curve_points(g, phi=phi, output_ring_angle=0.0)
        x, y = rotate_xy(x, y, ring_world_angle)
        self.outer_curve.set_data(x, y)
        self.outer_dot.set_data([x[0]], [y[0]])

    def update_limits(self, g: StageGeometry):
        lim = 1.35 * max(g.D / 2, g.Rd, g.D / 2 + g.d + abs(g.e))
        self.ax.set_xlim(-lim, lim)
        self.ax.set_ylim(-lim, lim)

    def draw(self, g: StageGeometry, phi, ring_world_angle=0.0, status=""):
        """Top-level draw: solve local mesh, then rotate entire result by ring_world_angle."""
        self.update_limits(g)
        self.draw_center_circle(g.Rd, ring_world_angle=ring_world_angle)
        self.update_pins(g, phi, ring_world_angle=ring_world_angle)
        self.update_drive_pins(g, phi, ring_world_angle=ring_world_angle)
        self.update_inner_curve(g, phi, ring_world_angle=ring_world_angle)
        self.update_outer_curve(g, phi, ring_world_angle=ring_world_angle)
        self.status_text.set_text(status)


# ===========================================================================
# Main — setup and launch (runs at module level for hub compatibility)
# ===========================================================================

# Sentinel: tells the hub not to override this file's custom layout
_has_custom_layout = True

# ---------------------------------------------------------------------------
# Figure and layout
# ---------------------------------------------------------------------------
fig = plt.figure(figsize=(16, 7.5), dpi=100, constrained_layout=False)
fig.canvas.manager.set_window_title("Wolfrom Cycloidal Planetary Generator - Cycloidal Drive Hub")

try:
    fig.canvas.manager.resize(1600, 750)
except Exception:
    pass

# Top ratio display
ratio_text = fig.text(
    0.56, 0.975, "",
    ha="center", va="top", fontsize=10, family="monospace",
    bbox=dict(boxstyle="round", facecolor="white", alpha=0.90),
)

# Plots — right of the sidebar
ax_stage1 = fig.add_axes([0.19, 0.38, 0.38, 0.50])
ax_stage2 = fig.add_axes([0.60, 0.38, 0.38, 0.50])

stage1_artist = CycloidalStageArtist(ax_stage1, "Stage 1 — Fixed Outer Ring")
stage2_artist = CycloidalStageArtist(ax_stage2, "Stage 2 — Output Outer Ring")

# ---------------------------------------------------------------------------
# Sliders
# ---------------------------------------------------------------------------
axcolor = "lightgoldenrodyellow"
sliders = {}

def add_slider(key, label, x, y, w, vmin, vmax, vinit, step, valfmt="%1.2f"):
    ax_s = fig.add_axes([x, y, w, 0.020], facecolor=axcolor)
    s = Slider(
        ax_s,
        label,
        vmin,
        vmax,
        valinit=vinit,
        valstep=step,
        valfmt=valfmt,
    )
    s.label.set_fontsize(8.5)
    s.valtext.set_fontsize(8.5)
    sliders[key] = s
    return s

# Speed slider — centered under the plots, above stage sliders
s_speed = add_slider("speed", "Input Speed \u00d7", 0.430, 0.305, 0.300, 0.05, 50.0, 1.0, 0.05, "%1.2f")

# Stage 1 sliders (under left plot)
left_x = 0.30
right_x = 0.72
slider_w = 0.22

s1_Rd = add_slider("s1_Rd", "S1 Center Circle Radius",  left_x, 0.240, slider_w, 1, 80, 34.0, 0.1, "%1.2f")
s1_rd = add_slider("s1_rd", "S1 Drive Pin Radius",      left_x, 0.200, slider_w, 0.1, 20, 4.0, 0.1, "%1.2f")
s1_e  = add_slider("s1_e",  "S1 Eccentricity",          left_x, 0.160, slider_w, 0.1, 20, 1.5, 0.1, "%1.2f")
s1_N  = add_slider("s1_N",  "S1 Number of Pins",        left_x, 0.120, slider_w, 3, 80, 14, 1, "%0.0f")
s1_d  = add_slider("s1_d",  "S1 Ring Pin Diameter",     left_x, 0.080, slider_w, 1, 30, 12.0, 0.1, "%1.2f")
s1_D  = add_slider("s1_D",  "S1 Pin Circle Diameter",   left_x, 0.040, slider_w, 10, 200, 89.0, 0.01, "%1.3f")

# Stage 2 sliders (under right plot)
s2_Rd = add_slider("s2_Rd", "S2 Center Circle Radius",  right_x, 0.240, slider_w, 1, 80, 34.0, 0.1, "%1.2f")
s2_rd = add_slider("s2_rd", "S2 Drive Pin Radius",      right_x, 0.200, slider_w, 0.1, 20, 4.0, 0.1, "%1.2f")
s2_e  = add_slider("s2_e",  "S2 Eccentricity",          right_x, 0.160, slider_w, 0.1, 20, 1.5, 0.1, "%1.2f")
s2_N  = add_slider("s2_N",  "S2 Number of Pins",        right_x, 0.120, slider_w, 3, 80, 14, 1, "%0.0f")
s2_d  = add_slider("s2_d",  "S2 Ring Pin Diameter",     right_x, 0.080, slider_w, 1, 30, 12.0, 0.1, "%1.2f")
s2_D  = add_slider("s2_D",  "S2 Output PCD",            right_x, 0.040, slider_w, 10, 200, 90.04, 0.001, "%1.3f")

# ---------------------------------------------------------------------------
# GUI state
# ---------------------------------------------------------------------------
target_ratio = 200.0
larger_output_ring = True
is_programmatic_update = False
input_angle = 0.0

# ---------------------------------------------------------------------------
# Geometry getters
# ---------------------------------------------------------------------------
def get_stage1_geometry() -> StageGeometry:
    return StageGeometry(
        fm=50.0,
        Rd=float(s1_Rd.val),
        rd=float(s1_rd.val),
        e=float(s1_e.val),
        N=int(round(s1_N.val)),
        d=float(s1_d.val),
        D=float(s1_D.val),
    )


def get_stage2_geometry() -> StageGeometry:
    return StageGeometry(
        fm=50.0,
        Rd=float(s2_Rd.val),
        rd=float(s2_rd.val),
        e=float(s2_e.val),
        N=int(round(s2_N.val)),
        d=float(s2_d.val),
        D=float(s2_D.val),
    )

# ---------------------------------------------------------------------------
# Ratio display
# ---------------------------------------------------------------------------
def update_ratio_display(g1: StageGeometry, g2: StageGeometry):
    base = base_planetary_ratio(g1)
    total = wolfrom_total_ratio(g1, g2)
    mismatch = 1.0 - g1.D / g2.D
    delta_D = g2.D - g1.D

    if np.isinf(total):
        total_text = "\u221e"
        out_per_rev = "0"
    else:
        total_text = f"{total:.2f}:1"
        out_per_rev = f"{1.0 / abs(total):.6f}" if abs(total) > EPS else "\u221e"

    direction = "\u2192" if total >= 0 else "\u2190"
    ratio_text.set_text(
        f"Base Stage Ratio: {base:.4f}:1     "
        f"Wolfrom Total: {direction} {total_text}     "
        f"\u0394D (D2\u2212D1): {delta_D:+.3f} mm     "
        f"Mismatch (1\u2212D1/D2): {mismatch:+.6f}     "
        f"Output rev/input rev: {out_per_rev}"
    )

# ---------------------------------------------------------------------------
# Ratio lock behaviour
# ---------------------------------------------------------------------------
def is_ratio_locked():
    return bool(lock_check.get_status()[0])


def apply_ratio_lock():
    global is_programmatic_update

    if not is_ratio_locked():
        return
    if is_programmatic_update:
        return

    g1 = get_stage1_geometry()

    try:
        required_D2 = solve_stage2_pcd_for_target(
            g1, target_ratio, larger_output_ring=larger_output_ring,
        )
    except Exception as exc:
        ratio_text.set_text(f"Invalid target ratio: {exc}")
        return

    if required_D2 < s2_D.valmin or required_D2 > s2_D.valmax:
        ratio_text.set_text(
            f"Required S2 Output PCD {required_D2:.3f} mm is outside slider range "
            f"[{s2_D.valmin}, {s2_D.valmax}]."
        )
        return

    is_programmatic_update = True
    try:
        old_eventson = s2_D.eventson
        s2_D.eventson = False
        s2_D.set_val(required_D2)
        s2_D.eventson = old_eventson
    finally:
        is_programmatic_update = False

    g2 = get_stage2_geometry()
    update_ratio_display(g1, g2)

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
def on_target_submit(text):
    global target_ratio
    try:
        target_ratio = abs(float(text))
    except ValueError:
        ratio_text.set_text("Invalid target ratio input.")
        return
    if is_ratio_locked():
        apply_ratio_lock()
    g1 = get_stage1_geometry()
    g2 = get_stage2_geometry()
    update_ratio_display(g1, g2)
    fig.canvas.draw_idle()


def on_lock_clicked(label):
    if is_ratio_locked():
        apply_ratio_lock()
    g1 = get_stage1_geometry()
    g2 = get_stage2_geometry()
    update_ratio_display(g1, g2)
    fig.canvas.draw_idle()


def on_direction_changed(label):
    global larger_output_ring
    larger_output_ring = (label.strip() == "D2 > D1")
    if is_ratio_locked():
        apply_ratio_lock()
    g1 = get_stage1_geometry()
    g2 = get_stage2_geometry()
    update_ratio_display(g1, g2)
    fig.canvas.draw_idle()


def on_any_slider_change(val):
    if is_programmatic_update:
        return
    if is_ratio_locked():
        apply_ratio_lock()
    g1 = get_stage1_geometry()
    g2 = get_stage2_geometry()
    update_ratio_display(g1, g2)
    fig.canvas.draw_idle()

# Register slider callbacks
for s in sliders.values():
    s.on_changed(on_any_slider_change)

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
sidebar_x = 0.025
sidebar_w = 0.135

fig.text(sidebar_x, 0.900, "Wolfrom Controls", fontsize=11, weight="bold", ha="left")

fig.text(sidebar_x, 0.850, "Target Ratio", fontsize=9, ha="left", va="bottom")
target_ax = fig.add_axes([sidebar_x, 0.810, sidebar_w, 0.040])
target_box = TextBox(target_ax, "", initial="200")
target_box.on_submit(on_target_submit)

lock_ax = fig.add_axes([sidebar_x, 0.725, sidebar_w, 0.060])
lock_check = CheckButtons(lock_ax, ["Lock Ratio"], [True])
lock_check.on_clicked(on_lock_clicked)

fig.text(sidebar_x, 0.675, "Output PCD Direction", fontsize=9, ha="left", va="bottom")
direction_ax = fig.add_axes([sidebar_x, 0.585, sidebar_w, 0.085])
direction_radio = RadioButtons(direction_ax, ["D2 > D1", "D2 < D1"], active=0)
direction_radio.on_clicked(on_direction_changed)

reset_ax = fig.add_axes([sidebar_x, 0.520, sidebar_w, 0.045])
reset_button = Button(reset_ax, "Reset", color=axcolor, hovercolor="0.975")
reset_button.label.set_fontsize(9)


def reset(event):
    global target_ratio, larger_output_ring, input_angle

    for s in sliders.values():
        s.reset()

    input_angle = 0.0
    target_ratio = 200.0
    target_box.set_val("200")
    larger_output_ring = True

    apply_ratio_lock()

    g1 = get_stage1_geometry()
    g2 = get_stage2_geometry()
    update_ratio_display(g1, g2)
    fig.canvas.draw_idle()


reset_button.on_clicked(reset)

# ---------------------------------------------------------------------------
# DXF Export button + status
# ---------------------------------------------------------------------------
last_export_path = None

export_ax = fig.add_axes([sidebar_x, 0.465, sidebar_w, 0.045])
export_button = Button(export_ax, "Export DXF", color=axcolor, hovercolor="0.975")
export_button.label.set_fontsize(9)

open_files_ax = fig.add_axes([sidebar_x, 0.410, sidebar_w, 0.045])
open_files_button = Button(open_files_ax, "Open Files", color=axcolor, hovercolor="0.975")
open_files_button.label.set_fontsize(9)

dxf_status_text = fig.text(sidebar_x, 0.020, DXF_UNITS_LABEL, fontsize=8, ha="left", va="bottom")

status_text = fig.text(sidebar_x, 0.008, "", fontsize=8, color="#444444")


def export_single_stage_dxf(g: StageGeometry, stage_label: str, output_path: Path):
    """Write one stage to a DXF file."""
    if ezdxf is None:
        raise RuntimeError("DXF export requires the ezdxf package.")

    phi = 0.0

    # Geometry at phi=0 (starting pose), using correct local angles
    inner_x, inner_y = get_inner_curve_points(g, phi=0.0, extra_world_angle=0.0)
    outer_x, outer_y = get_outer_curve_points(g, phi=0.0, output_ring_angle=0.0)
    pin_centers = get_outer_pin_centers(g, phi=0.0)
    drive_centers = get_drive_pin_centers(g, phi=0.0)

    doc = ezdxf.new(setup=True)
    doc.units = ezdxf.units.MM
    ms = doc.modelspace()

    # Layers
    layers = {
        "OUTER_RING": 5,             # blue
        "GREEN_COMPOUND_MEMBER": 3,  # green
        "DRIVE_PINS": 7,             # black/white
        "CENTER_CIRCLE": 1,          # red
    }
    for name, color in layers.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)

    # Outer ring pins
    pin_radius = g.d / 2.0
    for cx, cy in pin_centers:
        ms.add_circle((cx, cy), pin_radius, dxfattribs={"layer": "OUTER_RING"})

    # Drive pins
    drive_radius = g.rd
    for cx, cy in drive_centers:
        ms.add_circle((cx, cy), drive_radius, dxfattribs={"layer": "DRIVE_PINS"})

    # Center circle
    ms.add_circle((0.0, 0.0), g.Rd, dxfattribs={"layer": "CENTER_CIRCLE"})

    # Inner curve (green/lobed compound member)
    inner_points = list(zip(inner_x.tolist(), inner_y.tolist()))
    ms.add_lwpolyline(inner_points, close=True, dxfattribs={"layer": "GREEN_COMPOUND_MEMBER"})

    # Outer curve (blue ring profile)
    outer_points = list(zip(outer_x.tolist(), outer_y.tolist()))
    ms.add_lwpolyline(outer_points, close=True, dxfattribs={"layer": "OUTER_RING"})

    doc.saveas(output_path)


def _prompt_export_name_macos(title, default_name):
    """Ask for a file name via AppleScript (always on top on macOS)."""
    script = (
        f'tell application "System Events"\n'
        f'activate\n'
        f'display dialog "{title}:" default answer "{default_name}" '
        f'buttons {{"Cancel", "Export"}} default button "Export"\n'
        f'end tell'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, check=True,
        )
        text = result.stdout.strip()
        # Parse AppleScript output: "button returned:Export, text returned:filename"
        if "text returned:" in text:
            name = text.split("text returned:")[1].split(",")[0].strip()
            return name if name else None
        return None
    except subprocess.CalledProcessError:
        return None


def handle_export(event):
    global last_export_path
    g1 = get_stage1_geometry()
    g2 = get_stage2_geometry()

    try:
        base_name = _prompt_export_name_macos(
            "Export Wolfrom DXF",
            "wolfrom-drive",
        )
        if base_name is None:
            base_name = prompt_single_export_name(
                title="Export Wolfrom DXF",
                label="Base file name",
                default_name="wolfrom-drive",
            )
        if base_name is None:
            status_text.set_text("DXF export canceled.")
            status_text.set_color("#444444")
            fig.canvas.draw_idle()
            return

        export_dir = Path.home() / "Desktop" / DEFAULT_EXPORT_FOLDER
        export_dir.mkdir(parents=True, exist_ok=True)

        path1 = export_dir / f"{base_name}_Stage1.dxf"
        path2 = export_dir / f"{base_name}_Stage2.dxf"

        export_single_stage_dxf(g1, "Stage 1", path1)
        export_single_stage_dxf(g2, "Stage 2", path2)

        last_export_path = path1
        display = str(export_dir).replace(str(Path.home()), "~", 1)
        status_text.set_text(
            f"DXF exported: {path1.name} and {path2.name} \u2192 {display}"
        )
        status_text.set_color("#1b5e20")
    except Exception as error:
        status_text.set_text(f"DXF export failed: {error}")
        status_text.set_color("#8b0000")
        fig.canvas.draw_idle()


export_button.on_clicked(handle_export)


def handle_open_files(_event):
    """Open the export folder, or reveal the last-exported file in Finder."""
    if last_export_path is None:
        export_dir = default_export_directory(Path(__file__).resolve().parent)
        export_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(export_dir)], check=False)
        display = str(export_dir).replace(str(Path.home()), "~", 1)
        status_text.set_text(f"Opened export folder: {display}")
        status_text.set_color("#1b5e20")
        fig.canvas.draw_idle()
        return

    try:
        reveal_in_finder(last_export_path)
        status_text.set_text(f"Revealed in Finder: {last_export_path.name}")
        status_text.set_color("#1b5e20")
    except Exception as error:
        status_text.set_text(f"Finder reveal failed: {error}")
        status_text.set_color("#8b0000")
    fig.canvas.draw_idle()


open_files_button.on_clicked(handle_open_files)

# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------
def animate(_frame):
    global input_angle

    g1 = get_stage1_geometry()
    g2 = get_stage2_geometry()

    speed = float(s_speed.val)
    input_angle = (input_angle + speed * 2 * np.pi / 120.0) % (2 * np.pi * 1_000_000)

    phi = input_angle

    total = wolfrom_total_ratio(g1, g2)

    if np.isinf(total) or abs(total) < EPS:
        output_ring_angle = 0.0
    else:
        output_ring_angle = OUTPUT_VISUAL_SIGN * phi / total

    # Stage 1: fixed blue outer ring — no world rotation
    stage1_artist.draw(
        g1, phi,
        ring_world_angle=0.0,
        status="Fixed blue outer ring",
    )

    # Stage 2: entire solved mesh rotated by slow Wolfrom output angle
    stage2_artist.draw(
        g2, phi,
        ring_world_angle=output_ring_angle,
        status=f"Output ring angle: {np.degrees(output_ring_angle):.3f}\u00b0",
    )

    update_ratio_display(g1, g2)


ani = animation.FuncAnimation(
    fig, animate, frames=count(), interval=INTERVAL_MS, cache_frame_data=False,
)

# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------
apply_ratio_lock()
update_ratio_display(get_stage1_geometry(), get_stage2_geometry())
plt.show()
