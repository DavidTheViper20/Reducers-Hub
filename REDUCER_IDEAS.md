# Reducers Hub — Future Mechanism Ideas

A running backlog of mechanisms/reducers to potentially add to the hub, with
notes on how they work, the reduction-ratio principle, and how feasible they
are to animate as 2D parametric geometry (matplotlib + DXF export).

Already implemented: **cycloidal drive, harmonic (strain-wave) drive,
logarithmic drive, planetary gear drive, Wolfrom cycloidal-planetary**.

## 🟢 Built — "Novel Reducers" family (`Novel Reducers/`)
Six animated, slider-driven, DXF-exporting demos, launched from the parent
Reducers Hub. All share `novel_demo_common.py` (auto-fitting plot, slider stack,
reset / export / open-files, animation loop):
1. **Gerotor / Trochoidal Pump** — inner N-lobe rotor enveloping N+1 outer teeth.
2. **Capstan / Cable Drive** — kinematic ratio + Euler grip law.
3. **Non-Circular (Elliptical) Gears** — twin ellipses rolling about their foci.
4. **Geneva Drive (Maltese Cross)** — intermittent indexing with dwell.
5. **Friction Wheel-on-Disc CVT** — variable ratio with reverse / neutral.
6. **Antikythera Pin-and-Slot Lunar Anomaly** — variable output from offset centers.

---

## ✅ Shortlisted / Approved (build these)

### 1. Gerotor / Trochoidal Pump
- **Why:** "Same math as the cycloidal drive, totally different machine." Both
  rotors are fully analytic parametric curves — high visual payoff, reuses the
  existing cycloid curve code.
- **How it works:** Internal positive-displacement pump. Inner rotor profile is
  a trochoid; the outer rotor is its conjugate with exactly **one more tooth
  (N+1)**. Co-rotating about offset centers, sealed chambers expand/contract.
- **Ratio principle:** Rotor speed ratio = N / (N+1) (it's a pump, not a torque
  reducer — frame it as the geometric cousin of the cycloidal drive).
- **2D feasibility:** **Easy.** Inner rotor = direct parametric trochoid; outer
  rotor = conjugate envelope (analytic or numeric). Pure 2D curves + rotation.
- **Source:** https://file.scirp.org/Html/62630_62630.htm

### 2. Capstan / Cable (Tendon) Drive
- **Why:** The drive behind surgical robots, haptics, exoskeletons. Trivial
  geometry but a great teaching moment — it has **two distinct formulas** people
  routinely conflate.
- **How it works:** A small driving capstan/sheave has cable wrapped several
  turns running to a larger output pulley; motion transmits via cable tension,
  grip maintained by wrap-angle friction.
- **Ratio principle (two separate things — show both):**
  - Kinematic reduction ratio = R_out / R_in (e.g. 155.2 mm / 19.4 mm = 8:1).
  - Euler/Eytelwein grip (NOT the gear ratio): T₂ = T₁·e^(μθ), θ = total wrap
    angle. e.g. μ=0.1, 360° wrap → 1.88.
- **2D feasibility:** **Easy.** Two circles + tangent cable segments + an arc
  for the wrap; ratio animation θ_out = θ_in · R_in/R_out.
- **Sources:** https://arxiv.org/pdf/2507.15693 ,
  https://www.firgelliauto.com/blogs/mechanisms/capstan-gear

---

## 🔬 Strong backlog candidates (from research round 1)

Ranked roughly by coolness × clean 2D-parametric fit.

- **Pin-wheel / eccentric-roller cycloidal** — Easy. Canonical cycloidal variant
  with rollers; R = L/(P−L). Reuses cycloid code.
- **Archimedean spiral / scroll cam** — Easy. *Variable* ratio that sweeps as it
  turns. r = a+bθ; ratio = scroll/pinion radius at contact point.
- **Coaxial magnetic gear** — Easy–Medium. Contactless, overload-proof; three
  concentric rings of colored sectors. n_s = p_i + p_o; ratio = n_s/p_i (or
  −p_o/p_i). Ratio is mode-dependent (which ring is fixed).
- **RV (Rotary Vector) reducer, Nabtesco** — Medium. *Flagship* robot-joint
  reducer: planetary spur stage + crankshaft-driven cycloidal discs.
- **Spinea TwinSpin** — Medium. Two-disc zero-backlash cycloidal; ratios are
  **odd** numbers (vs even for harmonic). Reuses cycloid code.
- **3K / "mechanical paradox" / split-ring planetary** — Medium. Sun + two rings
  with slightly different tooth counts → 100s:1 in one stage. One animation
  subsumes split-ring + differential planetary. G = (1+I₁)/(1−I₂); the near-zero
  denominator explodes the ratio.
- **Ball reducer (sinusoidal grooves)** — Medium. Balls walk between two wavy
  raceways; R = (Z₁−Z₂)/Z₁ (22 waves/20 balls → 11:1).
- **Roller-pinion + ring (Nexen-style)** — Easy–Medium. Zero backlash, ~99%
  efficiency; circles on pitch circles.
- **Differential (compound) screw** — Easy. Output/rev = difference of two
  thread pitches → sub-micron motion. Clearer in 2D than 3D.
- **Worm drive (+ self-locking demo)** — Easy. Side cross-section; show the
  self-locking threshold (lead angle < arctan μ).
- **Pseudo-Direct-Drive (PDD) magnetic** — Medium. Renders as the coaxial
  magnetic gear with a labeled output.

