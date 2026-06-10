import ezdxf  # Ensure installed: pip install ezdxf
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider, Button, TextBox
import argparse
import json
import os

# ========== Command Line Arguments ==========
parser = argparse.ArgumentParser()
parser.add_argument('--fm', type=float, default=50)
parser.add_argument('--Rm', type=float, default=5)
parser.add_argument('--n', type=int, default=6)
parser.add_argument('--Rd', type=float, default=20)
parser.add_argument('--rd', type=float, default=5)
parser.add_argument('--e', type=float, default=2)
parser.add_argument('--N', type=int, default=10)
parser.add_argument('--d', type=float, default=10)
parser.add_argument('--D', type=float, default=80)
args = parser.parse_args()

# ========== Global Parameters ==========
t = np.linspace(0, 2*np.pi, 5000)
expression_text = ""
output_flag = False

# ========== Figure Setup ==========
fig, ax = plt.subplots(figsize=(6,6))
plt.subplots_adjust(left=0.15, bottom=0.45)
ax.set_aspect('equal')

# ========== Control Area ==========
slider_names = ['fm', 'Rm', 'n', 'Rd', 'rd', 'e', 'N', 'd', 'D']
slider_axes = {
    name: plt.axes([0.25, 0.23 - 0.025 * i, 0.5, 0.02], facecolor='lightgoldenrodyellow')
    for i, name in enumerate(slider_names)
}
sliders = {
    'fm': Slider(slider_axes['fm'], 'fm', 10, 100, valinit=args.fm, valstep=1),
    'Rm': Slider(slider_axes['Rm'], 'Rm', 1, 10, valinit=args.Rm, valstep=0.1),
    'n': Slider(slider_axes['n'], 'n', 3, 20, valinit=args.n, valstep=1),
    'Rd': Slider(slider_axes['Rd'], 'Rd', 1, 40, valinit=args.Rd, valstep=0.1),
    'rd': Slider(slider_axes['rd'], 'rd', 1, 10, valinit=args.rd, valstep=0.1),
    'e': Slider(slider_axes['e'], 'e', 0.1, 10, valinit=args.e, valstep=0.1),
    'N': Slider(slider_axes['N'], 'N', 3, 40, valinit=args.N, valstep=1),
    'd': Slider(slider_axes['d'], 'd', 2, 20, valinit=args.d, valstep=0.1),
    'D': Slider(slider_axes['D'], 'D', 5, 200, valinit=args.D, valstep=1),
}

# ========== Expression Output Box ==========
expr_ax = plt.axes([0.15, 0.30, 0.80, 0.10])
expr_box = TextBox(expr_ax, 'Expression', initial="Click 'Output Expression' to generate")
expr_box.text_disp.set_fontsize(6.)

# ========== All Graphical Elements ==========
num_pins = 61
pins = [ax.plot([], [], 'k-')[0] for _ in range(num_pins)]

num_inner_pins = 10
inner_pins = [ax.plot([], [], 'g-')[0] for _ in range(num_inner_pins)]

d0, = ax.plot([], [], 'k-')  # Drive circle
num_inner_circles = 10
inner_circles = [ax.plot([], [], 'r-')[0] for _ in range(num_inner_circles)]

inner_pin, = ax.plot([], [], 'r-')
dot, = ax.plot([], [], 'ro', ms=5)
ehypocycloid, = ax.plot([], [], 'r-')
edot, = ax.plot([], [], 'ro', ms=5)

# ========== Control Buttons ==========
btn_expr = Button(plt.axes([0.82, 0.03, 0.14, 0.04]), 'Expression', color='lightyellow')
btn_anim = Button(plt.axes([0.82, 0.08, 0.14, 0.04]), 'Animation', color='lightblue')
btn_export_dxf = Button(plt.axes([0.82, 0.18, 0.14, 0.04]), 'DXF_Sketch', color='lightcoral')
btn_reset  = Button(plt.axes([0.82, 0.13, 0.14, 0.04]), 'Reset', color='lightgreen')

# ========== Parameters and Updates ==========
def get_params():
    return {k: (int(v.val) if k in ['n', 'N'] else v.val) for k, v in sliders.items()}

def export_expression(event=None):
    global output_flag
    output_flag = True

def export_animation(event=None):
    print("Generating animation, please wait...")
    p = get_params()
    ani = animation.FuncAnimation(fig, animate, frames=int(p['fm'] * (p['N'] - 1)), interval=50)
    # Select save format
    try:
        ani.save("output.gif", writer='pillow', fps=20)
        print("Animation saved as output.gif")
    except:
        try:
            ani.save("output.mp4", writer='ffmpeg', fps=20)
            print("Animation saved as output.mp4")
        except Exception as e:
            print("Animation export failed:", e)

