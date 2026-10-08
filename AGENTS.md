# agent.md

## About the project

The main purpose of this project is **scripts for Rhinoceros (RhinoScript / rhinoscriptsyntax in Python) and Grasshopper components**.
It is not an application or a library to build — it is a set of computational design tools that run inside Rhino 6/7/8
(the `_ScriptEditor` / `_EditPythonScript` editor) or are pasted into GHPython components in Grasshopper.

Domain — cutting and pattern preparation (boat covers, leather wallets, patterns), work with curves, polylines,
bounding boxes, linetypes and splitting curves by angle.

Code compatibility: IronPython 2.7 and CPython 3 (Rhino 8).

## Language

- **Code and docs are in English**: prompts in `rs.Get*` / `SetCommandPrompt`, option names, `print` messages, `HELP`, comments,
  docstrings, layer names, UserText keys, file names, README.
- **Labels on the drawing are Italian codes** (customers and seamstresses are Italian), every number in a label is in **cm**
  (`PatternTextStyles.cm`; `w` width, `l` length, `h` height, `r` radius): `P<n>`, `F<w>  l=…`, `Off<w>` (ZipCover; older drawings `CZ<w>`), `C<w>`, `Z<n>`, `Can<n>`,
  `R<w>`, `RC<n>  r=…`, `RD<n>`, `RO<n>  r=…`, `T<n>`, `B<w>`, `Pt<w>` — the table is in README ("Labels"). On the panel one edge's labels go `Z<n> R<w> B<w> Pt<w>` (`ZipStops.labels_after`); without a zip the first of `R<w> B<w> Pt<w>` stays, the rest follow it.
- **The toolbar is in Italian**: tab / button names and tooltips from `IT` in `build_scripts_rui.py`; the English ones stay in `GROUPS` (`LANG`).
- `markup/Legend.py` output has a `UA / EN / IT` option on purpose (printed legends), default IT.
- Old drawings are not supported by the current scripts — English labels (`ZC`, `SA`, `Trk`, `S`, `TP`, `RB`, mm): git tag `legacy-en`;
  UA/IT names (`Parts::CopriZip`, `Parts::Canalina`, `CZ W`, `Can<n>`, `F<n>`): git tag `legacy-ua-it`.

## Rhino Scripts

