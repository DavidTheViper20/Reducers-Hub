"""
Cycloidal Drive with Intermediate Rollers and Free Cage animation script + export to dxf.

YouTube: https://youtube.com/MishinMachine
Instagram: https://instagram.com/mishinmachine

Shoutout to @Tomato1107 for his original cycloidal-drive animation scripts.
Source: https://github.com/Tomato1107/Cycloidal-Drive-Animation
"""

import ezdxf as ezdxf
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider, Button
import numpy as np
import subprocess
import sys
from pathlib import Path

SHARED_UTILS_DIR = Path(__file__).resolve().parents[1]
if str(SHARED_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_UTILS_DIR))

from export_naming import build_export_path, prompt_single_export_name
from cycloidal_drive import default_export_directory, reveal_in_finder, DXF_UNITS_LABEL

# ------------------------------------------------------------------------
# Initial values
# ------------------------------------------------------------------------
INITIAL_D = 45.8               # separator diameter
INITIAL_d = 3                # pin diameter
INITIAL_e = INITIAL_d * 0.2  # eccentricity of the pins
INITIAL_n = 29               # number of pins
INITIAL_isd = 5.0            # input shaft diameter
INITIAL_ced = 15.0           # cam eccentric diameter
INITIAL_out_d = 1.0          # output pin diameter

RESOLUTION = 50             # Resolution per pin

# visual and  animation
DOT_SIZE = 4
INTERVAL = 50 # ms

# initial rotation angle
rotation_angle = 0

# ------------------------------------------------------------------------
# Plot setup
# ------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10.2, 8.3))
ax.grid()

# Set initial limits
ax.set_xlim(-10, 10)
ax.set_ylim(-10, 10)
ax.set_aspect('equal', 'box')

# Reserve space at the bottom for constols
plt.subplots_adjust(bottom=0.38, top=0.92)

ratio_title = ax.set_title(f"Reduction Ratio  {INITIAL_n}:1", fontsize=14, fontweight='bold', pad=10)

base_dot, = ax.plot([], [], 'o', ms=DOT_SIZE, color='gray')
base_circle = plt.Circle((INITIAL_e, 0),
                          radius=INITIAL_D/2,
                          fill=False,
                          linestyle='--',
                          edgecolor='gray',
                          linewidth=0.6)
ax.add_patch(base_circle)

cam_dot,       = ax.plot([], [], 'ro', ms=DOT_SIZE)
cam_gear, = ax.plot([], [], 'r-',
                    label='Cam Gear',
                    )

crown_gear, = ax.plot([], [], 'b-',
                      label='Crown Gear',
                      )

ishaft_dot, = ax.plot([], [], 'ko', ms=DOT_SIZE)
ishaft_circle = plt.Circle((0, 0),
                                radius=INITIAL_isd/2,
                                fill=False,
                                edgecolor='black',
                                linewidth=1.5)
ax.add_patch(ishaft_circle)


ecc_circle = plt.Circle((2*INITIAL_e, 0),
                        radius=INITIAL_ced/2,
                        fill=False,
                        edgecolor='red',
                        linewidth=1.5)
ax.add_patch(ecc_circle)

pins = []
output_pins = []
pin_dot, = ax.plot([], [], 'go', ms=5)

# ------------------------------------------------------------------------
# Draw functions
# ------------------------------------------------------------------------
def draw_pins(n, e, D, d, rotate = 0, offset = [0, 0]):
    pins = []
    R = D / 2 # base radius
    r = d / 2 # pin radius

    pinCos = np.cos(rotate / n)
    pinSin = np.sin(rotate / n)

    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    for angle in angles:
        xT = R * np.cos(angle) # + e
        yT = R * np.sin(angle)

        # Rotate the pin
        x = xT * pinCos - yT * pinSin + offset[0]
        y = xT * pinSin + yT * pinCos + offset[1]

        c = plt.Circle((x, y),
                       radius=r,
                       fill=False,
                       edgecolor='green',
                       linewidth=1.5)
        pins.append(c)
    return pins

