# Novel Reducers — shared demo framework
#
# A small, dependency-light framework so every "novel reducer" demo in this
# family looks and behaves consistently:
#   * a single large, equal-aspect plot on the right
#   * a tidy vertical stack of sliders on the left
#   * Reset / Export DXF / Open Files buttons
#   * a live readout line (ratio / status)
#   * a smooth animation loop with a speed control
#
# A mechanism module only has to describe its parameters and provide a
# ``compute(values, phase)`` function that returns a list of drawable items.
# The framework owns all the matplotlib plumbing.
#
# Crucially, the plot view limits are recomputed by *sampling the motion over a
# full cycle whenever a slider changes* (not every frame). That keeps the
# geometry centred and fully visible for any parameter combination, so sliders
# can never push the drawing off-screen or make it jitter.

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
import subprocess
import sys

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider, Button

try:
    import ezdxf
except ImportError:  # pragma: no cover - export simply disabled without ezdxf
    ezdxf = None

EPS = 1e-9
AXCOLOR = "lightgoldenrodyellow"
SUCCESS = "#1b5e20"
ERROR = "#8b0000"
NEUTRAL = "#444444"
_CIRCLE_T = np.linspace(0.0, 2.0 * np.pi, 160)
DEFAULT_EXPORT_FOLDER = "Novel Reducer Exports"


def export_directory() -> Path:
    return Path.home() / "Desktop" / DEFAULT_EXPORT_FOLDER


# ---------------------------------------------------------------------------
# Scene item constructors (what a mechanism's compute() returns)
# ---------------------------------------------------------------------------
def path(x, y, color="#1f77b4", lw=1.8, closed=False, dxf=True, dxf_layer="GEOMETRY"):
    """A polyline. ``closed`` joins the last point back to the first."""
    return {
        "type": "path",
        "x": np.asarray(x, dtype=float),
        "y": np.asarray(y, dtype=float),
        "color": color,
        "lw": lw,
        "closed": closed,
        "dxf": dxf,
        "dxf_layer": dxf_layer,
    }


def circles(centers, r, color="#2ca02c", lw=1.2, dxf=True, dxf_layer="CIRCLES"):
    """A set of circle outlines of equal radius (pins, rollers, balls...)."""
    return {
        "type": "circles",
        "centers": [(float(cx), float(cy)) for cx, cy in centers],
        "r": float(r),
        "color": color,
        "lw": lw,
        "dxf": dxf,
        "dxf_layer": dxf_layer,
    }


def dot(x, y, color="#d62728", ms=6):
    """A small marker (never exported to DXF)."""
    return {"type": "dot", "x": float(x), "y": float(y), "color": color, "ms": ms}


def segment(p0, p1, color="#555555", lw=1.5, dxf=False, dxf_layer="GEOMETRY"):
    """A straight line between two points (links, cables, axes)."""
    return path([p0[0], p1[0]], [p0[1], p1[1]], color=color, lw=lw, closed=False,
                dxf=dxf, dxf_layer=dxf_layer)


# ---------------------------------------------------------------------------
# Parameter specification
# ---------------------------------------------------------------------------
@dataclass
class Param:
    key: str
    label: str
    vmin: float
    vmax: float
    vinit: float
    step: float = 0.0
    integer: bool = False
    fmt: str = "%.2f"

    def cast(self, value):
        return int(round(value)) if self.integer else float(value)


