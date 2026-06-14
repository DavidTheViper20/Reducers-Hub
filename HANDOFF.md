# Reducers Hub — Hand-off Document

This document hands off the work done in a Claude Code **web session** to a
**local session** (or a human) so it can be run locally, extended, and/or
deployed to Netlify. Everything described here is already committed and pushed.

- **Repository:** `DavidTheViper20/Reducers-Hub`
- **Working branch:** `claude/reducers-hub-dxf-export-6oytk9`
- **To get it locally:**
  ```bash
  git clone <your-repo-url> Reducers-Hub
  cd Reducers-Hub
  git checkout claude/reducers-hub-dxf-export-6oytk9
  git pull origin claude/reducers-hub-dxf-export-6oytk9
  ```

---

## 1. What was built (summary)

1. **Fixed the Wolfrom DXF export** so it writes the two reducers shown on the
   plot as **two separate DXF files** matching the live displayed pose.
   File: `Cycloidal Drive Demo Hub/wolfrom_cycloidal_planetary.py`
   (functions `export_single_stage_dxf` and `handle_export`).

2. **Researched and recorded** a large set of candidate mechanisms in
   `REDUCER_IDEAS.md` (two research rounds).

3. **Built a new "Novel Reducers" family** with six animated, slider-driven,
   DXF-exporting matplotlib demos on a shared framework. This is the main
   deliverable to potentially put on the web.

---

## 2. The Novel Reducers family (the thing to deploy/transfer)

Folder: **`Novel Reducers/`**

| File | What it is |
|---|---|
| `novel_demo_common.py` | **Shared framework.** Figure, auto-fitting plot, slider stack, reset/export/open buttons, animation loop, DXF writer. |
| `gerotor_pump.py` | Gerotor / trochoidal pump (inner N-lobe rotor enveloping N+1 outer teeth). |
| `capstan_drive.py` | Capstan / cable drive (kinematic ratio + Euler grip law). |
| `non_circular_gears.py` | Twin elliptical gears rolling about their foci. |
| `geneva_drive.py` | Geneva drive / Maltese cross (intermittent indexing). |
| `friction_disc_cvt.py` | Friction wheel-on-disc CVT (variable ratio, reverse/neutral). |
| `antikythera_anomaly.py` | Antikythera pin-and-slot lunar anomaly (variable output). |
| `main_menu.py` | Tkinter launcher page (`build_embedded_page`) used by the parent hub. |
| `requirements.txt` | `numpy`, `matplotlib`, `ezdxf`. |
| `tests/test_novel_reducers.py` | Headless tests: each module builds, animates, exports DXF. |

The family is registered in the parent hub `reducers_hub.py` (it appears as the
5th family, status "Ready").

### Run it locally
```bash
pip install -r "Novel Reducers/requirements.txt"

# Whole hub (Tk window -> choose "Novel Reducers"):
python reducers_hub.py

# Or run any single mechanism directly (opens its own animated window):
python "Novel Reducers/gerotor_pump.py"
python "Novel Reducers/capstan_drive.py"
python "Novel Reducers/non_circular_gears.py"
python "Novel Reducers/geneva_drive.py"
python "Novel Reducers/friction_disc_cvt.py"
python "Novel Reducers/antikythera_anomaly.py"
```
Each window has sliders (left), the animated plot (right), a live readout, and
**Reset / Export DXF / Open Files** buttons. DXF files are written to
`~/Desktop/Novel Reducer Exports/`.

### Run the tests
The repo uses `tkinter`. On a normal desktop Python that's present:
```bash
pip install pytest
python -m pytest "Novel Reducers/tests" -q
python -m pytest "Cycloidal Drive Demo Hub/tests/test_reducers_hub.py" -q
```
(If a CI/headless box lacks `tkinter`, only `main_menu.py`/`reducers_hub.py`
need it; the mechanism modules themselves do not import tkinter.)

### How the framework works (to add MORE mechanisms)
A mechanism module only defines:
- `PARAMS = [Param(key, label, vmin, vmax, vinit, step, integer, fmt), ...]`
- `compute(values: dict, phase: float) -> list[item]` where items are built with
  `path(...)`, `circles(...)`, `dot(...)`, `segment(...)` from `novel_demo_common`.
- optional `readout(values, phase) -> str`
- `demo = MechanismDemo(title, subtitle, params=PARAMS, compute=compute, readout=readout, export_name=...)`
- module tail: `_has_custom_layout = True`, `demo.build()`, `fig = demo.fig`,
  `if __name__ == "__main__": demo.show()`

The framework auto-fits the view by sampling `compute` over phase `0..2π` on
every slider change, so geometry never falls off-screen. `gerotor_pump.py` is
the cleanest reference to copy.

---

## 3. Getting it on Netlify

**Important:** Netlify serves **static** sites. The demos are Python/matplotlib
**desktop** apps and cannot run on Netlify as-is. There are two realistic paths.

### Path A — Static gallery (fast, recommended first step)
A generator script is included: **`build_web_gallery.py`** (repo root). It
renders each mechanism to a looping GIF + a default-config DXF and writes a
self-contained `web/index.html` gallery plus a `netlify.toml`.

```bash
pip install -r "Novel Reducers/requirements.txt" pillow
python build_web_gallery.py        # creates web/ (index.html + assets/) and netlify.toml
```
Then deploy any of these ways:
- **Connect the GitHub repo in Netlify** (Add new site → Import from Git →
  pick this repo/branch). `netlify.toml` already sets `publish = "web"` and no
  build command, so Netlify just serves `web/`.
- **Netlify CLI:** `npx netlify-cli deploy --prod --dir web`
- **Drag-and-drop:** zip/drag the `web/` folder onto https://app.netlify.com/drop

Result: a browser gallery showing all six animations with DXF download links.
(This shows the motion but is **not** interactive — no live sliders.)

> Note: the web session created `build_web_gallery.py` but did **not** run it,
> so `web/` and `netlify.toml` are not committed yet. Run the script locally to
> generate them, then commit if you want them in Git.

### Path B — Interactive web port (bigger effort)
To get real in-browser sliders, port each mechanism's `compute()` math to
JavaScript and draw on `<canvas>` (or use Pyodide to run the existing Python in
the browser). The math is simple and already verified in the Python modules —
each is a few parametric equations. This is a larger build; the static gallery
(Path A) is the quick win.

---

## 4. Suggested tasks for the local session

1. `git checkout claude/reducers-hub-dxf-export-6oytk9 && git pull`.
2. `pip install -r "Novel Reducers/requirements.txt"` and run
   `python reducers_hub.py` to confirm the six demos open and animate.
3. Run the tests (section 2).
4. For Netlify: run `python build_web_gallery.py`, review `web/index.html`
   locally (open in a browser), then deploy via one of the Path A options and
   commit `web/` + `netlify.toml`.
5. (Optional) If interactive web is wanted, start the Path B JS/Pyodide port,
   reusing the verified formulas in each `Novel Reducers/*.py`.

---

## 5. Key references (for math/validation)
See `REDUCER_IDEAS.md` for the researched mechanisms, formulas, and citations.
Each mechanism module also documents its ratio principle in the file header.
