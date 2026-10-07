# -*- coding: utf-8 -*-
"""Zip cover / track cover: a flap that covers the zip on a panel edge.
Select a panel (closed curve: polyline, lines, arcs — any segments) and click near an edge
(several in a row, Enter — done). The edge runs corner to corner (corner — tangent break larger than Angle;
small breaks of a curved edge do not count). The part is a closed curve: copy of the edge + offset by W
outward from the panel, ends along the extension of the neighbouring edges. If a neighbour leaves sharper than 30°
from the edge (the extension would go very far) — the end is perpendicular, with a warning.
Part + label "ZC W" in a group, layer Parts::ZipCover. The panel is not changed: before cutting
PreparePanelCut joins it with the part (for that the edge must be a polyline / lines).
Option Layout (toggle, default Yes): Yes — as in Reinf (ReinfCircle.add_part): only markup in place (flap lines
not lying on the panel edge, + label), the full part — 10000 up along CPlane Y, for Layout.
"""
import math
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import (Curve, CurveEnd, CurveExtensionStyle, CurveOffsetCornerStyle, CurveOrientation,
                            LineCurve, PolylineCurve, Vector3d)
from Rhino.Geometry.Intersect import Intersection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Seam import label_frame, label_style, pick_style  # label in the middle of the strip; style — option Style

STICKY = "ZipCover"
LAYER = "Parts::ZipCover"
MIN_SIN = 0.5  # sin 30°: sharper — perpendicular end
GAP_MM = 1.0  # gap between the ends of an "almost closed" panel (DXF) that we close ourselves


def pick_edge(panel, click, angle, tol):
    """(segments, index of the first edge segment, index of the segment after the edge, edge) or an error string.
    Edge — corner to corner near click; corner — tangent break larger than angle."""
    if not panel.IsClosed:
        gap = GAP_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
        panel = panel.DuplicateCurve()
        if not panel.MakeClosed(gap):
            return u"panel is not closed (gap between ends larger than %g mm)" % GAP_MM
    segs = [c for c in panel.DuplicateSegments() if c.GetLength() > tol] or [panel.DuplicateCurve()]
    n = len(segs)
    corners = set(i for i in range(n) if Vector3d.VectorAngle(segs[i - 1].TangentAtEnd, segs[i].TangentAtStart)
                  > math.radians(angle))  # corner i — start of segment i
    if len(corners) < 2:
        return u"panel has fewer than two corners larger than %g°" % angle
    i = min(range(n), key=lambda k: segs[k].PointAt(segs[k].ClosestPoint(click)[1]).DistanceTo(click))
    s, e = i, (i + 1) % n
    while s not in corners:
        s = (s - 1) % n
    while e not in corners:
        e = (e + 1) % n
    edge = Curve.JoinCurves([segs[(s + k) % n] for k in range((e - s) % n or n)], tol)[0]
    return segs, s, e, edge


def along_panel(loop, corner, ext, back, tol):
    """(point, panel piece) from the corner along the panel to the first intersection with ext: back — backwards
    (neighbour before the edge, the piece runs to the corner), otherwise forward (piece from the corner). (None, None) — no intersection."""
    c = loop.DuplicateCurve()
    c.ChangeClosedCurveSeam(c.ClosestPoint(corner)[1])  # corner on the seam: the piece does not cross the seam
    x = [ev.ParameterA for ev in Intersection.CurveCurve(c, ext, tol, tol) or []
         if ev.PointA.DistanceTo(corner) > tol]
    if not x:
        return None, None
    t = max(x) if back else min(x)
    piece = c.Trim(t, c.Domain.T1) if back else c.Trim(c.Domain.T0, t)
    return (c.PointAt(t), piece) if piece else (None, None)


