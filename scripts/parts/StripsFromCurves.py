# -*- coding: utf-8 -*-
"""Strips under the selected lines: a rectangle of height H and length = line length.
Each selected curve is a separate strip (nothing is joined automatically).
If a strip must run along several lines — join them (_Join) into one curve first.
Strips for cover edge binding or edge reinforcement — depends on the chosen height.

Strips are stacked in a column touching each other from the given point (along CPlane), in layer Parts::Strips; each labelled "S1  L=… × H".
The same number is placed as a TextDot at the middle of the corresponding line, to know which strip goes where.
"""
import re

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

STICKY = "StripsFromCurves"


def strips(curves):
    """One strip per curve. Returns [(length, midpoint)]."""
    out = []
    for c in curves:
        length = c.GetLength()
        ok, t = c.LengthParameter(length / 2.0)
        out.append((length, c.PointAt(t) if ok else c.PointAtStart))
    return out


def strips_layer():
    """Parts::Strips — creates it if missing."""
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer("Parts::Strips"):
        rs.AddLayer("Strips", parent="Parts")
    return "Parts::Strips"


def next_number(layer):
    """Next number after the largest S<n> already in the layer (text or TextDot)."""
    nums = [0]
    for o in rs.ObjectsByLayer(layer) or []:
        m = re.match(r"S(\d+)\b", rs.TextObjectText(o) if rs.IsText(o) else
                     rs.TextDotText(o) if rs.IsTextDot(o) else "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


def main():
    ids = rs.GetObjects(u"Select curves for strips (each curve is a separate strip)", rs.filter.curve, preselect=True)
    if not ids:
        return
    prev_h, prev_extra = sc.sticky.get(STICKY, (50.0, 0.0))
    h = rs.GetReal(u"Strip height", prev_h, 0.001)
    if h is None:
        return
    extra = rs.GetReal(u"Length allowance (added to each strip)", prev_extra, 0.0)
    if extra is None:
        return
    sc.sticky[STICKY] = (h, extra)

    found = strips([rs.coercecurve(i) for i in ids])
    found.sort(key=lambda x: -x[0])

    base = rs.GetPoint(u"Point to place the strips from (top-left corner)")
    if not base:
        return
    plane = rs.MovePlane(rs.ViewCPlane(), base)
    layer = strips_layer()
    txt_h = min(h * 0.4, 30.0)
    rs.EnableRedraw(False)
    try:
        first = next_number(layer)
        for i, (length, mid) in enumerate(found, 1):
            n = first + i - 1
            w = length + extra
            p = Rhino.Geometry.Plane(plane.PointAt(0, -i * h), plane.XAxis, plane.YAxis)
            rect = rs.AddRectangle(p, w, h)
            rs.ObjectLayer(rect, layer)
            label = u"S%d  L=%.0f × %g" % (n, w, h)
            tp = Rhino.Geometry.Plane(p.PointAt(txt_h * 0.5, h / 2.0), p.XAxis, p.YAxis)
            t = rs.AddText(label, tp, txt_h, justification=131073)  # left, vertical middle: stays inside the strip
            if t:
                rs.ObjectLayer(t, layer)
            d = rs.AddTextDot(u"S%d" % n, mid)
            rs.ObjectLayer(d, layer)
            print(u"S%d: length %.1f (+%g) → %.1f × %g" % (n, length, extra, w, h))
    finally:
        rs.EnableRedraw(True)
    print(u"Lines: %d → strips: %d" % (len(ids), len(found)))


if __name__ == "__main__":
    main()
