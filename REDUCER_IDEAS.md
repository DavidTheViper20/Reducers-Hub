# Reducers Hub — Future Mechanism Ideas

A running backlog of mechanisms/reducers to potentially add to the hub, with
notes on how they work, the reduction-ratio principle, and how feasible they
are to animate as 2D parametric geometry (matplotlib + DXF export).

Already implemented: **cycloidal drive, harmonic (strain-wave) drive,
logarithmic drive, planetary gear drive, Wolfrom cycloidal-planetary**.

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

## 🆕 Research round 2 (in progress)
New territory being explored: non-circular/elliptical gears, intermittent motion
(Geneva/ratchet/escapements), traction/friction CVTs, linkage-based mechanisms
(Strandbeest/Chebyshev/Peaucellier), and historical/horological gearing
(Antikythera, south-pointing chariot). Findings to be appended here.
