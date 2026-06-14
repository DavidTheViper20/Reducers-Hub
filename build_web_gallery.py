"""Build the static Netlify gallery for the Novel Reducers demos.

Renders each mechanism to a looping GIF and a default-configuration DXF, then
writes a self-contained ``web/index.html`` gallery plus ``netlify.toml``.

Run from the repo root:   python build_web_gallery.py
"""

from __future__ import annotations

import html
import importlib.util
import io
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent
NOVEL = ROOT / "Novel Reducers"
WEB = ROOT / "web"
ASSETS = WEB / "assets"
sys.path.insert(0, str(NOVEL))

MECHANISMS = [
    ("gerotor_pump", "Internal positive-displacement pump and the geometric cousin of the cycloidal "
                     "drive: an N-lobe inner rotor sweeps inside N+1 outer teeth, sealing chambers as "
                     "it turns. Speed ratio = (N+1) / N."),
    ("capstan_drive", "A small input sheave drives a larger output pulley through a wrapped cable. The "
                      "kinematic reduction is the pulley/sheave radius ratio; the Euler grip law "
                      "T2/T1 = exp(mu*theta) is a separate relationship that sets how much the wrap holds."),
    ("non_circular_gears", "Two identical ellipses pinned at their foci roll without slipping. The "
                           "instantaneous ratio swings through each turn while the centre distance stays "
                           "constant at C = 2a, so they always mesh."),
    ("geneva_drive", "An intermittent indexing drive: a continuously turning pin advances a slotted wheel "
                     "by 360/n per revolution, then a locking disc holds it stationary during the dwell."),
    ("friction_disc_cvt", "A continuously variable traction drive: a small wheel rolls on the face of a "
                          "spinning disc. The ratio equals contact-radius / wheel-radius and reverses as "
                          "the contact crosses the centre (a geared neutral)."),
    ("antikythera_anomaly", "The Antikythera mechanism's pin-and-slot device: two gears on slightly offset "
                            "centres, coupled by a pin riding in a slot, turn a constant input into a "
                            "varying output — reproducing the Moon's changing speed."),
]

CARD = """      <article class="card">
        <div class="media"><img loading="lazy" src="assets/{name}.gif" alt="{title} animation"></div>
        <div class="body">
          <h2>{title}</h2>
          <p class="blurb">{blurb}</p>
          <p class="readout">{readout}</p>
          <details>
            <summary>Adjustable parameters</summary>
            <ul>{params}</ul>
          </details>
          <a class="dl" href="assets/{name}.dxf" download>Download DXF</a>
        </div>
      </article>"""


def load(name):
    spec = importlib.util.spec_from_file_location(name, NOVEL / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def render_gif(demo, out_path, frames=44, dpi=64):
    fig = demo.fig
    demo._refit_limits()
    images = []
    for phase in np.linspace(0.0, 2 * np.pi, frames + 1)[:-1]:
        demo._render(phase)
        fig.canvas.draw()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi)
        buf.seek(0)
        images.append(Image.open(buf).convert("RGB"))
    images[0].save(out_path, save_all=True, append_images=images[1:],
                   duration=70, loop=0, optimize=True)


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    cards = []
    for name, blurb in MECHANISMS:
        module = load(name)
        demo = module.demo
        render_gif(demo, ASSETS / f"{name}.gif")
        demo._write_dxf(ASSETS / f"{name}.dxf")
        params = "".join(
            f"<li>{html.escape(p.label)} "
            f"<span>({p.vmin:g}–{p.vmax:g}, default {p.vinit:g})</span></li>"
            for p in demo.params
        )
        cards.append(CARD.format(
            name=name,
            title=html.escape(demo.title),
            blurb=html.escape(blurb),
            readout=html.escape(demo.readout(demo.values(), 0.0)),
            params=params,
        ))
        print(f"built {name}")

    page = PAGE_TEMPLATE.replace("{{CARDS}}", "\n".join(cards))
    (WEB / "index.html").write_text(page, encoding="utf-8")
    (ROOT / "netlify.toml").write_text(NETLIFY_TOML, encoding="utf-8")
    print(f"wrote {WEB / 'index.html'} and netlify.toml")


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Novel Reducers — Reducers Hub</title>
  <style>
    :root { color-scheme: dark; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
           background: #0e1116; color: #e6edf3; line-height: 1.55; }
    header { padding: 48px 24px 24px; text-align: center; border-bottom: 1px solid #222a35; }
    header h1 { margin: 0 0 8px; font-size: clamp(1.8rem, 4vw, 2.6rem); }
    header p { margin: 0 auto; max-width: 720px; color: #9aa7b4; }
    .note { max-width: 760px; margin: 18px auto 0; font-size: .9rem; color: #7d8a98;
            background: #131a22; border: 1px solid #222a35; border-radius: 10px; padding: 12px 16px; }
    main { max-width: 1200px; margin: 0 auto; padding: 28px 18px 64px;
           display: grid; gap: 22px; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
    .card { background: #131a22; border: 1px solid #222a35; border-radius: 14px; overflow: hidden;
            display: flex; flex-direction: column; }
    .media { background: #fff; }
    .media img { display: block; width: 100%; height: auto; }
    .body { padding: 16px 18px 20px; display: flex; flex-direction: column; gap: 10px; }
    .body h2 { margin: 0; font-size: 1.15rem; }
    .blurb { margin: 0; color: #c2ccd6; font-size: .92rem; }
    .readout { margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
               font-size: .78rem; color: #8fd3a6; background: #0e1419; border-radius: 8px;
               padding: 8px 10px; overflow-x: auto; }
    details { font-size: .86rem; color: #aab6c2; }
    summary { cursor: pointer; color: #cdd7e1; }
    details ul { margin: 8px 0 0; padding-left: 18px; }
    details li span { color: #7d8a98; }
    .dl { margin-top: auto; align-self: flex-start; text-decoration: none; font-size: .85rem;
          color: #0e1116; background: #58a6ff; padding: 8px 14px; border-radius: 8px; font-weight: 600; }
    .dl:hover { background: #79b8ff; }
    footer { text-align: center; padding: 24px; color: #6b7785; font-size: .82rem;
             border-top: 1px solid #222a35; }
  </style>
</head>
<body>
  <header>
    <h1>Novel Reducers</h1>
    <p>Animated, customizable demos of unusual reducers and motion mechanisms from the Reducers Hub.</p>
    <p class="note">These previews are one full input revolution of each interactive desktop demo.
      For the live sliders, clone the repo and run the matplotlib apps in <code>Novel Reducers/</code>.
      Each card links to a DXF exported at the default configuration.</p>
  </header>
  <main>
{{CARDS}}
  </main>
  <footer>Generated from the Reducers Hub &mdash; Novel Reducers family.</footer>
</body>
</html>
"""

NETLIFY_TOML = """# Static gallery for the Novel Reducers demos.
# Netlify just serves the pre-built files in web/ (no build step needed).
[build]
  publish = "web"
  command = ""
"""


if __name__ == "__main__":
    main()