def flap(panel, click, w, angle, normal, tol, inward=False):
    """(part curve, edge, offset, number of perpendicular ends) or an error string.
    inward — part inside the panel (ReinfBord): ends along the neighbouring edges themselves, not their extension."""
    res = pick_edge(panel, click, angle, tol)
    if not isinstance(res, tuple):
        return res
    segs, s, e, edge = res
    n = len(segs)

    cw = panel.ClosedCurveOrientation(normal) == CurveOrientation.Clockwise
    side = -1 if inward else 1
    def outward(t):  # towards the part (outside the panel, or inside with inward) for the direction at t
        return (Vector3d.CrossProduct(normal, t) if cw else Vector3d.CrossProduct(t, normal)) * side

    t0, tm = edge.TangentAtStart, edge.Domain.Mid
    offs = edge.Offset(edge.PointAt(tm) + outward(edge.TangentAt(tm)) * w, normal, w, tol, CurveOffsetCornerStyle.Sharp)
    offs = Curve.JoinCurves(offs, tol) if offs else None
    if not offs:
        return u"edge offset failed"
    off = max(offs, key=lambda c: c.GetLength())
    if off.PointAtStart.DistanceTo(edge.PointAtStart) > off.PointAtEnd.DistanceTo(edge.PointAtStart):
        off.Reverse()
    big = 10 * w + edge.GetLength()
    ext = off.Extend(CurveEnd.Both, big, CurveExtensionStyle.Line)  # offset extended with straight lines
    if ext is None:
        return u"could not extend the offset"

    loop = Curve.JoinCurves(segs, tol)[0] if inward else None  # closed panel: ends follow it
    ends, sides, square = [], [], 0
    for back, corner, d, t, own in ((True, edge.PointAtStart, segs[(s - 1) % n].TangentAtEnd * side, t0, off.PointAtStart),
                                    (False, edge.PointAtEnd, -segs[e].TangentAtStart * side, edge.TangentAtEnd, off.PointAtEnd)):
        k = d * outward(t)  # sin of the angle between the neighbour's extension and the edge (on the part side)
        p = piece = None
        if k >= MIN_SIN and inward:  # along the neighbouring edge itself (it may bend), up to the offset line
            p, piece = along_panel(loop, corner, ext, back, tol)
        elif k >= MIN_SIN:
            x = Intersection.CurveCurve(LineCurve(corner, corner + d * (w / k + big)), ext, tol, tol)
            p = min((ev.PointA for ev in x), key=corner.DistanceTo) if x and x.Count else None
        if p is None:
            p, piece, square = own, None, square + 1
        ends.append(p)
        sides.append(piece or (LineCurve(p, corner) if back else LineCurve(corner, p)))
    ta, tb = ext.ClosestPoint(ends[0])[1], ext.ClosestPoint(ends[1])[1]
    if ta >= tb - tol:
        return u"edge too short for a flap W=%g (neighbour extensions intersect)" % w
    top = ext.Trim(ta, tb)
    top.Reverse()
    joined = Curve.JoinCurves([edge, sides[1], top, sides[0]], tol)
    if len(joined) != 1 or not joined[0].IsClosed:
        return u"part did not close"
    out = joined[0]
    ok, pl = out.TryGetPolyline()  # for PreparePanelCut — a clean polyline if everything is straight
    if ok:
        pl.DeleteShortSegments(tol)
        out = PolylineCurve(pl)
    return out, edge, off, square


def ask(gp):
    """Click near an edge with options W / Angle / Layout / Style. A point or None (Enter / Esc)."""
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 25.0), 0.001, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    gp.AddOptionDouble("W", w)
    lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", True), "No", "Yes")
    gp.AddOptionDouble("Angle", a)
    gp.AddOptionToggle("Layout", lay)
    i_style = gp.AddOption("Style")
    while True:
        r = gp.Get()
        sc.sticky[STICKY + "_layout"] = lay.CurrentValue
        sc.sticky[STICKY] = w.CurrentValue
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_style:
                pick_style(sc.doc, STICKY)
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options:
  W — flap width: offset from the edge outward from the panel
  Angle — a break larger than this angle = panel corner (the edge is taken corner to corner)
  Layout — Yes: only markup on the panel, full part 10000 up; No: full part in place
  Style — label text style (default PAT 14 mm)"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    sys.modules.pop("ReinfCircle", None)  # here, not at the top: Rhino caches modules per session
    from ReinfCircle import add_part, off_panel  # Layout: markup in place + part above
    doc = sc.doc
    oid = rs.GetObject(u"Select a panel (closed curve)", rs.filter.curve, preselect=True)
    if not oid:
        return
    panel = rs.coercecurve(oid)
    tol = doc.ModelAbsoluteTolerance
    ok, plane = panel.TryGetPlane(tol)
    normal = plane.ZAxis if ok else rs.ViewCPlane().ZAxis
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("ZipCover", parent="Parts")
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(LAYER, -1)
    made = 0
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near the edge for the flap (Enter — done)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        w, angle = sc.sticky[STICKY], sc.sticky[STICKY + "_angle"]
        res = flap(panel, click, w, angle, normal, tol)
        if not isinstance(res, tuple):
            print(u"Skipped: %s" % res)
            continue
        crv, edge, off, square = res
        te = Rhino.Geometry.TextEntity.Create(u"ZC %g" % w, label_frame(edge, off, normal),
                                              label_style(doc, STICKY), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        add_part(doc, [crv], te, off_panel(crv, [panel], tol), attrs, sc.sticky[STICKY + "_layout"])
        made += 1
        if square:
            print(u"Warning: %d end(s) with a neighbour sharper than 30° — end is perpendicular" % square)
        doc.Views.Redraw()
    print(u"Zip cover: %d parts → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
