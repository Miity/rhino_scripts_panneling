# Parts that are candidates for tabs

Toolbar button macro:

```text
! _-RunPythonScript "/Users/dmytro/Documents/Rhino/scripts/analysis/RecommendCutTabs.py"
```

1. Select part contours and run the script.
2. Set the area threshold and the width threshold. For a millimetre document the defaults are **50 mm²** and **3 mm**. These are starting settings for a trial cut, not guaranteed limits for paper.
3. Look at the marks on layers `TABS_CHECK::Recommended` and `TABS_CHECK::Review`.
4. The script selects the whole contours of candidates of both levels. Keep the ones you need and run the AddCutTabs button.

**Red marks**: small area or narrow shape overall. The narrow shape indicator equals `2 × area / perimeter`. For a long strip it is close to its width, but it is not a measurement of the minimum width of an arbitrary part.

**Orange marks**: a local narrowing worth reviewing. The script looks for opposite sides coming close inside the contour; it skips the short neighbourhood of a turn. For NURBS it uses a polyline approximation with the document tolerance. This is a geometric heuristic that may miss some thin protrusions.

The mark text gives the reason and the measurement. Area — in square document units, width — in document units. Check the scale of an imported DXF.

Curves are kept with unchanged geometry and attributes. A repeated run replaces the previous marks of this script. Open contours, including those already processed by AddCutTabs, are skipped. Skipped objects and the reasons are printed in the command history. Each closed contour is assessed independently: areas of nested holes are not subtracted. The script does not decide which side remains the finished product.

Two different contours being close and a sharp corner do not by themselves trigger a recommendation. Holding also depends on the material, vacuum, knife and cutting order. An unmarked part has no stability guarantee.

For the following AddCutTabs run the selected candidates must lie in one plane. Do not include the marks in the DXF: export the selected cut curves.

Checked with 11 automatic tests (small parts, long strips, necks, empty slots, contour rotation/direction, vertex density and scale). In Rhino 8 on Mac, 5 synthetic shapes and 43 contours of an open document were checked without changing the drawing.

Creating and replacing marks was checked in a separate temporary Rhino document; a repeated run does not accumulate old marks.
