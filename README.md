# Rhino Scripts — toolbar

A set of Python scripts for Rhino 8 (cutting, patterns, cut preparation) and 6 toolbar tabs that launch them: **Sizes · Curves · Analysis · Cut · Parts · Markup**.

The toolbar is in **Italian** (customers and seamstresses are Italian): tabs **Misure · Curve · Analisi · Taglio · Pezzi · Segni**, Italian button names and tooltips (`IT` in `scripts/build_scripts_rui.py`). The English names and tooltips stay in `GROUPS` of the same file — `LANG = "EN"` builds an English toolbar. Below, buttons are listed by their English name.

| What | Where |
|---|---|
| Scripts (one subfolder per tab) | `scripts/sizes/` · `curves/` · `analysis/` · `cut/` · `parts/` · `markup/` |
| Grasshopper definitions | `Grasshoper scripts/*.gh` |
| Toolbar file (generated, do not edit by hand) | `Scripts.rui` |
| Toolbar builder — **the button list is edited here** | `scripts/build_scripts_rui.py` |
| Backup of the old `_Scripts` toolbar | `_backup_toolbar_20260930_2058/` |

### Labels — Italian codes, numbers in cm

Labels on the drawing are read by the seamstresses, so they are Italian codes; every number in a label is in **cm** (`w` — width, `l` — length, `h` — height, `r` — radius). Layers, prompts, options and docs stay English.

| Code | Meaning | Script |
|---|---|---|
| `P<n>` | pannello — panel | Panels |
| `F<w>  l=…` | fascia — strip | Strips |
| `Off<w>` | offset — zip / track cover flap (copri zip / canalina); `CZ<w>` in older drawings | ZipCover |
| `C<w>` | cucitura (with battute — seam points), usually 1 cm | ZipCover was used for it — now only `Off`; battute — Battute (`parts/sewing_points.py`) |
| `Z<n>` | zip | ZipStops, `Type=Zip` |
| `Can<n>` | canalina — track | ZipStops, `Type=Track` |
| `R<w>` | rinforzo — strip laid on the panel, not folded | Rinforzo (`R<w>`), Mark Reinf (` R<w>` on a label) |
| `RD<n>` / `RO<n>  r=…` | rinforzo D / O | Reinf D / O (RfD / RfO) |
| `T<n>` | tasca — pocket | Tube Pockets |
| `A–A`, `B–B`… | joint of panel pieces split to the material width | SplitToMaterial |

`B` (bordino, usually 3.5 cm) and `BR` (bordino reinf, usually 4.5 cm) are folded parts — not made by the scripts yet.

### Old drawings

New scripts do not recognise older labels (numbering, ZipList, MarkReinf, UpdateTubePockets, Legend), drawings are not converted. To keep working on an old drawing, use the matching version of the scripts from a git tag:

- `legacy-en` — English labels of 6–8 October 2026: `ZC W`, `SA W` (mm), `Trk<n>`, `S<n>`, `TP<n>  H=…`, `RB<n>` (script `ReinfBord.py`), `RC<n>  R=…` (mm);
- `legacy-ua-it` — before 6 October 2026: UA/IT names, layers `Parts::CopriZip`, `Parts::Canalina`, labels `CZ W`, `Can<n>`, `F<n>`.

```bash
git -C /Users/dmytro/Documents/Rhino worktree add ../Rhino-legacy legacy-en
```

---

## 1. Using the toolbar

Each group is a separate toolbar; all six sit as **tabs** in the top Rhino panel (next to Standard). Clicking a tab name shows its buttons.

| Action | Result |
|---|---|
| **Left click** a button | main script |
| **Right click** a button | second script (only where there is one — see the table) |
| Hover | tooltip |
| Drag a tab | move it elsewhere / tear it off into a separate window |

Scripts that work click after click (ZipCover, Join Corner, Battute, Panels, Reinf D / O, Rinforzo, Tube Pockets,
ZipStops, DotToPanelText) have the option **Undo** in the click prompt: it takes back the last click (again — the one
before it) without leaving the command; a number given in that click is reused. After the command ends, Rhino's own Undo works as usual.

### Groups

**Sizes** — `scripts/sizes/`
| Button | Left click | Right click |
|---|---|---|
| BBoxSize | bounding box in the CPlane with XYZ sizes | BBoxCenterLines — flat box + two centre lines |
| LabelSizes | label the size inside each closed curve | — |
| Rect 1340 | rectangle 1340 × 6658 centred on the CPlane | — |

