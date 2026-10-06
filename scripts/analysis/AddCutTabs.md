# Cutting tabs — AddCutTabs

Script for Rhino 6/7/8: manual placement of short gaps in the cut on closed planar curves. Supports polylines and NURBS. All selected contours must lie in one plane.

## Toolbar button

Paste into the Macro field:

```text
! _-RunPythonScript "/Users/dmytro/Documents/Rhino/scripts/analysis/AddCutTabs.py"
```

## Usage

1. Run the button and select the contours. Preselection works too.
2. Enter the tab width in document units. In a millimetre document the default is 0.5 mm; this is a trial value to be tuned to the material and knife settings.
3. Hover over a contour: a green segment shows the future tab. A click adds it; it turns orange. Orange means "do not cut this section".
4. Clicking an orange section again removes the tab. If several contours are close, zoom in for precise picking.
5. Enter applies the result. Esc cancels the whole preview.

Command line options:

| Option | Action |
| --- | --- |
| Move | Click an existing tab, then the new position. Enter returns to the normal mode without moving. |
| Width | Changes the width of all tabs in the current run. |
| Undo | Undoes the last add, remove, move or width change. |
| Clear | Removes all tabs of the current run. |

A red cross means the new tab is too large or overlaps another one. The width is measured along the curve. Crossing the start of a closed contour is handled; no extra gap is created at the start.

## Result and export

After Enter the script creates open cut curves with real gaps and the attributes of the source curves. Originals of the processed contours are hidden. Curves without tabs stay as they are.

For export, the new cut sections are selected automatically together with the rest of the initially selected contours. Use **Export Selected**. Preview marks are not document objects and do not end up in the DXF.

After the command, Rhino Undo returns to the state before the operation. The Show command can restore the hidden originals, but they will overlap the new curves: do not include them in the cut file.

The current version edits tabs within one run. To redo them after applying, undo the operation and run the script again.

On a trial cut, check that the plotter software does not join the ends across the gaps and that knife compensation / cut overrun does not cut through the tabs.

## Checks

- 12 automatic checks: crossing the contour start, overlaps, short remainders, 400 distribution variants and recovery from errors while creating the result.
- 180 split cases run inside Rhino 8.24 on Mac: a circle, a rectangular polyline and copies of 43 closed curves of an open document. Lengths and openness of the results checked; the drawing was not edited.
- The full interactive click cycle and an actual plotter cut have not been checked yet.