- Scripts run in Rhino's IronPython 2.7. Add `# -*- coding: utf-8 -*-` as the first line and avoid f-strings and Python 3-only syntax.
- Operate ONLY on the objects the user selected, never document-wide, unless explicitly told otherwise.
- Preserve the original layer, group membership and selection state of any object you modify or replace.
- Prefer click-based interaction (e.g., 'click near the end to trim') over abstract options like Start/End, because the user can't tell curve direction.
- Each new script needs: the script in its category subfolder, a toolbar button, and a README entry.
- Scripts that work in a click loop (click after click, Enter — done): option `Undo` in the click prompt that takes back the last click — shared `scripts/click_undo.py` (`Steps`: `start()` before each click's changes, `change(id)` before Replace / attribute changes, `delete(id)` instead of deleting; objects added during the click are found by themselves); numbers given in that click are reused.
- Option `Undo` is always added FIRST in its prompt (before every other `AddOption*`): Rhino gives the shortcut letter to the option added first, so `Undo` keeps **U** (e.g. after `Up` it got `n`).
- Scripts with command options (`AddOption*`): a `HELP` string right before `main()` explaining every option letter ("W — …"), printed as the first line of `main()` — on Mac the command history shows under the option fields.
- Syntax-checking is not verification. At the end, state clearly which scripts were NOT run in Rhino and give a 3-step manual test for each.

## Directories

- **`scripts/`** — Python scripts for Rhino (`rhinoscriptsyntax` / `Rhino.Geometry`), in subfolders = toolbar tabs:
  - **`sizes/`** (tab "Sizes"): `BoundingBoxWithSize_Rhino8_CPlane.py` (ghosted bbox with XYZ labels; `BoundingBoxWithSize.py` — old version), `BoundingBoxCenterLines.py`, `LabelClosedCurveSizes.py`, `draw_centered_rectangle.py` (rectangle of a given size centred on the CPlane).
  - **`curves/`** ("Curves"): `SplitCrvByAngle.py`, `smooth_corners.py`, `GH_SplitCurveByAngle.py` (split / round by angle), `CrvToPolyline.py`, `TrimCrvEnds.py`, `KeepCrvEnds.py`, `TrimOutsidePanel.py`, `find_exact_connection.py` (contact point at a fixed length), `MidLine.py`, `OffsetRigid.py` (copy without changing shape, moved by D along the normal at the clicked point).
  - **`cut/`** ("Cut"): `PreparePanelCut.py`, `SplitPanelsToMaterial.py` (panels at material lines: trimming, 1 cm seam, the piece moves by 50 mm, pairs A–A, B–B…), `sel_curve_overlap.py` (duplicates / overlaps: selected curves or all).
  - **`analysis/`** ("Analysis"): panel and cut analysis — `SelectSmallClosedCurves.py`, `CheckTangentialCutRisks.py`, `RecommendCutTabs.py`, `AddCutTabs.py` (+ `.md` descriptions).
  - **`parts/`** ("Parts", result in layer `Parts::<Name>`): `sewing_points.py` (button Battute, right after Panels) — battute: panels / curves + click near an edge → points from the centre of that edge (corner to corner, `ZipCover.pick_edge`) both ways with Step (200 mm) + centre tick (Tick 10 mm; panel — into the panel, curve — symmetric), layer `Parts::SewingMarks`. `Panels.py` — panels: copy of a closed curve in place in `Parts::Panels` (the input curve is deleted), number `P<n>` (text inside at a click + TextDot above-left in sublayer `Parts::Panels::Dots`, UserText `Part`), nested curves — panel holes; number — the smallest free one (a deleted panel's number is reused). `StripsFromCurves.py` — fascia strips (binding / reinforcement): each selected curve → rectangle of width W and the curve's length (+ allowance); stacked in layer `Parts::Strips`, label `F<w>  l=…` on the strip + the same TextDot on the curve, no number. `ZipCover.py` — zip cover: panel + click near an edge → edge corner to corner + offset W outward, ends along the extension of the neighbouring edges; label `Off<w>`, layer `Parts::ZipCover`; `EditPanel=No` — only markup in place (strip lines not on the panel edge + label, one group), `EditPanel=Yes` — the panel contour itself grows (layer / groups / UserText kept), the old edge stays as a zip line; no seam points (separate script). Also home of `label_frame`, `pick_edge`, `flap` used by other parts scripts. `MergeOutline.py` — closed panel + curve(s) enclosing an area together → one panel by the outer line (replaces the panel), the old edge left inside stays as an open curve. `JoinCorner.py` — join any two open curves at a corner, edge to edge: click near the corner → the two nearest curve ends; per end its last edge (corner to corner) is joined or dropped, whichever pair meets nearest the click; extended / trimmed to the intersection, one curve (first keeps layer / groups, second deleted, its group merges); frame (both ends of one curve) → closed; a closed curve with a notch (inward break > Angle) nearest the click → joined there as a frame corner. `ZipStops.py` — zips and tracks, panels / curves untouched: select panels and / or open curves, then click near each edge of one zip (edge corner to corner as in `sewing_points`: `ZipCover.pick_edge` / `sewing_points.curve_edge`, option `Angle`); `Type` = `Zip` (`Z<n>`, `Parts::Zip`) / `Track` (canalina `Can<n>`, `Parts::Track`); `Trim` per type (Zip 4 cm, Track 0) — stops in from the real ends; split side → junction clicks; marks on the text's side (stop = leg across + 90° towards the middle, junction = short leg); text near the middle, inside the panel, first free spot; data on the text (UserText `Zip`, `ZipLine`, `ZipEdge`, `ZipAngle`, `ZipTrim`, `ZipLen`, `ZipSide`, `ZipJunction`, `ZipSize`) — flipping a number rebuilds its marks on the other side. `ZipList.py` — order table from the number texts, length live = edge found again (`ZipStops.edge_of`) − trims, else `ZipLen` with a warning: zips — two sides with the closest sums, the longer one, up to 1 cm, difference > 5 mm or one line — warning; tracks — full length; CSV `<file>_zips.csv` + clipboard. `MarkReinf.py` — reinforcement strip as ` R<w>` on an existing label (edge length in UserText); `RList.py` — strip table, length = edge + Plus (cm). `ReinfCircle.py` — corner reinforcement circle: click near a corner → sector of radius R between the sides, in place, label `RC<n>  r=…`, layer `Parts::Reinforcements` (other shapes — their own prefixes RS, RT…). `ReinfD.py` — D reinforcement at the end of a pocket: click top corner (centre of the end) → bottom corner, width W + extension R (half-circle / half-ellipse), `RD<n>`, same layer (uses `layer` / `next_number` / `text_style` from ReinfCircle). `ReinfO.py` — O reinforcement at a full-width pocket: boundary (panel) → click centre (top corner of the pocket) → click on a line, R = distance + Plus (5 cm), only inside the panel, `RO<n>`, same layer (uses `piece` from ReinfCircle). `Rinforzo.py` — rinforzo R (strip laid on the panel, not folded): panel + click near an edge → `ZipCover.flap(..., inward=True)`: strip W (6 cm) inward, ends along the neighbouring edges; the part for cutting is longer by `Plus` (10 cm, `flap(plus=…)`), the markup on the panel is not; label `R<w>  l=…`, no number, same layer. `Pettola.py` — pettola `Pt<w>`: Bordino with kind "Pettola" (`Bordino.KINDS`: code, default W 10 cm, layer `Parts::Pettola`), wider. `Bordino.py` — bordino B (folded over the edge, always a separate part): panel + click near an edge → straight rectangle W (3.5 cm; 4.5 rinforzato) × edge + `Plus` (6 cm) next to the panel outside + its copy `Up` up (`ReinfCircle.add_part`), label `B<w>`, layer `Parts::Bordino`; on the panel only `B<w>` (UserText `BordEdge`, `BordLine`) after `Z<n> R<w>`, also when the zip is on a zip line inside (`ZipStops.bordino_near`). `TubePockets.py` / `UpdateTubePockets.py` — tube pockets `T<n>` in `Parts::Pockets`. `PartPanel.py` — ` P<n>` on part labels, the panel found at run time from where the part sits (part up moved back down by `LayoutUp` / `TP_Up`, centroid → numbered curve in `Parts::Panels`; Bordino — from `BordEdge`); nothing stored when parts are made. `LayoutParts.py` — canvas for cutting: select parts with their markup (window), a copy of each part (closed curves + points / crosses / circles + label codes `P4`, `RC3`, `Z15` + a seam centre tick `Tick` at the middle of each markup line) in a row from the click point (Enter — continue the row), in sublayer `<layer>::Layout`; open lines, TextDots, long labels stay only on the schema; UserText `LayoutOf` on the copy. `LayoutStack.py` — strips that may turn along the grain (checkboxes Rinforzo / Bordini) on the canvas (LayoutParts `own` / `place`), turned along CPlane X, stacked down from the click `Gap` apart, longest first.
  - **`markup/`** ("Markup"): `PointsToCrosses.py` (points / clouds / TextDot → cross or circle), `line_type.py` + `linetype.gh` (linetype `400,2`), `PatternTextStyles.py` (+ `_check.py`), `TextToDot.py`, `DotToPanelText.py`, `TextToCurves.py` (text → curves for nesting, upside-down text is not mirrored — like Draw forward on screen), `Legend.py` (legend of script labels — only marks present, text at the click point, Lang = UA / EN / IT, default IT), `PanelPage.py` (selection → one new A4 Layout `P<n>`, detail Top, like Zoom Selected on the whole selection; one run — one sheet).
  - `build_scripts_rui.py` — builder of the `Scripts.rui` toolbar (6 tabs: Sizes / Curves / Analysis / Cut / Parts / Markup; shown in Italian: Misure / Curve / Analisi / Taglio / Pezzi / Segni).
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
- A part with a copy `Up` up (Reinf*, Rinforzo, Bordino, TubePockets): the markup on the panel and the copy up are **one group** (`ReinfCircle.add_part`); LayoutParts splits such a group by `PartMarkup` / `TP_Markup`.
- Scripts that **create parts** (strips, reinforcements etc.) live in `scripts/parts/`, put the result in layer `Parts::<Name>` and go to the **Parts** toolbar tab (`py("parts/<Script>.py")`).

## Toolbar (`Scripts.rui`)

- New script → add a line to `GROUPS` in `scripts/build_scripts_rui.py` (English) + its Italian name and tooltip to `IT` (and to the table in `README.md`).
- **Do NOT run the builder `build_scripts_rui.py`** — the user rebuilds `Scripts.rui` themselves (with Rhino closed). Remind them of the build command at the end of the reply.
- After every created / changed script, end the reply with the full button macro:
  `!_-RunPythonScript "/Users/dmytro/Documents/Rhino/scripts/<subfolder/><Script>.py"`

## Git

- Repository: https://github.com/Miity/rhino_scripts_panneling (public, branch `main`).
- After every finished change — commit and push: `git add -A && git commit -m "<what changed>" && git push`.
- `Patterns/` and `*.3dm` are in `.gitignore` (third-party patterns / working files) — do not add them to the repository.