@dataclass
class MechanismDemo:
    title: str
    subtitle: str
    params: list
    compute: object                 # compute(values: dict, phase: float) -> list[item]
    readout: object = None          # readout(values, phase) -> str  (optional)
    units: str = "millimeters (mm)"
    export_name: str = "novel-reducer"
    phase_per_frame: float = 2 * np.pi / 180.0
    figsize: tuple = (13.5, 8.0)

    # populated by build()
    fig: object = field(default=None, init=False)
    ax: object = field(default=None, init=False)
    sliders: dict = field(default_factory=dict, init=False)
    _phase: float = field(default=0.0, init=False)

    # -- public ------------------------------------------------------------
    def values(self) -> dict:
        return {p.key: p.cast(self.sliders[p.key].val) for p in self.params}

    def build(self):
        self.fig = plt.figure(figsize=self.figsize, dpi=100)
        try:
            self.fig.canvas.manager.set_window_title(f"{self.title} — Novel Reducers")
        except Exception:
            pass

        self.ax = self.fig.add_axes([0.34, 0.30, 0.62, 0.62])
        self.ax.set_aspect("equal")
        self.ax.set_title(self.title, fontsize=12, pad=8)
        self.ax.grid(True, color="#eeeeee")

        self._path_pool = []
        self._circle_pool = []
        self._dot_pool = []

        self.fig.text(0.03, 0.945, self.title, fontsize=13, weight="bold")
        self.fig.text(0.03, 0.915, self.subtitle, fontsize=8.5, color=NEUTRAL, wrap=True)

        self._build_sliders()
        self._build_buttons()

        self.readout_text = self.fig.text(
            0.34, 0.95, "", ha="left", va="bottom", fontsize=10, family="monospace",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.9),
        )
        self.status_text = self.fig.text(0.03, 0.02, "", fontsize=8.5, color=NEUTRAL)
        self.fig.text(0.03, 0.045, f"DXF units: {self.units}.", fontsize=8.5, color=NEUTRAL)

        self._last_export = None
        self._refit_limits()
        self._render(self._phase)
        self._ani = animation.FuncAnimation(
            self.fig, self._tick, frames=count(), interval=50, cache_frame_data=False,
        )
        return self

    def show(self):
        if self.fig is None:
            self.build()
        plt.show()

    # -- internal: layout --------------------------------------------------
    def _build_sliders(self):
        x = 0.06
        w = 0.20
        top = 0.84
        bottom = 0.20
        all_specs = list(self.params) + [
            Param("__speed__", "Animation Speed ×", 0.0, 6.0, 1.0, 0.05, fmt="%.2f")
        ]
        n = len(all_specs)
        step = (top - bottom) / max(n - 1, 1) if n > 1 else 0.0
        for i, spec in enumerate(all_specs):
            y = top - i * step
            ax_s = self.fig.add_axes([x, y, w, 0.018], facecolor=AXCOLOR)
            valstep = spec.step if spec.step > 0 else None
            if spec.integer and valstep is None:
                valstep = 1
            slider = Slider(ax_s, spec.label, spec.vmin, spec.vmax,
                            valinit=spec.vinit, valstep=valstep, valfmt=spec.fmt)
            slider.label.set_fontsize(8)
            slider.valtext.set_fontsize(8)
            slider.on_changed(self._on_slider)
            self.sliders[spec.key] = slider
        self._speed_key = "__speed__"

    def _build_buttons(self):
        bw, bh = 0.085, 0.04
        y = 0.10
        ax_reset = self.fig.add_axes([0.06, y, bw, bh])
        ax_export = self.fig.add_axes([0.155, y, bw, bh])
        ax_open = self.fig.add_axes([0.25, y, 0.05, bh])
        self.reset_button = Button(ax_reset, "Reset", color=AXCOLOR, hovercolor="0.95")
        self.export_button = Button(ax_export, "Export DXF", color=AXCOLOR, hovercolor="0.95")
        self.open_button = Button(ax_open, "Open\nFiles", color=AXCOLOR, hovercolor="0.95")
        for b in (self.reset_button, self.export_button, self.open_button):
            b.label.set_fontsize(8.5)
        self.reset_button.on_clicked(self._on_reset)
        self.export_button.on_clicked(self._on_export)
        self.open_button.on_clicked(self._on_open)

    # -- internal: callbacks ----------------------------------------------
    def _on_slider(self, _val):
        self._refit_limits()
        self._render(self._phase)
        self.fig.canvas.draw_idle()

    def _on_reset(self, _event):
        for s in self.sliders.values():
            s.reset()
        self._phase = 0.0
        self._refit_limits()
        self._render(self._phase)
        self.fig.canvas.draw_idle()

    def _on_export(self, _event):
        if ezdxf is None:
            self._set_status("DXF export needs the ezdxf package.", ERROR)
            return
        try:
            name = self._prompt_name()
            if name is None:
                self._set_status("DXF export canceled.", NEUTRAL)
                return
            out_dir = export_directory()
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{name}.dxf"
            self._write_dxf(out_path)
            self._last_export = out_path
            shown = str(out_dir).replace(str(Path.home()), "~", 1)
            self._set_status(f"DXF exported: {out_path.name} → {shown}", SUCCESS)
        except Exception as error:  # noqa: BLE001 - surface to the user
            self._set_status(f"DXF export failed: {error}", ERROR)

    def _on_open(self, _event):
        out_dir = export_directory()
        out_dir.mkdir(parents=True, exist_ok=True)
        target = self._last_export if self._last_export else out_dir
        for opener in ("open", "xdg-open"):
            try:
                subprocess.run([opener, str(target)], check=False)
                break
            except FileNotFoundError:
                continue
        self._set_status(f"Opened {str(target).replace(str(Path.home()), '~', 1)}", SUCCESS)

    def _prompt_name(self):
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from export_naming import prompt_single_export_name
            return prompt_single_export_name(
                title=f"Export {self.title} DXF",
                label="Base file name",
                default_name=self.export_name,
            )
        except Exception:
            from datetime import datetime
            return f"{self.export_name}-{datetime.now():%Y%m%d-%H%M%S}"

    def _set_status(self, message, color):
        self.status_text.set_text(message)
        self.status_text.set_color(color)
        self.fig.canvas.draw_idle()

    # -- internal: animation / rendering ----------------------------------
    def _tick(self, _frame):
        speed = float(self.sliders[self._speed_key].val)
        self._phase = (self._phase + speed * self.phase_per_frame) % (2 * np.pi * 1_000_000)
        self._render(self._phase)

    def _scene(self, phase):
        try:
            return list(self.compute(self.values(), phase)) or []
        except Exception:
            return []

    def _render(self, phase):
        scene = self._scene(phase)
        pi = ci = di = 0
        for item in scene:
            kind = item["type"]
            if kind == "path":
                line = self._get(self._path_pool, pi); pi += 1
                x, y = item["x"], item["y"]
                if item.get("closed") and x.size:
                    x = np.append(x, x[0]); y = np.append(y, y[0])
                line.set_data(x, y)
                line.set_color(item["color"]); line.set_linewidth(item["lw"])
                line.set_visible(True)
            elif kind == "circles":
                r = item["r"]
                for cx, cy in item["centers"]:
                    line = self._get(self._circle_pool, ci); ci += 1
                    line.set_data(cx + r * np.cos(_CIRCLE_T), cy + r * np.sin(_CIRCLE_T))
                    line.set_color(item["color"]); line.set_linewidth(item["lw"])
                    line.set_visible(True)
            elif kind == "dot":
                line = self._get(self._dot_pool, di, marker=True); di += 1
                line.set_data([item["x"]], [item["y"]])
                line.set_color(item["color"]); line.set_markersize(item["ms"])
                line.set_visible(True)
        for pool, used in ((self._path_pool, pi), (self._circle_pool, ci), (self._dot_pool, di)):
            for j in range(used, len(pool)):
                pool[j].set_visible(False)
        if self.readout is not None:
            try:
                self.readout_text.set_text(self.readout(self.values(), phase))
            except Exception:
                pass

    def _get(self, pool, index, marker=False):
        while index >= len(pool):
            if marker:
                (line,) = self.ax.plot([], [], "o")
            else:
                (line,) = self.ax.plot([], [], "-")
            pool.append(line)
        return pool[index]

    def _refit_limits(self):
        xs, ys = [], []
        for phase in np.linspace(0.0, 2 * np.pi, 13):
            for item in self._scene(phase):
                if item["type"] == "path" and item["x"].size:
                    xs.append(item["x"]); ys.append(item["y"])
                elif item["type"] == "circles":
                    r = item["r"]
                    for cx, cy in item["centers"]:
                        xs.append(np.array([cx - r, cx + r]))
                        ys.append(np.array([cy - r, cy + r]))
        if not xs:
            return
        x_all = np.concatenate(xs); y_all = np.concatenate(ys)
        x_all = x_all[np.isfinite(x_all)]; y_all = y_all[np.isfinite(y_all)]
        if x_all.size == 0 or y_all.size == 0:
            return
        cx = 0.5 * (x_all.min() + x_all.max())
        cy = 0.5 * (y_all.min() + y_all.max())
        half = 0.55 * max(x_all.max() - x_all.min(), y_all.max() - y_all.min(), 1.0)
        self.ax.set_xlim(cx - half, cx + half)
        self.ax.set_ylim(cy - half, cy + half)

    # -- internal: DXF -----------------------------------------------------
    def _write_dxf(self, out_path):
        doc = ezdxf.new(setup=True)
        doc.units = ezdxf.units.MM
        msp = doc.modelspace()
        layers = set()
        for item in self._scene(0.0):
            if not item.get("dxf", True):
                continue
            layer = item.get("dxf_layer", "GEOMETRY")
            if layer not in layers and layer not in doc.layers:
                doc.layers.add(layer)
                layers.add(layer)
            if item["type"] == "path":
                pts = list(zip(item["x"].tolist(), item["y"].tolist()))
                if len(pts) >= 2:
                    msp.add_lwpolyline(pts, close=item.get("closed", False),
                                       dxfattribs={"layer": layer})
            elif item["type"] == "circles":
                for cx, cy in item["centers"]:
                    msp.add_circle((cx, cy), item["r"], dxfattribs={"layer": layer})
        doc.saveas(out_path)