def reset_sliders(event): [s.reset() for s in sliders.values()]

def export_dxf_sketch(event=None):
    print("Exporting DXF sketch...")
    p = get_params()
    phi = 0  # Default to initial state

    RD, rd_half = p['D']/2, p['d']/2
    rc = (p['N'] - 1)*(RD / p['N'])
    rm = RD / p['N']
    r_drive = p['Rm']
    r_ecc = p['e']

    # Create DXF document
    doc = ezdxf.new()
    doc.units = ezdxf.units.MM  # Set to millimeters
    msp = doc.modelspace()
    # Create layers
    doc.layers.new(name='Cycloid', dxfattribs={'color': 1})       # Red
    doc.layers.new(name='Pins', dxfattribs={'color': 3})          # Green
    doc.layers.new(name='Eccentric', dxfattribs={'color': 5})     # Blue
    doc.layers.new(name='DriveCircle', dxfattribs={'color': 6})   # Cyan
    doc.layers.new(name='Center', dxfattribs={'color': 8})        # Gray

    # ========== 1. Cycloid Profile ==========
    xa = (rc + rm) * np.cos(t) - r_ecc * np.cos((rc + rm)/rm * t)
    ya = (rc + rm) * np.sin(t) - r_ecc * np.sin((rc + rm)/rm * t)

    dxa = (rc+rm)*(-np.sin(t)+(r_ecc/rm)*np.sin((rc+rm)/rm*t))
    dya = (rc+rm)*(np.cos(t)-(r_ecc/rm)*np.cos((rc+rm)/rm*t))

    norm = np.sqrt(dxa**2 + dya**2)
    x_a = xa - rd_half*dya/norm + r_ecc*np.cos(phi)
    y_a = ya + rd_half*dxa/norm + r_ecc*np.sin(phi)

    msp.add_lwpolyline(list(zip(x_a, y_a)), close=True, dxfattribs={'layer': 'Cycloid'})

    # ========== 2. Pin Holes (Outer Ring) ==========
    for i in range(p['N']):
        angle = 2 * np.pi * i / p['N']
        cx = RD * np.cos(angle)
        cy = RD * np.sin(angle)
        msp.add_circle((cx, cy), rd_half, dxfattribs={'layer': 'Center'})

    # ========== 3. Eccentric Wheel ==========
    ecc_x = r_ecc * np.cos(phi)
    ecc_y = r_ecc * np.sin(phi)
    msp.add_circle((ecc_x, ecc_y), r_drive+r_ecc, dxfattribs={'layer': 'Eccentric'})

    # ========== 4. Drive Circle ==========
    msp.add_circle((0, 0), r_drive, dxfattribs={'layer': 'DriveCircle'})

    # ========== 5. Inner Pins (Green) ==========
    for i in range(p['n']):
        angle = 2 * np.pi * i / p['n']
        cx = p['Rd'] * np.cos(angle)
        cy = p['Rd'] * np.sin(angle)
        msp.add_circle((cx, cy),  p['rd'], dxfattribs={'layer': 'Pins'})

    # ========== 6. Inner Ring Circles (Red) ==========
    for i in range(p['n']):
        angle = 2 * np.pi * i / p['n']
        cx = p['Rd'] * np.cos(angle)
        cy = p['Rd'] * np.sin(angle)
        msp.add_circle((cx+ r_ecc * np.cos(phi), cy+ r_ecc * np.sin(phi)),  p['rd'] + r_ecc, dxfattribs={'layer': 'Cycloid'})

    # Save DXF file
    doc.saveas("all_geometry_export.dxf")
    print("Sketch saved as all_geometry_export.dxf")

# Connect button events
btn_expr.on_clicked(export_expression)
btn_anim.on_clicked(export_animation)
btn_reset.on_clicked(reset_sliders)
btn_export_dxf.on_clicked(export_dxf_sketch)

# ========== Drawing Functions ==========
def draw_pin_init():
    for p in pins: p.set_data([], [])

def draw_inner_pin_init():
    for p in inner_pins: p.set_data([], [])

def draw_inner_circle_init():
    for p in inner_circles: p.set_data([], [])

def pin_update(n, d, D):
    for i in range(n):
        x = (d/2*np.sin(t)+ D/2*np.cos(2*i*np.pi/n))
        y = (d/2*np.cos(t)+ D/2*np.sin(2*i*np.pi/n))
        pins[i].set_data(x, y)

def inner_pin_update(n,N,rd,Rd,phi):
    for i in range(n):
        x = (rd*np.sin(t)+ Rd*np.cos(2*i*np.pi/n))*np.cos(-phi/(N-1)) - (rd*np.cos(t)+ Rd*np.sin(2*i*np.pi/n))*np.sin(-phi/(N-1))
        y = (rd*np.sin(t)+ Rd*np.cos(2*i*np.pi/n))*np.sin(-phi/(N-1)) + (rd*np.cos(t)+ Rd*np.sin(2*i*np.pi/n))*np.cos(-phi/(N-1))
        inner_pins[i].set_data(x, y)

