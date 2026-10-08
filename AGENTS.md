# agent.md

## About the project

The main purpose of this project is **scripts for Rhinoceros (RhinoScript / rhinoscriptsyntax in Python) and Grasshopper components**.
It is not an application or a library to build — it is a set of computational design tools that run inside Rhino 6/7/8
(the `_ScriptEditor` / `_EditPythonScript` editor) or are pasted into GHPython components in Grasshopper.

Domain — cutting and pattern preparation (boat covers, leather wallets, patterns), work with curves, polylines,
bounding boxes, linetypes and splitting curves by angle.

Code compatibility: IronPython 2.7 and CPython 3 (Rhino 8).

## Language

- **Everything is in English**: prompts in `rs.Get*` / `SetCommandPrompt`, `print` messages, `HELP`, comments, docstrings,
  layer names, labels / prefixes, UserText keys, file names, toolbar tabs and tooltips, README.
- The only exception is `markup/Legend.py`: its output text has an `UA / EN / IT` option on purpose (printed legends).
- Old drawings with UA/IT names (`Parts::CopriZip`, `Parts::Canalina`, labels `CZ`, `Can<n>`, `F<n>`) are not supported by the
  current scripts — the version for them is the git tag `legacy-ua-it`.

## Rhino Scripts

- Scripts run in Rhino's IronPython 2.7. Add `# -*- coding: utf-8 -*-` as the first line and avoid f-strings and Python 3-only syntax.
- Operate ONLY on the objects the user selected, never document-wide, unless explicitly told otherwise.
- Preserve the original layer, group membership and selection state of any object you modify or replace.
- Prefer click-based interaction (e.g., 'click near the end to trim') over abstract options like Start/End, because the user can't tell curve direction.
- Each new script needs: the script in its category subfolder, a toolbar button, and a README entry.
- Scripts with command options (`AddOption*`): a `HELP` string right before `main()` explaining every option letter ("W — …"), printed as the first line of `main()` — on Mac the command history shows under the option fields.
- Syntax-checking is not verification. At the end, state clearly which scripts were NOT run in Rhino and give a 3-step manual test for each.

## Directories