def draw_output_pins(n, D, d, out_d, rotate = 0, offset = [0, 0]):
    """Black output pins — smaller circles within the green lobes."""
    output_pins = []
    R = D / 2       # base radius (same as green pins)
    r = out_d / 2   # output pin radius

    pinCos = np.cos(rotate / n)
    pinSin = np.sin(rotate / n)

    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    for angle in angles:
        xT = R * np.cos(angle)
        yT = R * np.sin(angle)

        # Rotate the pin
        x = xT * pinCos - yT * pinSin + offset[0]
        y = xT * pinSin + yT * pinCos + offset[1]

        c = plt.Circle((x, y),
                       radius=r,
                       fill=False,
                       edgecolor='black',
                       linewidth=1.5)
        output_pins.append(c)
    return output_pins

# Draw Hypocycloid or Epicycloid
def draw_cycloid(D, d, e, n, epicycloid = False, offset = [0,0], angle_rad = 0):
    sign = epicycloid and -1 or 1 # sign for outer or inner cycloid

    R = D / 2 # base radius
    r = d / 2 # pin radius

    Rn = (R / n)
    Rz = (n - sign * 1) * Rn
    Rzn = Rz + sign * Rn

    cosA = np.cos(angle_rad)
    sinA = np.sin(angle_rad)

    t = np.linspace(0, 2 * np.pi, RESOLUTION * n)

    sin_t = np.sin(t)
    cos_t = np.cos(t)

    factor = Rzn / Rn
    sin_factor_t = np.sin(factor * t)
    cos_factor_t = np.cos(factor * t)

    # Compute the base cycloid coordinates
    xa = Rzn * cos_t - sign * e * cos_factor_t
    ya = Rzn * sin_t - e * sin_factor_t

    dxa = Rzn * (-sin_t + sign * (e / Rn) * sin_factor_t)
    dya = Rzn * (cos_t - (e / Rn) * cos_factor_t)

    denom = np.sqrt(dxa**2 + dya**2)
    # Offset the cycloid coordinates along the normal direction
    xT = xa + sign * (r / denom) * (-dya)
    yT = ya + sign * (r / denom) * dxa

    # Rotate by angle_rad and then apply the offset
    x = xT * cosA - yT * sinA + offset[0]
    y = xT * sinA + yT * cosA + offset[1]

    return [x, y]

def draw_cam(D, d, e, n, angle = 0):
    # angle = angle + np.pi / (n - 1) # if cam is not eccentric
    off = 2 * e
    offX = off * np.cos(-angle)
    offY = off * np.sin(-angle)

    return draw_cycloid(D, d, e, n, False, [offX, offY], angle / ((n-1)/2))

def draw_crown(D, d, e, n, angle = 0):
    return draw_cycloid(D, d, e, n, True, [0, 0], angle)

# ------------------------------------------------------------------------
# Updates
# ------------------------------------------------------------------------
def update_slider_limits ():
    D_val = D_slider.val
    d_val = d_slider.val
    e_val = e_slider.val


    min_D = d_val * 2
    D_slider.valmin = min_D
    D_slider.ax.set_xlim(D_slider.valmin, D_slider.valmax)
    if D_val < min_D:
        D_slider.set_val(min_D)
        D_val = min_D

    max_d = D_val / 2
    d_slider.valmax = max_d
    d_slider.ax.set_xlim(d_slider.valmin, d_slider.valmax)
    if d_slider.val > max_d:
        d_slider.set_val(max_d)
        d_val = max_d

    max_e = round((min(d_val, max_d) / 4), 1)
    e_slider.valmax = max_e
    e_slider.ax.set_xlim(e_slider.valmin, e_slider.valmax)
    if e_slider.val > max_e:
        e_slider.set_val(max_e)
        e_val = max_e

    n_max = np.ceil((np.pi * (D_val - e_val * 2)) / (d_val))
    n_slider.valmax = n_max
    n_slider.ax.set_xlim(n_slider.valmin, n_slider.valmax)
    if n_slider.val > n_max:
        n_slider.set_val(n_max)

    isd_max = D_val - d_val - e_val*5 - 2
    isd_slider.valmax = isd_max
    isd_slider.ax.set_xlim(isd_slider.valmin, isd_slider.valmax)

    if isd_slider.val > isd_max:
        isd_slider.set_val(isd_max)

    ced_min = isd_slider.val + e_val * 5
    ced_max = D_val - d_val - e_val * 2 - 1

    if ced_min > ced_max:
        ced_min = ced_max

    ced_slider.valmin = ced_min
    ced_slider.valmax = ced_max
    ced_slider.ax.set_xlim(ced_min, ced_slider.valmax)

    if ced_slider.val < ced_min:
        ced_slider.set_val(ced_min)

    if ced_slider.val > ced_max:
        ced_slider.set_val(ced_max)

    out_d_max = d_val
    out_d_slider.valmax = out_d_max
    out_d_slider.ax.set_xlim(out_d_slider.valmin, out_d_slider.valmax)
    if out_d_slider.val > out_d_max:
        out_d_slider.set_val(out_d_max)

