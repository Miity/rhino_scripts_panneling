# -*- coding: utf-8 -*-
"""Panels → parts P1, P2, P3…
Select closed curves (panels). Each panel is copied in place to layer Parts::Panels,
the input curve (and its holes) is deleted. The copy gets number P<n>: text inside the panel in the corner you click near (Enter — top right;
placement as in markup/DotToPanelText.py), style — option Style (remembered, default PAT 14 mm),
and a TextDot "P<n>" (sublayer Parts::Panels::Dots) above-left of the panel edge, so the number is visible at any zoom.
The number is written to the copy's UserText (Part = P<n>): a repeated run
skips curves already in Parts::Panels with a number. A new panel gets the smallest free number in the layer,
so the number of a deleted panel is reused.
A curve lying inside another selected one is a hole of that panel: it is copied together with it
under the same number and does not take its own number. Copy, holes, text and TextDot are one group.
"""
import os
import re
import sys

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
from Rhino.Geometry import Curve, RegionContainment

# text placement in a panel corner and style picking — from scripts/markup/DotToPanelText.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
for _m in ("DotToPanelText", "PatternTextStyles"):  # Rhino keeps modules from the first run for the session
    sys.modules.pop(_m, None)
import DotToPanelText as D

LAYER = "Parts::Panels"
DOTS = LAYER + "::Dots"  # TextDot — in a separate sublayer, everything else in LAYER
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

PREFIX = "P"
KEY = "Part"  # UserText key with the panel number
STYLE = "Panels"  # sticky key of the label style (PatternTextStyles.label_style)


def bbox(crv, plane):
    """(xmin, ymin, xmax, ymax) of the curve in plane coordinates."""
    b = crv.GetBoundingBox(plane)
    return b.Min.X, b.Min.Y, b.Max.X, b.Max.Y


def classify(curves, plane, tol):
    """[(i, [hole indices])] — outer panels in reading order: rows top to bottom, left to right within a row."""
    holes = {}
    outer = []
    for i, a in enumerate(curves):
        parent = None
        for j, b in enumerate(curves):
            if i != j and Curve.PlanarClosedCurveRelationship(a, b, plane, tol) == RegionContainment.AInsideB:
                if parent is None or Curve.PlanarClosedCurveRelationship(
                        curves[parent], b, plane, tol) == RegionContainment.AInsideB:
                    parent = j  # the largest container: a hole in a hole still belongs to the outer panel
        if parent is None:
            outer.append(i)
        else:
            holes.setdefault(parent, []).append(i)
    boxes = dict((i, bbox(curves[i], plane)) for i in outer)
    order, rows = sorted(outer, key=lambda i: -boxes[i][3]), []
    for i in order:  # new row when the panel top is below the bottom of the first panel of the current row
        if rows and boxes[i][3] > boxes[rows[-1][0]][1]:
            rows[-1].append(i)
        else:
            rows.append([i])
    return [(i, holes.get(i, [])) for row in rows for i in sorted(row, key=lambda k: boxes[k][0])]


def layer():
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Panels", parent="Parts")
    if not rs.IsLayer(DOTS):
        rs.AddLayer("Dots", parent=LAYER)
    return LAYER


def num(s):
    """P4 → 4, otherwise None."""
    m = re.match(PREFIX + r"(\d+)$", s or "")
    return int(m.group(1)) if m else None


def used_numbers(lay):
    """Used numbers P<n> in the layer (UserText, text or TextDot)."""
    nums = set()
    for o in rs.ObjectsByLayer(lay) or []:
        s = rs.GetUserText(o, KEY) or (rs.TextObjectText(o) if rs.IsText(o) else
                                       rs.TextDotText(o) if rs.IsTextDot(o) else "")
        if num(s):
            nums.add(num(s))
    return nums


