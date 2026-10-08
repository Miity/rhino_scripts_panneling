# -*- coding: utf-8 -*-
""""O" reinforcement at the end of a full-width pocket.
Like ReinfD, but without the rectangle: the pocket reaches the panel edge, so the reinforcement is a circle
centred at the top corner of the pocket, trimmed by the panel.
Select a boundary (panel or corner lines; Enter — no trimming, full circle). Then in a loop:
first point — top corner of the pocket (circle centre), second — a click on a line (e.g. the other side of the pocket):
R = distance to the click + Plus (option, default 5 cm, remembered). The circle is shown live. Enter — done.
With a panel (closed curve) only the part of the circle inside the panel touching the centre is kept;
with open lines — the part between them on the side of the second click.
Option SA — seam allowance (default 1 cm, panel only): sides along the panel edge extend outward by SA
(the arc stays at R — no seam on it); seam line — panel edges inside the circle, in the group.
SA=0 — no allowance. Plus and SA — in the second click prompt.
The part lies in place,
layer Parts::Reinforcements, label "RO<n>  <r>" (r in cm) along the arc (inside) in a group; RO numbering continues between runs.
Option Layout (default Yes, in the second click prompt): on the panel — markup (arc only, without panel edges),
full part — 10000 up (ReinfCircle.add_part); No — full part in place.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import AreaMassProperties, ArcCurve, Circle, Curve, CurveOffsetCornerStyle, Plane, PointContainment, Vector3d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("ReinfCircle", None)  # Rhino keeps modules from the first run for the session
from ReinfCircle import LAYER, UP_KEY, add_part, up_option, layer, next_number, off_panel, piece, cm, label_style, pick_style  # layer, numbering, trimming, style

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

STICKY = "ReinfO"
PREFIX = "RO"  # Reinforcement O


def o_shape(curves, center, edge, plus, normal, tol):
    """Circle (centre center, R = distance to edge + plus) trimmed by curves. (curve or None, R)."""
    plane = Plane(center, normal)
    d = plane.ClosestPoint(edge).DistanceTo(center)
    r = d + plus
    if d <= tol or r <= tol:
        return None, r
    circle = ArcCurve(Circle(plane, r))
    closed = [c for c in curves if c.IsClosed]
    if closed:  # panel: only inside it, the piece containing the centre (or closest to it)
        best = None
        for c in closed:
            for p in Curve.CreateBooleanIntersection(circle, c, tol) or []:
                inside = p.Contains(center, plane, tol) != PointContainment.Outside
                gap = 0.0 if inside else center.DistanceTo(p.PointAt(p.ClosestPoint(center)[1]))
                if best is None or gap < best[0]:
                    best = (gap, p)
        return (best[1] if best else None), r
    if curves:
        return piece(curves, center, edge, r, normal, tol), r
    return circle, r


def outward(crv, d, normal, tol):
    """Offset of closed crv by d outward (of the two sides, the larger one). None — failed."""
    plane = Plane(crv.PointAtStart, normal)
    best = None
    for s in (d, -d):
        offs = crv.Offset(plane, s, tol, CurveOffsetCornerStyle.Sharp)
        offs = Curve.JoinCurves(offs, tol) if offs else None
        if offs and offs[0].IsClosed:
            a = AreaMassProperties.Compute(offs[0]).Area
            if best is None or a > best[0]:
                best = (a, offs[0])
    return best[1] if best else None


def grow(curves, sa, normal, tol):
    """Closed panels grown outward by sa (for the cut line). [] — no panel or sa = 0."""
    if sa <= 0:
        return []
    return [g for g in (outward(c, sa, normal, tol) for c in curves if c.IsClosed) if g]


def on_circle(s, center, r, tol):
    return all(abs(center.DistanceTo(s.PointAtNormalizedLength(t)) - r) <= tol for t in (0.25, 0.5, 0.75))


def seam_lines(crv, center, r, tol):
    """Panel edges on contour crv — everything except the circle arc (centre center, radius r)."""
    keep = [s for s in crv.DuplicateSegments() or [crv] if not on_circle(s, center, r, tol)]
    return list(Curve.JoinCurves(keep, tol)) if keep else []


def arc_label(crv, center, r, normal, gap, tol):
    """(text plane, alignment): arc midpoint, along the tangent, moved by gap towards the centre. None — no arc."""
    arcs = [s for s in crv.DuplicateSegments() or [crv] if on_circle(s, center, r, tol)]
    if not arcs:
        return None
    a = max(arcs, key=lambda s: s.GetLength())
    ok, t = a.LengthParameter(a.GetLength() / 2.0)
    m = a.PointAt(t if ok else a.Domain.Mid)
    u = a.TangentAt(t if ok else a.Domain.Mid)
    if u.X < -1e-9 or (abs(u.X) < 1e-9 and u.Y < 0):  # text reads left to right
        u = -u
    inward = center - m
    inward.Unitize()
    plane = Plane(m + inward * gap, u, Vector3d.CrossProduct(normal, u))
    va = Rhino.DocObjects.TextVerticalAlignment
    return plane, (va.Bottom if plane.YAxis * inward > 0 else va.Top)


def reinf(curves, center, edge, plus, sa, normal, tol, grown=None):
    """(cut, [seam lines], R): cut = circle trimmed by panel + sa; seam — panel edges inside the circle. cut None — failed."""
    crv, r = o_shape(curves, center, edge, plus, normal, tol)
    if grown is None:
        grown = grow(curves, sa, normal, tol)
    if crv is None or not grown:
        return crv, [], r
    cut = o_shape(grown, center, edge, plus, normal, tol)[0]
    return cut, (seam_lines(crv, center, r, tol) if cut else []), r


def get_edge(curves, center, normal, tol):
    """Second point with a live O and options Plus, SA. (point, plus, sa) or None."""
    unit = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    plus = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 50.0 * unit), 0.0, 1e6)
    sa = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_sa", 10.0 * unit), 0.0, 1e6)

    grown = {}  # SA → grown panels: the panel offset is not recomputed on every mouse move

    def draw(sender, e):
        s = sa.CurrentValue
        if s not in grown:
            grown[s] = grow(curves, s, normal, tol)
        cut, seams, _ = reinf(curves, center, e.CurrentPoint, plus.CurrentValue, s, normal, tol, grown[s])
        color = sc.doc.Layers.CurrentLayer.Color
        if cut:
            e.Display.DrawCurve(cut, color, 2)
        for c in seams:
            e.Display.DrawCurve(c, color, 1)
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Click on a line: R = distance to it + Plus")
    gp.SetBasePoint(center, True)
    gp.DrawLineFromPoint(center, True)
    gp.AddOptionDouble("Plus", plus)
    gp.AddOptionDouble("SA", sa)
    lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", True), "No", "Yes")
    gp.AddOptionToggle("Layout", lay)
    up = up_option(gp)
    i_style = gp.AddOption("Style")
    gp.DynamicDraw += draw
    try:
        while True:
            res = gp.Get()
            sc.sticky[STICKY] = plus.CurrentValue
            sc.sticky[STICKY + "_sa"] = sa.CurrentValue
            sc.sticky[STICKY + "_layout"] = lay.CurrentValue
            sc.sticky[UP_KEY] = up.CurrentValue
            if res == Rhino.Input.GetResult.Option and gp.OptionIndex() == i_style:
                pick_style(sc.doc, STICKY)
            if res != Rhino.Input.GetResult.Option:
                return (gp.Point(), plus.CurrentValue, sa.CurrentValue) if res == Rhino.Input.GetResult.Point else None
    finally:
        gp.DynamicDraw -= draw


def get_center():
    """Top corner of the pocket with option Undo. A point, UNDO or None (Enter / Esc)."""
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Top corner of the pocket — centre of the O (Enter — done)")
    gp.AcceptNothing(True)
    i_undo = gp.AddOption("Undo")
    res = gp.Get()
    if res == Rhino.Input.GetResult.Option and gp.OptionIndex() == i_undo:
        return UNDO
    return gp.Point() if res == Rhino.Input.GetResult.Point else None


HELP = u"""Options:
  Plus — how far the O arc extends past the line you clicked
  SA — seam allowance along the panel edges (no seam on the arc; 0 — none)
  Layout — Yes: only markup on the panel, full part `Up` up; No: full part in place
  Up — how far up (along CPlane Y) the full part goes with Layout=Yes; shared by all part scripts
  Style — label text style (default PAT 14 mm)
  Undo (at the centre click) — take back the last O (again — the one before it); its number is reused"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    ids = rs.GetObjects(u"Select a boundary: panel or corner lines (Enter — no trimming)", rs.filter.curve, preselect=True)
    curves = [rs.coercecurve(i) for i in ids or []]
    normal = rs.ViewCPlane().ZAxis
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer(), -1)
    n = next_number(LAYER, PREFIX)
    made = 0
    steps = Steps(doc)
    while True:
        center = get_center()
        if center is None:
            break
        if center == UNDO:
            if steps.undo():
                n, made = n - 1, made - 1
            continue
        steps.start()
        got = get_edge(curves, center, normal, tol)
        if got is None:
            break
        crv, seams, r = reinf(curves, center, got[0], got[1], got[2], normal, tol)
        if crv is None:
            print(u"Could not cut the circle (points coincide? curves not in the CPlane?)")
            continue
        if got[2] > 0 and not seams:  # ponytail: SA only with a closed panel; with corner lines — no allowance
            print(u"SA skipped: a closed panel is needed")
        label = u"%s%d  %s" % (PREFIX, n, cm(r))
        style = label_style(doc, STICKY)
        tp, valign = arc_label(crv, center, r, normal, style.TextHeight * 0.5, tol) or \
            (Plane(rs.ViewCPlane()), Rhino.DocObjects.TextVerticalAlignment.Middle)
        if valign == Rhino.DocObjects.TextVerticalAlignment.Middle:
            amp = AreaMassProperties.Compute(crv)
            tp.Origin = amp.Centroid if amp else center
        te = Rhino.Geometry.TextEntity.Create(label, tp, style, False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = valign
        fin = o_shape(curves, center, got[0], got[1], normal, tol)[0] or crv  # without SA: what is visible on the panel
        add_part(doc, [crv] + seams, te, off_panel(fin, curves, tol), attrs, sc.sticky[STICKY + "_layout"])
        doc.Views.Redraw()
        print(label)
        n += 1
        made += 1
    print(u"O reinforcements: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