## 🟡 Cool but inherently 3D (schematic / 2.5D side view only)
Nutating/nutation drive, wobble-plate / swashplate, globoid (hourglass) worm,
globoidal cam indexer, roller-cam reducer, magnetic lead screw, Humpage bevel
train, SRI **Abacus** pure-rolling drive.

## ⚠️ Corrections / gotchas
- The **Abacus drive is SRI International** (Kernbaum, ~2016), **not MIT**.
- **"Galloway train"** could not be verified as a distinct named topology —
  treat as a generic compound epicyclic example.
- Magnetic gear ratio is **mode-dependent** (fixed ring changes formula/sign).
- **Archimedes screw is a pump**, and the **swashplate is a motion converter** —
  include them but frame honestly, not as rotary-to-rotary gearboxes.

---

## 🆕 Research round 2 — new territory (broader "cool mechanisms")

Ranked by coolness × clean-2D-parametric fit. Many of these are *better* 2D fits
than classic reducers because they're inherently planar.

### ⭐ Top new picks (Easy, build-ready)

- **Non-circular / twin-elliptical gears** — Easy, *striking* variable-ratio
  visual. Pitch ellipse r(θ)=a(1−e²)/(1+e·cosθ); twin pair needs no integration.
  ONE general engine — define ratio function i(φ), integrate conjugate
  φ2=∫ r1/(C−r1) dφ, space teeth by arc length — covers ellipse, eccentric,
  N-lobed, and sine/function-generating gears as presets. Highest feature-per-
  effort of the whole round. Refs: Litvin; https://sjsutst.polsl.pl/archives/2019/vol104/095_SJSUTST104_2019_Malakova.htm
- **Geneva drive (Maltese cross)** — Easy, iconic (film projectors). Exact
  geometry, verified: index = 360/n; slot angle ≈ 2·(90−180/n); center distance
  C = R_crank/sin(180/n); pin radius = C·cos(180/n); tangential entry required.
  4-slot external = 90° move / 270° dwell. Ref: https://en.wikipedia.org/wiki/Geneva_drive
- **Friction wheel-on-disc CVT** — Easy "hero" demo. Tiny circle translating
  across a big disc; live readout ratio = R_contact/r_wheel, with direction
  reversal through center (geared neutral). Ref: https://www.firgelliauto.com/blogs/mechanisms/friction-disc-and-roller
- **Scotch yoke** — Easy, closed-form, exact SHM: x = R·sinθ, a = −Rω²·sinθ
  (no 2nd harmonic, unlike slider-crank). Ref: https://en.wikipedia.org/wiki/Scotch_yoke

### ⭐ Story-rich / showpieces (Medium–Hard, high payoff)

- **Antikythera pin-and-slot lunar anomaly** — Medium. The best story in the
  history of machines, and genuinely planar: two offset circles + pin-in-slot →
  variable angular velocity. Metonic 235 months / 19 years. Ref: Freeth et al.
- **Strandbeest / Jansen 11-bar leg** — Hard but a viral showpiece. "Holy
  numbers" a:38 b:41.5 c:39.3 d:40.1 e:55.8 f:39.4 g:36.7 h:65.7 i:49 j:50
  k:61.9, crank m:15 (proportions; uniform scaling OK). Needs a numeric
  loop-closure solver. Ref: https://en.wikipedia.org/wiki/Jansen%27s_linkage
- **Fusee (clockwork constant-torque spiral)** — Easy–Medium. Spiral cone
  profile + migrating chain; geometry-solves-physics tale. radius ∝ 1/spring-torque.
- **Orrery** — Easy. Concentric coplanar trains; tooth ratios approximate
  planetary period ratios (Earth:Mars ≈ 8:15).

### Reusable engines worth building once (unlock whole families)
- **Two-circle-intersection loop-closure solver** → unlocks Chebyshev/Hoeken
  (4-bar straight-line), Watt's linkage, Klann, and Jansen walkers.
- **Conjugate-curve integrator** (φ2=∫ r1/(C−r1) dφ) → unlocks every
  non-circular gear (ellipse / eccentric / lobed / sine).

### Other solid candidates from round 2
- Internal Geneva (smoother, 270/90), ratchet-and-pawl, mutilated/intermittent
  gears, star wheels — all Easy–Medium, planar.
- NuVinci ball-and-ring & toroidal (Extroid) CVT — Medium, animate as a 2D
  cross-section with a tilting ball/roller; 1:1 at the 45° symmetric pose.
  (NuVinci efficiency figures ~70–89% are unofficial — present as estimates.)
- Kopp/cone variator, planetary traction-roller reducer — Easy–Medium.
- Straight-line linkage family (Watt → Chebyshev → Hoeken → Peaucellier, exact
  via inversion OP×OQ=const), Klann walker — Medium–Hard.
- Quick-return (Whitworth): time ratio = α/(360−α), ~2:1 — Medium.
- Schmidt offset coupling: constant 1:1 across parallel offset — Medium.
- Curta stepped-drum calculator — Medium, developed-view staircase profile.

### ⚠️ 3D / schematic-only (round 2)
Clock escapements: anchor/recoil & deadbeat (Medium), Swiss lever 15-tooth +
fork (Medium–Hard), grasshopper (Hard). Automotive differential & differential-
as-adder (same mechanism: ω_L+ω_R = 2·ω_carrier — pair them as one
"differential = mechanical +" concept piece) and south-pointing chariot — all
use 3D bevels, do as cutaway/top-down schematics.