**Curves** — `scripts/curves/`
| Button | Left click | Right click |
|---|---|---|
| SplitByAngle | split curves at corners sharper than the threshold | SmoothCorners — round such corners |
| CrvToPolyline | curves → polylines (layer kept) | — |
| TrimEnds | trim curve ends by a given distance | KeepEnds — cut out the middle, keep ends of a given length |
| TrimOutside | trim everything outside the panel contour | — |
| ExactConnection | contact point on a curve at a given length | — |
| MidLine | line from the midpoint of one curve to the midpoint of another | — |
| OffsetRigid | offset without changing the shape: a copy moved by D along the normal at the clicked point | — |

**Analysis** — `scripts/analysis/`
| Button | Left click |
|---|---|
| SmallClosed | select closed curves smaller than the minimum cut area |
| CutRisks | mark risky cut spots (geometry unchanged) |
| RecommendTabs | select contours that need tabs |
| CutTabs | interactively add tabs |

**Cut** — `scripts/cut/`
| Button | Left click |
|---|---|
| PreparePanelCut | any panel lines (closed, separate, seam strips, duplicates) → the outer contour of each panel on CUT, the rest on INT/INK (texts too) |
| SplitToMaterial | split panels at the material lines: 1 cm seam, cut-off pieces moved by 50 mm, pairs labelled A–A, B–B… |
| CurveOverlap | delete exact duplicates (SelDup), select the shorter curve of overlapping pairs (among selected, or all if nothing is selected) |

