# -*- coding: utf-8 -*-
"""Zip cover (copri zip / canalina): a strip of width W outside a panel edge.
Select a panel (closed curve: polyline, lines, arcs — any segments) and click near an edge
(several in a row, Enter — done). The edge runs corner to corner (corner — tangent break larger than Angle;
small breaks of a curved edge do not count). The part is a closed curve: copy of the edge + offset by W
outward from the panel, ends along the extension of the neighbouring edges. If a neighbour leaves sharper than 30°
from the edge (the extension would go very far) — the end is perpendicular, with a warning.
Labels are Italian codes, numbers in cm (PatternTextStyles.cm).
Label "Off<w>" (offset), layer Parts::ZipCover. Notches (battute) — a separate script, pattern/Notches.py.
Option EditPanel=No (default): only markup is added, in place: the strip lines not lying on the panel edge
+ label, one group. The panel is not changed: before cutting PreparePanelCut joins
it with the markup (for that the edge must be a polyline / lines).
EditPanel=Yes: the panel contour itself gets the strip (one closed curve; layer, groups, UserText kept),
the old edge stays as a line (zip line) + label, one group.
"""
import math
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import (Curve, CurveEnd, CurveExtensionStyle, CurveOffsetCornerStyle, CurveOrientation,
                            LineCurve, Plane, PolylineCurve, Vector3d)
from Rhino.Geometry.Intersect import Intersection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
sys.modules.pop("PatternTextStyles", None)  # Rhino keeps modules from the first run for the session
from PatternTextStyles import cm, label_style, pick_style  # label number in cm; style: option Style, default PAT 14 mm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

STICKY = "ZipCover"
CODE, NAME = "Off", "ZipCover"  # label code, sublayer of Parts
MIN_SIN = 0.5  # sin 30°: sharper — perpendicular end
GAP_MM = 1.0  # gap between the ends of an "almost closed" panel (DXF) that we close ourselves


def close_panel(panel):
    """Closed copy of an "almost closed" panel (DXF gap up to GAP_MM), the panel itself if closed, None — gap too big."""
    if panel.IsClosed:
        return panel
    gap = GAP_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    panel = panel.DuplicateCurve()
    return panel if panel.MakeClosed(gap) else None


def grow_panel(panel, edge, outer, tol):
    """Panel contour with the edge replaced by outer (part lines off the panel, from corner to corner):
    one closed curve (a clean polyline if all straight) or None."""
    c = close_panel(panel).DuplicateCurve()
    c.ChangeClosedCurveSeam(c.ClosestPoint(edge.PointAtEnd)[1])  # rest of the panel: edge end → around → edge start
    rest = c.Trim(c.Domain.T0, c.ClosestPoint(edge.PointAtStart)[1])
    joined = Curve.JoinCurves([rest] + list(outer), tol) if rest else []
    if len(joined) != 1 or not joined[0].IsClosed:
        return None
    ok, pl = joined[0].TryGetPolyline()
    if ok:
        pl.DeleteShortSegments(tol)
        return PolylineCurve(pl)
    return joined[0]


def pick_edge(panel, click, angle, tol):
    """(segments, index of the first edge segment, index of the segment after the edge, edge) or an error string.
    Edge — corner to corner near click; corner — tangent break larger than angle."""
    panel = close_panel(panel)
    if panel is None:
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


def flap(panel, click, w, angle, normal, tol, inward=False, plus=0.0):
    """(part curve, edge, offset, number of perpendicular ends) or an error string.
    inward — part inside the panel (Rinforzo): ends along the neighbouring edges themselves, not their extension.
    plus — the part is longer by plus (plus / 2 past each end, straight on): cut longer, trimmed after sewing."""
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
    if plus > 0:  # both lines longer by plus / 2 at each end, ends — straight lines between them
        e2 = edge.Extend(CurveEnd.Both, plus / 2.0, CurveExtensionStyle.Line)
        top = top.Extend(CurveEnd.Both, plus / 2.0, CurveExtensionStyle.Line)
        if e2 is None or top is None:
            return u"could not extend the part by Plus"
        sides = [LineCurve(top.PointAtEnd, e2.PointAtStart), LineCurve(e2.PointAtEnd, top.PointAtStart)]
    joined = Curve.JoinCurves([e2 if plus > 0 else edge, sides[1], top, sides[0]], tol)
    if len(joined) != 1 or not joined[0].IsClosed:
        return u"part did not close"
    out = joined[0]
    ok, pl = out.TryGetPolyline()  # for PreparePanelCut — a clean polyline if everything is straight
    if ok:
        pl.DeleteShortSegments(tol)
        out = PolylineCurve(pl)
    return out, edge, off, square