def get_corner(doc, crv, name):
    """Click near a panel corner for the text; Enter — top right; options Style, Undo. Point, UNDO or None."""
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near a panel corner for %s (Enter — top right, style: %s)"
                           % (name, D.pts.label_style(doc, STYLE).Name))
        gp.AcceptNothing(True)
        i_undo = gp.AddOption("Undo")
        opt = gp.AddOption("Style")
        res = gp.Get()
        if res == Rhino.Input.GetResult.Option and gp.OptionIndex() == i_undo:
            return UNDO
        if res == Rhino.Input.GetResult.Option and gp.OptionIndex() == opt:
            D.pts.pick_style(doc, STYLE)
            continue
        if res == Rhino.Input.GetResult.Point:
            return gp.Point()
        if res == Rhino.Input.GetResult.Nothing:
            return crv.GetBoundingBox(True).Max
        return None


HELP = u"""Options:
  Style — text style of the number P<n> (default PAT 14 mm)
  Undo — take back the previous panel (its number is freed, the input curve is back) and label it again"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select panels (closed curves)", rs.filter.curve, preselect=True)
    if not ids:
        return
    picked = list(ids)
    tol = doc.ModelAbsoluteTolerance
    plane = rs.ViewCPlane()

    # a finished panel is a curve in LAYER with a number; old tags on curves in other layers do not interfere
    done = [i for i in ids if rs.ObjectLayer(i) == LAYER and rs.GetUserText(i, KEY)]
    bad = [i for i in ids if i not in done and not (rs.IsCurveClosed(i) and rs.IsCurvePlanar(i))]
    ids = [i for i in ids if i not in done and i not in bad]
    if done:
        print(u"Already numbered, skipped: %d" % len(done))
    if bad:
        print(u"Not closed or not planar, skipped: %d" % len(bad))
    if not ids:
        return

    curves = [rs.coercecurve(i) for i in ids]
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer(), -1)
    dot_attrs = attrs.Duplicate()
    dot_attrs.LayerIndex = doc.Layers.FindByFullPath(DOTS, -1)
    used = used_numbers(LAYER)
    made = 0
    steps = Steps(doc)
    items = list(classify(curves, plane, tol))
    done_n = []  # numbers given, per labelled panel — for Undo
    while made < len(items):
        i, hole_idx = items[made]
        n = min(k for k in range(1, len(used) + 2) if k not in used)  # smallest free: a gap after deletion is filled
        name = u"%s%d" % (PREFIX, n)
        crv = curves[i]
        rs.UnselectAllObjects()
        rs.SelectObject(ids[i])  # highlight which panel is being labelled now
        click = get_corner(doc, crv, name)
        if click is None:
            break
        if click == UNDO:
            if done_n and steps.undo():
                used.discard(done_n.pop())
                made -= 1
            elif not done_n:
                print(u"Nothing to undo")
            continue
        used.add(n)
        done_n.append(n)
        steps.start()
        ds = D.pts.label_style(doc, STYLE)
        # TextDot near the top-left of the panel: curve point closest to the bbox corner, slightly up-left
        x0, y0, x1, y1 = bbox(crv, plane)
        ok, t = crv.ClosestPoint(plane.PointAt(x0, y1))
        gap = 2 * ds.TextHeight * ds.DimensionScale
        dot = Rhino.Geometry.TextDot(name, crv.PointAt(t) + (plane.YAxis - plane.XAxis) * gap)

        tagged = attrs.Duplicate()
        tagged.SetUserString(KEY, name)
        new = [doc.Objects.AddCurve(curves[k], tagged) for k in [i] + hole_idx]
        for k in [i] + hole_idx:  # input curves are deleted (Undo restores them)
            steps.delete(ids[k])
        tid = D.place_text(doc, name, crv, click, ds, attrs, tol)
        if not tid:
            print(u"%s: text does not fit in the panel (smaller style — option Style), TextDot kept" % name)
        new += [o for o in (tid, doc.Objects.AddTextDot(dot, dot_attrs)) if o]
        rs.AddObjectsToGroup(new, rs.AddGroup())
        doc.Views.Redraw()
        print(u"%s%s" % (name, u"  (holes: %d)" % len(hole_idx) if hole_idx else u""))
        made += 1
    rs.UnselectAllObjects()
    rs.SelectObjects([o for o in picked if rs.IsObject(o)])  # selection as before (without deleted ones)
    print(u"Panels: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
