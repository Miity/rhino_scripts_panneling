# -*- coding: utf-8 -*-
"""Bordino (B): a straight strip folded over a panel edge — always a separate part, never part of the panel.
Select a panel (closed curve) and click near an edge (several in a row, Enter — done); the edge is taken corner to
corner (corner — tangent break larger than Angle, as in ZipCover).
The part is a rectangle W × (edge length + Plus), straight even if the edge is curved, laid next to the panel
(outside, along the edge chord, GAP from the edge), label "B<w>" (cm) on it; part + label one group; the length is
only in the command history. A copy of the part (with its label) goes Up (default 10000, shared by all part scripts)
up along CPlane Y, as Rinforzo's full part.
W: 3.5 cm — bordino, 4.5 cm — bordino rinforzato. Plus (default 6 cm) — cut longer, trimmed after sewing.
The panel is not changed, no markup lines on it — only the label "B<w>" (no number): if the edge has a ZipStops
number it stands right after it, after R<w> if there is one ("Z20  R6  B3.5"; made before or later, follows a flip;
the number may be on a zip line inside the panel — the old edge after ZipCover, ZipStops.bordino_near),
else inside the panel at three quarters of the edge. Layer Parts::Bordino.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.DocObjects import TextHorizontalAlignment, TextVerticalAlignment
from Rhino.Geometry import CurveOrientation, Plane, Polyline, PolylineCurve, TextEntity, Vector3d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _m in ("ReinfCircle", "ZipCover", "ZipStops"):  # Rhino keeps modules from the first run for the session
    sys.modules.pop(_m, None)
from ReinfCircle import UP_KEY, add_part, up_option  # copy of the part Up up, as Rinforzo
from ZipCover import cm, label_style, layer_attrs, pick_edge, pick_style
from ZipStops import BORD_EDGE, BORD_LINE, bordino_near, labels_after, mid_point, point_at, zip_text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

STICKY = "Bordino"
CODE = "B"
GAP_MM = 20.0  # part this far from the edge (outermost point of a curved edge)


def readable(u, normal):
    """Text plane axes along u, reading left to right."""
    if u.X < -1e-9 or (abs(u.X) < 1e-9 and u.Y < 0):
        u = -u
    return u, Vector3d.CrossProduct(normal, u)


def part(edge, out, w, plus, gap):
    """Rectangle W × (edge length + plus) along the edge chord, centred on it, outside (out) beyond the edge's
    outermost point + gap. Returns (rectangle, centre, chord direction)."""
    s = edge.PointAtStart
    d = edge.PointAtEnd - s
    c = s + d * 0.5
    d.Unitize()
    n = out(d)
    off = max([(edge.PointAt(t) - s) * n for t in edge.DivideByCount(64, True)] + [0.0]) + gap
    half = (edge.GetLength() + plus) / 2.0
    pts = [c - d * half + n * off, c + d * half + n * off, c + d * half + n * (off + w), c - d * half + n * (off + w)]
    return PolylineCurve(Polyline(pts + [pts[0]])), c + n * (off + w / 2.0), d


def ask(gp):
    """Click near an edge with options Undo / W / Plus / Angle / Up / Style. A point, UNDO or None (Enter / Esc)."""
    unit = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    i_undo = gp.AddOption("Undo")
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 35.0 * unit), 0.001, 1e6)
    plus = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_plus", 60.0 * unit), 0.0, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get("ZipCover_angle", 30.0), 1.0, 179.0)  # shared with ZipCover
    gp.AddOptionDouble("W", w)
    gp.AddOptionDouble("Plus", plus)
    gp.AddOptionDouble("Angle", a)
    up = up_option(gp)
    i_style = gp.AddOption("Style")
    while True:
        r = gp.Get()
        sc.sticky[STICKY] = w.CurrentValue
        sc.sticky[STICKY + "_plus"] = plus.CurrentValue
        sc.sticky["ZipCover_angle"] = a.CurrentValue
        sc.sticky[UP_KEY] = up.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_undo:
                return UNDO
            if gp.OptionIndex() == i_style:
                pick_style(sc.doc, STICKY)
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options:
  Undo — take back the last click (again — the click before it)
  W — strip width (B<w> in the label, cm): 3.5 cm bordino, 4.5 cm bordino rinforzato
  Plus — the strip is longer than the edge by this much, trimmed after sewing (default 6 cm)
  Angle — a break larger than this angle = panel corner (the edge is taken corner to corner)
  Up — how far up (along CPlane Y) the copy of the part goes; shared by all part scripts (default 10000)
  Style — label text style (default PAT 14 mm)"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    oid = rs.GetObject(u"Select a panel (closed curve)", rs.filter.curve, preselect=True)
    if not oid:
        return
    panel = rs.coercecurve(oid)
    tol = doc.ModelAbsoluteTolerance
    ok, plane = panel.TryGetPlane(tol)
    normal = plane.ZAxis if ok else rs.ViewCPlane().ZAxis
    cw = panel.ClosedCurveOrientation(normal) == CurveOrientation.Clockwise

    def out(t):  # away from the panel for a direction t along the panel's own direction (edge segments keep it)
        v = Vector3d.CrossProduct(normal, t) if cw else Vector3d.CrossProduct(t, normal)
        v.Unitize()
        return v
    attrs = layer_attrs(doc, "Bordino")
    gap = GAP_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    made = 0
    steps = Steps(doc)
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near the edge for the bordino (Enter — done)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        if click == UNDO:
            if steps.undo():
                made -= 1
            continue
        w, plus, angle = sc.sticky[STICKY], sc.sticky[STICKY + "_plus"], sc.sticky["ZipCover_angle"]
        res = pick_edge(panel, click, angle, tol)
        if not isinstance(res, tuple):
            print(u"Skipped: %s" % res)
            continue
        steps.start()
        edge = res[3]
        label = u"%s%s" % (CODE, cm(w))
        style = label_style(doc, STICKY)
        rect, centre, d = part(edge, out, w, plus, gap)
        x, y = readable(d, normal)
        te = TextEntity.Create(label, Plane(centre, x, y), style, False, 0, 0)
        te.TextHorizontalAlignment = TextHorizontalAlignment.Center
        te.TextVerticalAlignment = TextVerticalAlignment.Middle
        add_part(doc, [rect], te, [rect], attrs)  # next to the panel + its copy Up up (linked by PartLink), groups

        # label on the panel: inside, three quarters along the edge; the zip's number pulls it beside itself
        p, tan = point_at(edge, edge.GetLength() * 0.75)
        inn = -out(tan)
        x, y = readable(tan, normal)
        mark = TextEntity.Create(label, Plane(p + inn * style.TextHeight * 0.5, x, y), style, False, 0, 0)
        mark.TextHorizontalAlignment = TextHorizontalAlignment.Center
        mark.TextVerticalAlignment = TextVerticalAlignment.Bottom if y * inn > 0 else TextVerticalAlignment.Top
        a = attrs.Duplicate()
        m = mid_point(edge)
        a.SetUserString(BORD_EDGE, u"%r,%r,%r" % (m.X, m.Y, m.Z))
        a.SetUserString(BORD_LINE, str(oid))
        rs.AddObjectsToGroup([doc.Objects.AddText(mark, a)], rs.AddGroup())
        near = lambda q, z: bordino_near(z, q, m, oid, tol)
        zid = zip_text(lambda q, z: near(q, z) is not None, near)  # the zip of this side, also on a zip line inside
        if zid:
            labels_after(doc, zid, m, tol, steps)  # Z<n> R<w> B<w>
        doc.Views.Redraw()
        print(u"%s  l=%s" % (label, cm(edge.GetLength() + plus)))  # length only in the command history
        made += 1
    print(u"Bordino: %d → Parts::Bordino" % made)


if __name__ == "__main__":
    main()