def update(_):
    update_slider_limits()

    D_val = D_slider.val
    d_val = d_slider.val
    e_val = e_slider.val
    n_val = int(n_slider.val)
    isd_val = isd_slider.val
    ced_val = ced_slider.val

    ratio_title.set_text(f"Reduction Ratio  {n_val}:1")

    angle = rotation_angle / 180 * np.pi

    cosA = np.cos(angle)
    sinA = np.sin(angle)

    eccOffX = e_val * cosA
    eccOffY = e_val * -sinA

    # Separator circle
    base_r = D_val / 2
    base_circle.center = (eccOffX, eccOffY)
    base_circle.set_radius(base_r)
    base_circle.set_linestyle('--')  # dashed

    # Cam gear
    cam_points = draw_cam(D_val, d_val, e_val, n_val, angle )
    cam_gear.set_data(cam_points[0], cam_points[1])
    cam_dot.set_data([cam_points[0][0]], [cam_points[1][0]])

    # Crown gear
    crown_points = draw_crown(D_val, d_val, e_val, n_val)
    crown_gear.set_data(crown_points[0], crown_points[1])

    # Input shaft
    isr = isd_val / 2
    ishaft_circle.set_radius(isr)
    ishaft_dot.set_data([isr * cosA], [isr * -sinA])

    # Cam eccentric circle
    ecc_circle.center = (eccOffX * 2, eccOffY * 2)
    ecc_circle.set_radius(ced_val / 2)

    # Remove old pins from the plot
    for p in pins:
        p.remove()
    pins.clear()

    # Create new pins
    new_pins = draw_pins(n_val, e_val, D_val, d_val, angle, [eccOffX, eccOffY])
    pins.extend(new_pins)
    for p in pins:
        ax.add_patch(p)

    # Remove old output pins from the plot
    for p in output_pins:
        p.remove()
    output_pins.clear()

    # Create new output pins (black, off-center from green lobes, orbiting centrally)
    out_d_val = out_d_slider.val
    new_output_pins = draw_output_pins(n_val, D_val, d_val, out_d_val, angle, [0, 0])
    output_pins.extend(new_output_pins)
    for p in output_pins:
        ax.add_patch(p)

    pinX = pins[0].center[0]
    pinY = pins[0].center[1]

    pin_r = d_val / 2
    base_dot.set_data([pinX], [pinY])
    pin_dot.set_data([pinX + pin_r * cosA ], [pinY + pin_r * -sinA])

    # Adjust plot limits so everything is visible
    body_D = D_val + d_val + e_val * 2

    lim = body_D/2 + 1
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)

    ax.set_aspect('equal', 'box')
    fig.canvas.draw_idle()

# ------------------------------------------------------------------------
# Sliders
# ------------------------------------------------------------------------
slider_width = 0.65
slider_height = 0.03

D_ax = plt.axes([0.2, 0.30, slider_width, slider_height])
d_ax = plt.axes([0.2, 0.26, slider_width, slider_height])
e_ax = plt.axes([0.2, 0.22, slider_width, slider_height])
n_ax = plt.axes([0.2, 0.18, slider_width, slider_height])
isd_ax = plt.axes([0.2, 0.14, slider_width, slider_height])
ced_ax = plt.axes([0.2, 0.10, slider_width, slider_height])
out_d_ax = plt.axes([0.2, 0.06, slider_width, slider_height])