- **`scripts/`** — Python scripts for Rhino (`rhinoscriptsyntax` / `Rhino.Geometry`), in subfolders = toolbar tabs:
  - **`sizes/`** (tab "Sizes"): `BoundingBoxWithSize_Rhino8_CPlane.py` (ghosted bbox with XYZ labels; `BoundingBoxWithSize.py` — old version), `BoundingBoxCenterLines.py`, `LabelClosedCurveSizes.py`, `draw_centered_rectangle.py` (rectangle of a given size centred on the CPlane).
  - **`curves/`** ("Curves"): `SplitCrvByAngle.py`, `smooth_corners.py`, `GH_SplitCurveByAngle.py` (split / round by angle), `CrvToPolyline.py`, `TrimCrvEnds.py`, `KeepCrvEnds.py`, `TrimOutsidePanel.py`, `find_exact_connection.py` (contact point at a fixed length), `MidLine.py`, `OffsetRigid.py` (copy without changing shape, moved by D along the normal at the clicked point).
  - **`cut/`** ("Cut"): `PreparePanelCut.py`, `SplitPanelsToMaterial.py` (panels at material lines: trimming, 1 cm seam, the piece moves by 50 mm, pairs A–A, B–B…), `sel_curve_overlap.py` (duplicates / overlaps: selected curves or all).
  - **`analysis/`** ("Analysis"): panel and cut analysis — `SelectSmallClosedCurves.py`, `CheckTangentialCutRisks.py`, `RecommendCutTabs.py`, `AddCutTabs.py` (+ `.md` descriptions).
  - **`parts/`** ("Parts", result in layer `Parts::<Name>`): `Panels.py` — panels: copy of a closed curve in place in `Parts::Panels` (the input curve is deleted), number `P<n>` (text inside at a click + TextDot above-left in sublayer `Parts::Panels::Dots`, UserText `Part`), nested curves — panel holes; number — the smallest free one (a deleted panel's number is reused). `StripsFromCurves.py` — strips (binding / reinforcement): each selected curve → rectangle of height H and the curve's length (+ allowance); stacked in layer `Parts::Strips`, labels `S<n>  L=… × H` + TextDot `S<n>` on the curve; numbering continues from the largest `S<n>` in the layer. `ZipCover.py` — zip cover / seam allowance (one script): panel + click near an edge → edge corner to corner + offset W outward, ends along the extension of the neighbouring edges; `Points=No` — label `ZC W`, layer `Parts::ZipCover`; `Points=Yes` — seam points (`sewing_lengths` from `markup/sewing_points.py`) on a copy of the edge, label `SA W`, layer `Parts::Seam`; `EditPanel=No` — only markup in place (strip lines not on the panel edge + label, one group), `EditPanel=Yes` — the panel contour itself grows (layer / groups / UserText kept), the old edge stays as a line; no part above. Also home of `label_frame`, `sewing_geometry`, `pick_edge`, `flap` used by other parts scripts. `JoinCorner.py` — join any two open curves at a corner, edge to edge: click near the corner → the two nearest curve ends; per end its last edge (corner to corner) is joined or dropped, whichever pair meets nearest the click; extended / trimmed to the intersection, one curve (first keeps layer / groups, second deleted, its group merges); frame (both ends of one curve) → closed; closed curves ignored. `ZipStops.py` — zips and tracks, only stops + number text (the lines stay untouched in their layer/group): option `Type` = `Zip` (both sides, `Z<n>`, `Parts::Zip`) / `Track` (one side, `Trk<n>`, `Parts::Track`); one zip/track = all its lines on all panels (picked one after another); option `Trim` (per type, Zip 4 cm, Track 0) — stops this far in from the real ends; text above the middle between the stops, data on the text (UserText `Zip`, `ZipLine` = line id, `ZipTrim`), option `Style`; stops + text a group per line; split side (Zip 3+ lines, Track 2+) → a click near the junction changes the stop to a tick at the line end; then a step to flip the number (click the text) to the other side of the line. `ZipList.py` — order table from the number texts, length live = line − trims (deleted line — warning): zips — lines of one number → two sides with the closest sums, the longer one is ordered, rounded up to 1 cm, difference > 5 mm or a single line — warning, summary "cm × pcs"; tracks — full length (sum of lines) in a separate section; CSV `<file>_zips.csv` next to the `.3dm` + clipboard. `MarkReinf.py` — reinforcement strip as ` R<H>` on an existing label (edge length in UserText); `RList.py` — strip table. `ReinfCircle.py` — corner reinforcement circle: click near a corner → sector of radius R between the sides, in place, label `RC<n>  R=…`, layer `Parts::Reinforcements` (other shapes — their own prefixes RS, RT…). `ReinfD.py` — D reinforcement at the end of a pocket: click top corner (centre of the end) → bottom corner, width W + extension R (half-circle / half-ellipse), `RD<n>`, same layer (uses `layer` / `next_number` / `text_style` from ReinfCircle). `ReinfO.py` — O reinforcement at a full-width pocket: boundary (panel) → click centre (top corner of the pocket) → click on a line, R = distance + Plus (5 cm), only inside the panel, allowance SA (1 cm) along the panel edge (arc without a seam), `RO<n>`, same layer (uses `piece` from ReinfCircle). `ReinfBord.py` — reinforced border: panel + click near an edge → `ZipCover.flap(..., inward=True)`: strip H (6 cm) inward, ends along the neighbouring edges; JoinCorner joins two strips at a corner (overlap → BooleanUnion), SA (0) on the inner edge, `RB<n>  H=…`, same layer. `TubePockets.py` / `UpdateTubePockets.py` — tube pockets `TP<n>` in `Parts::Pockets`. `LayoutParts.py` — layout for cutting: a copy of each selected part (whole group) in a row from the click point (Enter — continue the row), in sublayer `<layer>::Layout`; the original stays as markup, UserText `LayoutOf` on the copy.
  - **`markup/`** ("Markup"): `PointsToCrosses.py` (points / clouds / TextDot → cross or circle), `sewing_points.py`, `line_type.py` + `linetype.gh` (linetype `400,2`), `PatternTextStyles.py` (+ `_check.py`), `TextToDot.py`, `DotToPanelText.py`, `TextToCurves.py` (text → curves for nesting, upside-down text is not mirrored — like Draw forward on screen), `Legend.py` (legend of script labels — only marks present, text at the click point, Lang = UA / EN / IT), `PanelPage.py` (selection → one new A4 Layout `P<n>`, detail Top, like Zoom Selected on the whole selection; one run — one sheet).
  - `build_scripts_rui.py` — builder of the `Scripts.rui` toolbar (6 tabs: Sizes / Curves / Analysis / Cut / Parts / Markup).
  - `tests/` — checks (some run in Rhino 8 via `rhinocode`).
  - Imports between folders — via `sys.path` from `__file__` (e.g. `cut/SplitPanelsToMaterial.py` uses `markup/PatternTextStyles.py`).

- **`Grasshoper scripts/`** — Grasshopper definitions (`.gh`): `bounding_dimensions.gh`, `Len_dimentions.gh`,
  `polyline.gh`, `drag.gh`, `sew points.gh`, `divanno_v1.gh`, `autonest.gh`.

- **`Patterns/`** — source patterns and cutting material (`.3dm`, `.dxf`, `.pdf`): wallets, tote, origami templates.

- The root `allalunga.3dm` — Rhino working file.

## Working with code

- Put new scripts in a subfolder `scripts/<tab>/` (sizes / curves / analysis / cut / parts / markup) or `Grasshoper scripts/` (`.gh`); in `GROUPS` — `py("<folder>/<Script>.py")`.
- Keep IronPython 2.7 and CPython 3 compatibility unless explicitly told otherwise.
- Take units and tolerances from the document (`sc.doc.ModelAbsoluteTolerance`), do not hardcode them.
- Scripts that **create parts** (strips, reinforcements etc.) live in `scripts/parts/`, put the result in layer `Parts::<Name>` and go to the **Parts** toolbar tab (`py("parts/<Script>.py")`).

## Toolbar (`Scripts.rui`)

- New script → add a line to `GROUPS` in `scripts/build_scripts_rui.py` (and to the table in `README.md`).
- **Do NOT run the builder `build_scripts_rui.py`** — the user rebuilds `Scripts.rui` themselves (with Rhino closed). Remind them of the build command at the end of the reply.
- After every created / changed script, end the reply with the full button macro:
  `!_-RunPythonScript "/Users/dmytro/Documents/Rhino/scripts/<subfolder/><Script>.py"`

## Git

- Repository: https://github.com/Miity/rhino_scripts_panneling (public, branch `main`).
- After every finished change — commit and push: `git add -A && git commit -m "<what changed>" && git push`.
- `Patterns/` and `*.3dm` are in `.gitignore` (third-party patterns / working files) — do not add them to the repository.