**Parts** — scripts that create parts (strips, reinforcements…); `scripts/parts/`, the result goes to layer `Parts::…`
| Button | Left click |
|---|---|
| Panels | selected closed curves → copy in place in `Parts::Panels`, number `P<n>`: text inside (click, Enter — corner) + TextDot above-left, UserText `Part`; numbered ones are skipped, nested curves = panel holes; numbering continues |
| SewingPoints (Battute) | `parts/sewing_points.py` — battute: select panels and / or curves, click near an edge (several, Enter — done) → only that edge corner to corner (`Angle`; a curve without corners — the whole curve, a closed or DXF "almost closed" panel — never the whole contour): points from the edge centre both ways with `Step` (default 200 mm) + centre tick `Tick` (default 10 mm, 0 — none): on a panel from the edge into the panel, on a curve symmetric across it; one group per edge, layer `Parts::SewingMarks`; inputs not changed; option `Undo` — removes the marks of the last click (again — the one before). Put battute before ZipCover with `EditPanel=Yes` (it widens the neighbouring edges). Right click — SewPoints GH (old Grasshopper version) |
| Strips | fascia strips under the selected curves: width W, length = curve length (+ allowance); stacked touching, in `Parts::Strips`, label `F<w>  l=…` (cm) on the strip and as a TextDot on the curve — no number, strips with the same `w` and `l` are the same |
| ZipCover | zip cover (copri zip / canalina): panel (closed curve: lines, polylines, arcs; DXF gap up to 1 mm is closed) + click near an edge (several in a row) → edge corner to corner (corner — break > `Angle`) + offset by `W` outward, ends along the extension of the neighbouring edges (neighbour sharper than 30° — perpendicular end); label `Off<w>` (cm, offset), layer `Parts::ZipCover`. Defaults: `W` 10, `Angle` 30, `EditPanel` No. `EditPanel`: `No` — only markup in place (strip lines not lying on the panel edge + label, one group), the panel is not changed, PreparePanelCut joins them before cutting; `Yes` — the panel contour itself grows by the strip (layer, groups, UserText kept), the old edge stays as a zip line + label. Seam points — Battute, a separate script |
| Join Corner | join any two open curves at a corner, edge to edge (like `Connect`): select curves (window allowed — texts and points are ignored), click near the corner (several corners, Enter — done); the two curve ends nearest the click are taken; edges run corner to corner (`Angle`); per end the last edge is joined or dropped (short end to the panel) — whichever pair meets nearest the click; edges extended (straight) / trimmed to their intersection, everything beyond removed, one curve: the first keeps layer / groups / UserText, the second is deleted and its group (label, seam points) merges in; both ends of one curve (frame) → closed; if the far ends also touch at another corner, that corner is joined too; one closed curve with a notch at a corner (inward break > `Angle` nearest the click) → joined there as a frame corner (panels with outward corners are not touched); parallel edges — skipped |
| Merge Outline | select a closed panel and the curve(s) that enclose an area together with it (ZipCover / Rinforzo outline, an overlapping panel, open curves forming a loop; same plane, ends touching): the outer line of everything they enclose becomes **one closed curve** that replaces the panel (the first closed one: layer / groups / UserText / label stay; the others are deleted, their groups merge in); pieces **not** on the outer line (the old panel edge now inside) are cut off and stay as **open curves**, one per source curve (source layer / groups, UserText `Part` removed). Original segments are kept (lines, arcs, no refit); undo — one step |
| ZipStops | mark zips and tracks — panels and curves are not touched: select panels (closed curves) and / or open curves, then click near each edge / curve of one zip on all panels (as in Battute: edge corner to corner, option `Angle`), Enter — next zip, Enter on an empty one — done; option `Type` — `Zip` (both sides, `Z<n>`, layer `Parts::Zip`) or `Track` (one side, canalina `Can<n>`, layer `Parts::Track`); option `Trim` — stops this far in from the real ends (remembered per type, Zip 4 cm, Track 0); split side (Zip 3+ edges, Track 2+) → click near a junction; marks on the text's side: stop = leg across + 90° along towards the middle, junction = short leg; number near the middle, inside the panel, in the first free spot; data on the text (UserText); clicking a number flips it and all its marks to the other side; `Undo` at every step |
| ZipList | order table: selected numbers (Enter — all). Length measured live: the marked panel edge / curve, found again, minus `Trim` (not found — length when marked, warning). Zips: lines of one `Z<n>` → two sides with the closest sums, the longer one is ordered, rounded up to 1 cm; difference > 5 mm or a single line — warning; summary "cm × pcs". Tracks: `Can<n>` full length (sum of lines), rounded up to 1 cm, total in cm. CSV `<file>_zips.csv` next to the `.3dm` + table to the clipboard |
| Mark Reinf | reinforcement strip as a mark only: select labels (window, on different panels; panel — the nearest closed curve with corners within 20 cm outside `Parts::` or in `Parts::Panels`, no panel nearby — skipped) → ` R<w>` (option `W`, label in cm) appended to the text (an old one is replaced, W=0 removes it); edge length (corner to corner, closest to the label) — UserText `ReinfLen` |
| RList | strip table: labels with `Reinf` (selected / Enter — all), length = edge + `Plus` (asked, cm, default 10 — half past each end), rounded up to 1 cm; totals by width; CSV `<file>_reinf.csv` + clipboard |
| Reinf D | D reinforcement at the end of a tube pocket: click the top corner of the pocket (half-circle centre) → click the bottom corner (where the D starts, the D is shown live); rectangle of width `W` (default 100) + an end `R` past the corner (default 50; W = 2R — half-circle, otherwise half-ellipse W/2 × R); label `RD<n>`, group; in `Parts::Reinforcements`, one for each pocket end. Option `Layout` (default Yes): only markup on the panel (lines not on panel edges + label), the full part `Up` (default 10000, shared by all part scripts) up along CPlane Y; `Layout=No` — full part in place |
| Reinf O | O reinforcement at the end of a full-width pocket: pick a boundary (panel / corner lines; Enter — no trimming) → click the top corner of the pocket (circle centre) → click on a line: R = distance to the click + `Plus` (default 5 cm; the O is shown live); with a panel only the part of the circle inside the panel is kept; `SA` (default 1 cm) — sides along the panel edge extend outward by SA, the arc stays at R; seam line — panel edges inside the circle, label `RO<n>  r=…` (cm) along the arc, group; in `Parts::Reinforcements`. Option `Layout` (default Yes): only markup on the panel (lines not on panel edges + label), the full part `Up` (default 10000, shared by all part scripts) up along CPlane Y; `Layout=No` — full part in place |
| Reinf Strip (Rinforzo) | `parts/Rinforzo.py` — reinforcement `R`, a strip laid on the panel without folding: selected panel → click near an edge (corner to corner, `Angle` as in ZipCover) → like ZipCover, but inward: edge + offset by `W` (default 6 cm) into the panel, ends along the neighbouring edges (sharper than 30° — perpendicular); `Plus` (default 10 cm) — the part for cutting is that much longer than the edge (half past each end, straight on), trimmed after sewing; the panel is not changed; label `R<w>` (cm; ≈ W/10, at a quarter of the edge, along the inner line on the strip side), no number, group; if the strip holds a zip (a ZipStops number whose edge midpoint is on the strip: the panel edge itself or a zip line inside it, e.g. the old edge after ZipCover) — made before or later — the label stands right after it (`Z20  R6`: two texts, each in its own group, so deleting the strip deletes `R6`; flipping the number moves the label with it), and the full part on the canvas gets the zip's stops, the zip line between them and the label `Z20 R6`; in `Parts::Reinforcements`. Option `Layout` (default Yes): only markup on the panel (the inner line, without Plus, + label), the full part `Up` (default 10000, shared by all part scripts) up along CPlane Y; `Layout=No` — full part in place |
| Tube Pockets | tube pockets in a cover: selected panel → click near an edge (corner to corner, `Angle` as in ZipCover) → a segment of width W centred on the edge (0 — the whole edge), offset by H into the panel, the offset line shorter by `Trim` at each end (narrowing), no seam allowance — the pocket bottom is the panel edge (the seam is already on the panel), `Hem` (default 20) — hem allowance at the ends: the end moves outward by Hem, top and bottom extended straight, the old end becomes a fold line (sublayer `Parts::Pockets::Fold`, in the group), option `Notch` — centre mark, `Rigid` — pocket top by rigid offset (like OffsetRigid: edge shape unchanged, H along the normal at the centre); label `T<n>` (h is kept in UserText `TP_H`); in `Parts::Pockets`. Option `Layout` (default Yes): only markup stays on the panel (ends + pocket top without the edge and Hem + label, its own group), the full part `Up` (default 10000, shared by all part scripts) up along CPlane Y, that is what Layout lays out; `Layout=No` — full part in place |
| Update Pockets | update existing TubePockets pockets: select any part of a pocket (or several with a window) → new `H` / `Trim` / `Hem` / `Notch` / `Rigid`; the pocket is rebuilt from its edge in place (an old `SA` is dropped), same `T<n>`, layer and side; only what you changed changes; you can select the markup on the panel or the part above — both are rebuilt. Parameters in UserText `TP_*`, in old pockets — from geometry. Copies in Layout are not updated |
| Layout | canvas for cutting: select parts together with their markup (window over panels and parts above); part = group with a closed curve on a `Parts::` layer (not panel markup). The copy gets only: closed curves (contour, holes), points / crosses (buttons) / circles (seams), labels shortened to the code (`RC3  r=4` → `RC3`, `P4`, `Z15`, `F5`, `CZ3.5`; no code — not copied), a seam centre tick `Tick` (default 20 mm) at the middle of each markup line (on the contour — into the part, inside — across; lines shorter than 4 × Tick — none). Open lines, TextDots, long labels stay only on the schema. Row from the click point (Enter — continue the row), sublayer `<layer>::Layout`, UserText `LayoutOf`; already laid out — skipped |

