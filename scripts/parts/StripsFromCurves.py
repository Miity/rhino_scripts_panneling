# -*- coding: utf-8 -*-
"""Fascia (F) strips under the selected lines: a rectangle of width W and length = line length.
Each selected curve is a separate strip (nothing is joined automatically).
If a strip must run along several lines — join them (_Join) into one curve first.
Strips for cover edge binding or edge reinforcement — depends on the chosen width.

Strips are stacked in a column touching each other from the given point (along CPlane), in layer Parts::Strips;
each labelled "F<w>  l=<l>" (cm, l — with the allowance). The same label is placed as a TextDot at the middle
of the corresponding line, to know which strip goes where (no number: strips with the same w and l are the same).
Option Style (at the width prompt) — label text style, default PAT 14 mm.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
sys.modules.pop("PatternTextStyles", None)  # Rhino keeps modules from the first run for the session
import PatternTextStyles  # label style: option Style, default PAT 14 mm

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


HELP = u"""Options:
  Style — label text style (default PAT 14 mm)"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    ids = rs.GetObjects(u"Select curves for strips (each curve is a separate strip)", rs.filter.curve, preselect=True)
    if not ids:
        return
    prev_w, prev_extra = sc.sticky.get(STICKY, (50.0, 0.0))
    w = PatternTextStyles.get_number(u"Strip width W", prev_w, STICKY, 0.001)
    if w is None:
        return
    extra = rs.GetReal(u"Length allowance (added to each strip)", prev_extra, 0.0)
    if extra is None:
        return
    sc.sticky[STICKY] = (w, extra)

    found = strips([rs.coercecurve(i) for i in ids])
    found.sort(key=lambda x: -x[0])

    base = rs.GetPoint(u"Point to place the strips from (top-left corner)")
    if not base:
        return
    plane = rs.MovePlane(rs.ViewCPlane(), base)
    layer = strips_layer()
    style = PatternTextStyles.label_style(sc.doc, STICKY)
    txt_h = style.TextHeight * style.DimensionScale
    rs.EnableRedraw(False)
    try:
        for i, (length, mid) in enumerate(found, 1):
            l = length + extra
            p = Rhino.Geometry.Plane(plane.PointAt(0, -i * w), plane.XAxis, plane.YAxis)
            rect = rs.AddRectangle(p, l, w)
            rs.ObjectLayer(rect, layer)
            label = u"F%s  l=%s" % (PatternTextStyles.cm(w), PatternTextStyles.cm(l))
            tp = Rhino.Geometry.Plane(p.PointAt(txt_h * 0.5, w / 2.0), p.XAxis, p.YAxis)
            te = Rhino.Geometry.TextEntity.Create(label, tp, style, False, 0, 0)
            te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Left
            te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle  # stays inside the strip
            text = PatternTextStyles.label_attrs(sc.doc, rs.coercerhinoobject(rect).Attributes)  # Labels::Strips
            sc.doc.Objects.AddText(te, text)
            sc.doc.Objects.AddTextDot(label, mid, text)
            print(u"%s: length %.1f (+%g)" % (label, length, extra))
    finally:
        rs.EnableRedraw(True)
    print(u"Lines: %d → strips: %d" % (len(ids), len(found)))


if __name__ == "__main__":
    main()