D_slider = Slider(D_ax, 'Pins base: D', 10, 200.0, valinit=INITIAL_D, valstep=0.5)
d_slider = Slider(d_ax, 'Pin dia: d',       1, 20,  valinit=INITIAL_d, valstep=0.5)
e_slider = Slider(e_ax, 'Eccentricity: e',      0.1, 5.0,  valinit=INITIAL_e, valstep=0.1)
n_slider = Slider(n_ax, 'Pins num: n',     3,   50,   valinit=INITIAL_n, valstep=1)
isd_slider = Slider(isd_ax, 'Input shaft dia: isd',   0.1, 20.0, valinit=INITIAL_isd, valstep=0.1)
ced_slider = Slider(ced_ax, 'Cam ecc dia: ced',   0.1, 20.0, valinit=INITIAL_ced, valstep=0.1)
out_d_slider = Slider(out_d_ax, 'Output pin dia: out_d', 0.1, 10.0, valinit=INITIAL_out_d, valstep=0.1)

D_slider.on_changed(update)
d_slider.on_changed(update)
e_slider.on_changed(update)
n_slider.on_changed(update)
isd_slider.on_changed(update)
ced_slider.on_changed(update)
out_d_slider.on_changed(update)


# ------------------------------------------------------------------------
# Controls & Export
# ------------------------------------------------------------------------
AXIS_COLOR = "lightgoldenrodyellow"
STATUS_TEXT_COLOR = "#444444"
STATUS_SUCCESS_COLOR = "#1b5e20"
STATUS_ERROR_COLOR = "#8b0000"

reset_btn = Button(plt.axes([0.20, 0.01, 0.10, 0.04]), 'Reset', color="#EEEEEE", hovercolor='0.975')
open_btn = Button(plt.axes([0.31, 0.01, 0.12, 0.04]), 'Open\nFiles', color=AXIS_COLOR, hovercolor='0.975')
export_btn = Button(plt.axes([0.44, 0.01, 0.14, 0.04]), 'Export DXF', color=AXIS_COLOR, hovercolor='0.975')
open_btn.label.set_fontsize(9)
status_text = plt.text(0.5, 0.055, '', ha='center', va='center', fontsize=10, transform=plt.gcf().transFigure)
units_text = plt.text(0.02, 0.005, DXF_UNITS_LABEL, fontsize=9, color=STATUS_TEXT_COLOR, transform=plt.gcf().transFigure)

export_state = {"last_export_path": None}


def format_path_for_display(path: Path) -> str:
    try:
        return str(path).replace(str(Path.home()), "~", 1)
    except Exception:
        return str(path)


def reset(_):
    global rotation_angle
    rotation_angle = 0

    D_slider.reset()
    d_slider.reset()
    e_slider.reset()
    n_slider.reset()
    isd_slider.reset()
    ced_slider.reset()
    out_d_slider.reset()

    status_text.set_text("")
    update(_)

reset_btn.on_clicked(reset)


def _prompt_export_name_macos(title, default_name):
    """Use AppleScript dialog on macOS — more reliable than Tk with Matplotlib."""
    escaped_default = default_name.replace('"', '\\"')
    script = f'''
    tell application "System Events"
        activate
        set userInput to text returned of (display dialog "DXF file name:" default answer "{escaped_default}" with title "{title}" buttons {{"Cancel", "Export"}} default button "Export")
        return userInput
    end tell
    '''
    try:
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=True)
        name = result.stdout.strip()
        return name if name else None
    except subprocess.CalledProcessError:
        return None