def drive_pin_update(r):
    d0.set_data(r*np.sin(t), r*np.cos(t))

def update_inner_circle(e,n,N,rd,Rd,phi):
    for i in range(n):
        x = ((rd+e)*np.cos(t)+Rd*np.cos(2*i*np.pi/n))*np.cos(-phi/(N-1)) - ((rd+e)*np.sin(t)+Rd*np.sin(2*i*np.pi/n))*np.sin(-phi/(N-1)) + e*np.cos(phi)
        y = ((rd+e)*np.cos(t)+Rd*np.cos(2*i*np.pi/n))*np.sin(-phi/(N-1)) + ((rd+e)*np.sin(t)+Rd*np.sin(2*i*np.pi/n))*np.cos(-phi/(N-1)) + e*np.sin(phi)
        inner_circles[i].set_data(x, y)

def update_inner_pin(e,Rm,phi):
    x = (Rm+e)*np.cos(t)+e*np.cos(phi)
    y = (Rm+e)*np.sin(t)+e*np.sin(phi)
    inner_pin.set_data([x], [y])
    dot.set_data([(Rm+e)*np.cos(phi)+e*np.cos(phi)], [(Rm+e)*np.sin(phi)+e*np.sin(phi)])

def update_ehypocycloid(e,n,D,d,phi):
    RD, rd_half = D/2, d/2
    rc = (n-1)*(RD/n)
    rm = RD/n
    xa = (rc+rm)*np.cos(t)-e*np.cos((rc+rm)/rm*t)
    ya = (rc+rm)*np.sin(t)-e*np.sin((rc+rm)/rm*t)
    dxa = (rc+rm)*(-np.sin(t)+(e/rm)*np.sin((rc+rm)/rm*t))
    dya = (rc+rm)*(np.cos(t)-(e/rm)*np.cos((rc+rm)/rm*t))
    norm = np.sqrt(dxa**2 + dya**2)
    x = (xa - rd_half*dya/norm)*np.cos(-phi/(n-1)) - (ya + rd_half*dxa/norm)*np.sin(-phi/(n-1)) + e*np.cos(phi)
    y = (xa - rd_half*dya/norm)*np.sin(-phi/(n-1)) + (ya + rd_half*dxa/norm)*np.cos(-phi/(n-1)) + e*np.sin(phi)
    ehypocycloid.set_data(x, y)
    edot.set_data([x[0]], [y[0]])

# ========== Animation Function ==========
def animate(frame):
    global output_flag
    p = get_params()
    phi = 2*np.pi*frame / p['fm']
    ax.set_title(f"Reduction ratio {p['N'] - 1}:1")
    ax.set_xlim(-1.2*0.5*p['D'], 1.2*0.5*p['D'])
    ax.set_ylim(-1.2*0.5*p['D'], 1.2*0.5*p['D'])

    draw_pin_init()
    draw_inner_pin_init()
    draw_inner_circle_init()
    pin_update(p['N'], p['d'], p['D'])
    update_inner_pin(p['e'], p['Rm'], phi)
    inner_pin_update(p['n'], p['N'], p['rd'], p['Rd'], phi)
    drive_pin_update(p['Rm'])
    update_inner_circle(p['e'], p['n'], p['N'], p['rd'], p['Rd'], phi)
    update_ehypocycloid(p['e'], p['N'], p['D'], p['d'], phi)

    if output_flag:
        RD = p['D'] / 2
        rc = (p['N'] - 1) * (RD / p['N'])
        rm = RD / p['N']
        R_EN = RD / (p['e'] * p['N'])
        x_expr = f"({rc+rm:.3f} * cos(t)) - ({p['rd']/2:.3f} * cos(t + arctan(sin({1 - p['N']} * t)/({R_EN:.3f} - cos({1 - p['N']} * t))))) - ({p['e']:.3f} * cos({p['N']} * t))"
        y_expr = f"(-{rc+rm:.3f} * sin(t)) + ({p['rd']/2:.3f} * sin(t + arctan(sin({1 - p['N']} * t)/({R_EN:.3f} - cos({1 - p['N']} * t))))) + ({p['e']:.3f} * sin({p['N']} * t))"
        expression = f"X = {x_expr}\nY = {y_expr}"
        expr_box.set_val(expression)
        with open("expression.txt", "w") as f: f.write(expression)
        output_flag = False

# ========== Start Animation ==========
ani = animation.FuncAnimation(fig, animate, frames=1000, interval=50)
plt.show()