def label_frame(crv, offset, normal):
    """Point in the middle of the strip and direction along the edge (text reads left to right)."""
    ok, t = crv.LengthParameter(crv.GetLength() / 2.0)
    t = t if ok else crv.Domain.Mid
    m = crv.PointAt(t)
    q = offset.PointAt(offset.ClosestPoint(m)[1])
    u = crv.TangentAt(t)
    if u.X < -1e-9 or (abs(u.X) < 1e-9 and u.Y < 0):
        u = -u
    return Plane((m + q) / 2.0, u, Vector3d.CrossProduct(normal, u))


def layer_attrs(doc, name, parent="Parts"):
    """Attributes on layer <parent>::<name> (created if missing)."""
    if not rs.IsLayer(parent):
        rs.AddLayer(parent)
    if not rs.IsLayer(parent + "::" + name):
        rs.AddLayer(name, parent=parent)
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(parent + "::" + name, -1)
    return attrs


def add_markup(doc, geoms, te, attrs):
    """Markup in place: geometry + label te, one group. Returns the ids."""
    ids = [doc.Objects.Add(g, attrs) for g in geoms] + [doc.Objects.AddText(te, attrs)]
    rs.AddObjectsToGroup(ids, rs.AddGroup())
    return ids


def edit_panel(doc, oid, panel, edge, outer, tol):
    """EditPanel: replace the panel object with panel + part (layer, groups, UserText kept). New panel curve or None."""
    new = grow_panel(panel, edge, outer, tol)
    if new is None or not doc.Objects.Replace(oid, new):
        print(u"Stopped: could not join the part with the panel contour")
        return None
    return new


def ask(gp):
    """Click near an edge with options W / Angle / EditPanel / Style / Undo. A point, UNDO or None (Enter / Esc)."""
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 10.0), 0.001, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    i_undo = gp.AddOption("Undo")
    gp.AddOptionDouble("W", w)
    gp.AddOptionDouble("Angle", a)
    ed = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_edit", False), "No", "Yes")
    gp.AddOptionToggle("EditPanel", ed)
    i_style = gp.AddOption("Style")
    while True:
        r = gp.Get()
        sc.sticky[STICKY] = w.CurrentValue
        sc.sticky[STICKY + "_edit"] = ed.CurrentValue
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_undo:
                return UNDO
            if gp.OptionIndex() == i_style:
                pick_style(sc.doc, STICKY)
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options:
  W — strip width: offset from the edge outward from the panel
  Angle — a break larger than this angle = panel corner (the edge is taken corner to corner)
  EditPanel — Yes: the panel contour itself gets the strip, the old edge stays as a line; No: only strip lines
  Style — label text style (default PAT 14 mm)
  Undo — take back the last click (again — the click before it)"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    sys.modules.pop("ReinfCircle", None)  # here, not at the top: Rhino caches modules per session
    from ReinfCircle import off_panel  # markup: part lines not lying on the panel
    doc = sc.doc
    oid = rs.GetObject(u"Select a panel (closed curve)", rs.filter.curve, preselect=True)
    if not oid:
        return
    panel = rs.coercecurve(oid)
    tol = doc.ModelAbsoluteTolerance
    ok, plane = panel.TryGetPlane(tol)
    normal = plane.ZAxis if ok else rs.ViewCPlane().ZAxis
    made = 0
    steps = Steps(doc)
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near the edge (Enter — done)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        if click == UNDO:
            if steps.undo():
                made -= 1
                panel = rs.coercecurve(oid)  # EditPanel: the panel is back as it was
            continue
        steps.start()
        w, angle = sc.sticky[STICKY], sc.sticky[STICKY + "_angle"]
        res = flap(panel, click, w, angle, normal, tol)
        if not isinstance(res, tuple):
            print(u"Skipped: %s" % res)
            continue
        crv, edge, off, square = res
        te = Rhino.Geometry.TextEntity.Create(CODE + cm(w), label_frame(edge, off, normal),
                                              label_style(doc, STICKY), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        geoms = off_panel(crv, [panel], tol)
        if sc.sticky[STICKY + "_edit"]:
            steps.change(oid)
            new = edit_panel(doc, oid, panel, edge, geoms, tol)
            if new is None:
                continue
            panel = new
            geoms = [edge]  # old edge = zip line
        add_markup(doc, geoms, te, layer_attrs(doc, NAME))
        made += 1
        if square:
            print(u"Warning: %d end(s) with a neighbour sharper than 30° — end is perpendicular" % square)
        doc.Views.Redraw()
    print(u"Zip cover: %d strips → Parts::%s" % (made, NAME))


if __name__ == "__main__":
    main()