def handle_export(_):
    D_val = D_slider.val
    d_val = d_slider.val
    e_val = e_slider.val
    n_val = int(n_slider.val)
    isd_val = isd_slider.val
    ced_val = ced_slider.val
    out_d_val = out_d_slider.val

    status_text.set_text("Getting file name... ")
    status_text.set_color(STATUS_TEXT_COLOR)
    fig.canvas.draw_idle()

    # Try AppleScript first (more reliable on macOS), fall back to Tkinter
    try:
        file_name = _prompt_export_name_macos(
            "Export Cycloidal Roller Drive DXF",
            "cycloidal-roller-drive",
        )
    except Exception:
        file_name = prompt_single_export_name(
            title="Export Cycloidal Roller Drive DXF",
            label="DXF file name",
            default_name="cycloidal-roller-drive",
        )

    if file_name is None:
        status_text.set_text("DXF export canceled.")
        status_text.set_color(STATUS_TEXT_COLOR)
        fig.canvas.draw_idle()
        return

    status_text.set_text("Saving... ")
    status_text.set_color(STATUS_TEXT_COLOR)
    fig.canvas.draw_idle()

    try:
        doc = ezdxf.new("R2018")
        doc.units = ezdxf.units.MM
        msp = doc.modelspace()

        # Separator circle
        msp.add_circle((e_val, 0), radius=D_val / 2)

        # Cam gear
        cam_points = draw_cam(D_val, d_val, e_val, n_val)
        msp.add_lwpolyline(np.stack(cam_points, axis=1))

        # Crown gear
        crown_points = draw_crown(D_val, d_val, e_val, n_val)
        msp.add_lwpolyline(np.stack(crown_points, axis=1))

        # Pins (green intermediate rollers)
        R = D_val / 2
        r = d_val / 2
        angles = np.linspace(0, 2*np.pi, n_val, endpoint=False)
        for angle in angles:
            x = R * np.cos(angle) + e_val
            y = R * np.sin(angle)
            msp.add_circle((x, y), radius=r)

        # Output pins (black, off-center from green lobes)
        r_out = out_d_val / 2
        for angle in angles:
            x = R * np.cos(angle)
            y = R * np.sin(angle)
            msp.add_circle((x, y), radius=r_out)

        # Input shaft
        msp.add_circle((0, 0), radius=isd_val / 2)

        # Eccentric circle
        msp.add_circle((2 * e_val, 0), radius=ced_val / 2)

        export_dir = default_export_directory(Path(__file__).resolve().parent)
        output_path = build_export_path(export_dir, "cycloidal-roller-drive", file_name=file_name)
        doc.saveas(str(output_path))

        export_state["last_export_path"] = output_path
        export_location = format_path_for_display(output_path.parent)
        status_text.set_text(f"DXF exported to {export_location}")
        status_text.set_color(STATUS_SUCCESS_COLOR)
        print(f"DXF exported to {output_path}")
    except Exception as error:
        status_text.set_text(f"DXF export failed: {error}")
        status_text.set_color(STATUS_ERROR_COLOR)
        print(f"DXF export failed: {error}")

    fig.canvas.draw_idle()

export_btn.on_clicked(handle_export)


def handle_open_file_location(_):
    if export_state["last_export_path"] is None:
        export_directory = default_export_directory(Path(__file__).resolve().parent)
        export_directory.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(export_directory)], check=False)
        status_text.set_text(f"Opened export folder: {format_path_for_display(export_directory)}")
        status_text.set_color(STATUS_SUCCESS_COLOR)
        fig.canvas.draw_idle()
        return

    try:
        reveal_in_finder(export_state["last_export_path"])
        status_text.set_text(f"Revealed in Finder: {export_state['last_export_path'].name}")
        status_text.set_color(STATUS_SUCCESS_COLOR)
    except Exception as error:
        status_text.set_text(f"Finder reveal failed: {error}")
        status_text.set_color(STATUS_ERROR_COLOR)

    fig.canvas.draw_idle()

open_btn.on_clicked(handle_open_file_location)


# ------------------------------------------------------------------------
# Initialize
# ------------------------------------------------------------------------
step = 20
def animate(_):
    global rotation_angle
    n = int(n_slider.val)
    rotation_angle = (rotation_angle + step) % (360 * n)
    update(_)

ani = animation.FuncAnimation(fig, animate, frames=int(360/step), interval=INTERVAL, repeat=True)

plt.show()