**Markup** — `scripts/markup/`
| Button | Left click | Right click |
|---|---|---|
| Crosses | points → crosses or circles | — |
| Linetype 400,2 | assign linetype `400,2` | — |
| TextStyles | create/update PAT 2.5–40 mm text styles | — |
| TextToDot | text → TextDot | DotToPanelText — TextDot → text in the panel corner (INK) |
| TextToCurves | text → curves for the nesting program: like `Explode`, but text with a flipped plane (after Mirror, 180° rotation, another CPlane) is not mirrored — the curves lie like the text on screen in the Top view (Draw forward); layer / colour / groups of the original, text without a group → letters in a new group; the original is deleted | — |
| Legend | label legend (P, F, Off, C, Z, Can, R, RC, RD, RO, T, A–A) — only those present in the drawing, as text at the click point; option Lang = IT (default) / EN / UA | — |
| Panel Page | sheet for PDF: selected objects (panel contour or any of its parts) → one new A4 Layout (always portrait — Print on Mac uses one orientation for all sheets), one Top detail aimed at the whole selection (like Zoom Selected), scale as in Zoom Selected (the selection fills the frame, not rounded), the detail is not locked; name — UserText `Part` / label `P<n>` within the selection / the next free `P<n>`; one run — one sheet; labels are not touched | — |

Deliberately left off the toolbar: `BoundingBoxWithSize.py` (old version), `GH_SplitCurveByAngle.py` (code for a GHPython component), `PatternTextStyles_check.py` (check), `build_scripts_rui.py` (builder).

---

## 2. Where to find the toolbar

Tabs **Sizes / Curves / Analysis / Cut / Parts / Markup** — in the top toolbar panel.

**A tab disappeared** — in Rhino: menu **Window → Toolbars** (or the `Toolbar` command), find the **Scripts** library, enable the toolbar you need. It appears as a floating window — drag it by its tab into the top panel.

**Rhino does not know the toolbar at all** (new computer, reset settings) — `Scripts.rui` is not in git, build it first (`python3 scripts/build_scripts_rui.py`), then open it once. The most reliable way is via `_ScriptEditor` → new Python script → Run:

```python
import Rhino
Rhino.RhinoApp.ToolbarFiles.Open("/Users/dmytro/Documents/Rhino/Scripts.rui")
```

Then show the toolbars as described above. Rhino remembers the file and opens it itself.

---

## 3. Adding a script

1. Put the file in its tab's subfolder, e.g. `scripts/curves/MyNewScript.py`.
2. Open `scripts/build_scripts_rui.py` and in the `GROUPS` list, in the right group, add a line:

   ```python
   (u"MyNew", u"What the script does — tooltip", py("curves/MyNewScript.py"), None),
   ```

   - `u"MyNew"` — English button text (short); it is also the key of the button GUID.
   - `u"What the script does…"` — English tooltip.
   - Add the Italian name and tooltip to `IT` in the same file: `u"MyNew": (u"Nome", u"Cosa fa lo script"),` — the toolbar shows these (`LANG = "IT"`).
   - `py("curves/MyNewScript.py")` — path to the file from `scripts/`. The file goes in its tab's subfolder: `sizes/` (Sizes), `curves/` (Curves), `analysis/` (Analysis), `cut/` (Cut), `parts/` (Parts), `markup/` (Markup).
   - `None` — nothing on right click. To put a second script there:
     ```python
     (u"MyNew", u"Tooltip", py("curves/MyNewScript.py"),
      (u"MyNew 2", u"Second tooltip", py("Other.py"))),
     ```
   - Line order = button order.
   - For a Grasshopper file write the macro as a string instead of `py(...)`, like `GH_SEW` in the same file.

3. **Close Rhino** and rebuild the toolbar (only the user builds it — Claude only edits `GROUPS` and does not run the builder):

   ```bash
   python3 /Users/dmytro/Documents/Rhino/scripts/build_scripts_rui.py
   ```

   It should print `OK -> …/Scripts.rui`. If a file is missing it stops with `Missing files: …` and breaks nothing.

4. Start Rhino — the button is there.

**New group** — add another block to `GROUPS` following the existing ones: `(u"Name", u"Group description", [ ...button lines... ]),`. Group name = tab name. After the first run the new tab must be shown and dragged into the top panel (section 2).

---

## 4. Removing a script from the toolbar

1. In `scripts/build_scripts_rui.py` delete its line from `GROUPS`.
   - If the script is on the **right** click — replace the whole `(u"...", u"...", py("..."))` block with `None`.
   - To remove **a whole group** — delete its block entirely.
2. Close Rhino, run `python3 scripts/build_scripts_rui.py`, open Rhino.

The script file itself stays in `scripts/`. If you delete the file from disk — remove its line **first**, otherwise the builder stops with `Missing files`.

**Renaming / moving a file** — update the name in `py("...")`, rebuild. **Moving a button between groups** — move the line to the other group, rebuild.

---

## 5. Important

- **Edit only `build_scripts_rui.py`, not `Scripts.rui`.** `Scripts.rui` is overwritten on every build.
- **Build the toolbar with Rhino closed.** An open Rhino keeps its own copy of the toolbar in memory and may write it over the new one on exit — and the newly added buttons disappear.
- The toolbar position survives a rebuild: button and group ids are stable (derived from the names). But if you **rename** a button or a group, Rhino treats it as new (that is why the tabs renamed to English in October 2026 had to be placed again).
- The script path comes from the project folder location. If the `Rhino` folder is moved — rebuild the toolbar and open `Scripts.rui` again (section 2).
- Script compatibility: IronPython 2.7 and CPython 3 (Rhino 8), units and tolerances — from the document.

---

## 6. Troubleshooting

| Symptom | What to do |
|---|---|
| A tab is not on screen | Section 2. |
| A button does nothing / "file not found" in the command line | The file was renamed or moved — fix `py("...")` and rebuild. |
| New buttons disappeared after quitting Rhino | It was built with Rhino open. Close Rhino and rebuild. |
| Old tabs (Розміри / Криві / …) still show next to the new ones | They come from the previous build: Window → Toolbars, turn them off (or close and reopen `Scripts.rui`). |
| Need the old `_Scripts` toolbar | With Rhino closed copy the contents of `_backup_toolbar_20260930_2058/Scheme__Default/` to `~/Library/Application Support/McNeel/Rhinoceros/8.0/settings/Scheme__Default/`. Note: the old buttons point to old file names (`SplitCrvByAngle copy.py`, `sel_curve_overlap.py` in the root). |
