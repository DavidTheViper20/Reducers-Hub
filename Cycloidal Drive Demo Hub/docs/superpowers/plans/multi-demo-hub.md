# Multi-Demo Hub Plan

## Goal
Turn the Cycloidal Drive repo into a single launchable app with a main menu that can open any demo and provide the same shared affordances in each window:
- consistent slider labels
- DXF export
- reveal export in Finder
- cleaner bottom controls

## Constraints
- Keep the original demo scripts runnable.
- Avoid hand-rewriting every demo.
- Reuse the current Python/matplotlib stack already in the repo.

## Approach
1. Build a demo catalog from the existing Python demo files with friendly names and ordering.
2. Add a shared runner that loads a chosen demo script in-process with a patched `plt.show()` hook.
3. During the hook, decorate the figure with:
   - full slider labels
   - export DXF button
   - reveal in Finder link/button
   - shared status text
4. Export the currently visible plot content to DXF generically from the primary plot axes so every demo gets the feature.
5. Build a Tk main menu that launches any catalog entry through the shared runner.
6. Point the Desktop launcher at the new main menu.

## Tests First
1. Demo catalog returns expected entries and friendly labels.
2. Generic artist export writes a DXF from simple line content.
3. Slider label mapping expands common abbreviations.
4. Finder reveal helper uses `open -R`.

## Risks
- Some demos may open multiple non-control axes or have unusual UI layouts.
- A few scripts may use artist patterns that need filtering during export.

## Mitigation
- Start with a generic primary-axes detector and verify across a few representative demos.
- Keep the wrapper additive so original script behavior remains intact.
