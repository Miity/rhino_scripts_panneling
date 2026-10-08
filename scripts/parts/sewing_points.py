# -*- coding: utf-8 -*-
"""Battute (sewing marks): points from the centre of an edge, left and right with an equal step, + a centre tick.
Select panels (closed curves) and / or curves, then click near an edge (several in a row, Enter — done).
The selected object nearest the click is used, only its edge corner to corner near the click (corner — a break
larger than Angle, as in ZipCover; a curve without corners — the whole curve). Points: the edge centre (half its
length), then centre ± k·Step while on the edge. Tick (length Tick) at the centre, perpendicular to the edge:
on a panel — from the edge into the panel; on a curve — symmetric across it.
Points + tick of one edge — one group, layer Parts::SewingMarks. Panels and curves are not changed.
"""
import math
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, CurveOrientation, LineCurve, Point, Vector3d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("ZipCover", None)  # Rhino keeps modules from the first run for the session
from ZipCover import close_panel, layer_attrs, pick_edge  # panel edge corner to corner, Parts::<name> layer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

STICKY = "SewingMarks"
NAME = "SewingMarks"


def sewing_lengths(total, step):
    """Lengths along the curve: centre, then centre ± k*step, while within the curve."""
    mid = total / 2.0
    out = [mid]
    k = 1
    while k * step <= mid + 1e-9:
        out += [mid - k * step, mid + k * step]
        k += 1
    return sorted(out)


def curve_edge(crv, click, angle, tol):
    """Open curve: its piece corner to corner nearest the click (no corners — the whole curve)."""
    groups = []
    for s in crv.DuplicateSegments() or [crv.DuplicateCurve()]:
        if s.GetLength() <= tol:
            continue
        if groups and Vector3d.VectorAngle(groups[-1][-1].TangentAtEnd, s.TangentAtStart) <= math.radians(angle):
            groups[-1].append(s)
        else:
            groups.append([s])
    pieces = [Curve.JoinCurves(g, tol)[0] for g in groups] or [crv]
    return min(pieces, key=lambda c: c.PointAt(c.ClosestPoint(click)[1]).DistanceTo(click))


def marks(obj, click, step, tick, angle, normal, tol):
    """(points, tick line or None) on the edge of obj near the click, or an error string.
    Closed obj = panel: tick from the edge centre into the panel; open = curve: tick symmetric across it."""
    panel = close_panel(obj)  # closed, or "almost closed" from DXF (gap up to ZipCover.GAP_MM) → panel
    if panel is not None:
        res = pick_edge(panel, click, angle, tol)
        if not isinstance(res, tuple):
            return res
        edge = res[3]
    else:
        edge = curve_edge(obj, click, angle, tol)
    length = edge.GetLength()
    pts = []
    for s in sewing_lengths(length, step):
        ok, t = edge.LengthParameter(s)
        if ok:
            pts.append(Point(edge.PointAt(t)))
    line = None
    if tick > 0:
        ok, t = edge.LengthParameter(length / 2.0)
        c, u = edge.PointAt(t), edge.TangentAt(t)
        side = Vector3d.CrossProduct(normal, u)  # left of the edge direction
        side.Unitize()
        if panel is not None:  # into the panel: left of the direction for a counter-clockwise panel
            if panel.ClosedCurveOrientation(normal) == CurveOrientation.Clockwise:
                side = -side
            line = LineCurve(c, c + side * tick)
        else:
            line = LineCurve(c - side * (tick / 2.0), c + side * (tick / 2.0))
    return pts, line


def ask(gp):
    """Click near an edge / curve with options Step / Tick / Angle / Undo. A point, UNDO or None (Enter / Esc)."""
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    step = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_step", 200.0 * mm), 0.001, 1e9)
    tick = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_tick", 10.0 * mm), 0.0, 1e9)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    gp.AddOptionDouble("Step", step)
    gp.AddOptionDouble("Tick", tick)
    gp.AddOptionDouble("Angle", a)
    i_undo = gp.AddOption("Undo")
    while True:
        r = gp.Get()
        sc.sticky[STICKY + "_step"] = step.CurrentValue
        sc.sticky[STICKY + "_tick"] = tick.CurrentValue
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_undo:
                return UNDO
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options:
  Step — distance between the points, from the edge centre both ways (default 200 mm)
  Tick — centre tick length: on a panel into the panel, on a curve across it; 0 — no tick (default 10 mm)
  Angle — a break larger than this angle = corner (the edge is taken corner to corner)
  Undo — remove the marks of the last click (again — the click before it)"""  # printed at start


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select panels and / or curves for sewing marks", rs.filter.curve, preselect=True)
    if not ids:
        return
    tol = doc.ModelAbsoluteTolerance
    attrs = layer_attrs(doc, NAME)
    made = 0
    steps = Steps(doc)
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near the edge or curve for sewing marks (Enter — done)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        if click == UNDO:
            if steps.undo():
                made -= 1
            continue
        steps.start()
        crvs = [rs.coercecurve(i) for i in ids]
        obj = min((c for c in crvs if c), key=lambda c: c.PointAt(c.ClosestPoint(click)[1]).DistanceTo(click))
        view = doc.Views.ActiveView
        up = view.ActiveViewport.ConstructionPlane().ZAxis if view else Vector3d.ZAxis  # headless: WorldXY
        ok, plane = obj.TryGetPlane(tol)
        normal = plane.ZAxis if ok else up
        if normal * up < 0:
            normal = -normal  # one up direction for every curve
        res = marks(obj, click, sc.sticky[STICKY + "_step"], sc.sticky[STICKY + "_tick"],
                    sc.sticky[STICKY + "_angle"], normal, tol)
        if not isinstance(res, tuple):
            print(u"Skipped: %s" % res)
            continue
        pts, line = res
        new = [doc.Objects.Add(p, attrs) for p in pts] + ([doc.Objects.AddCurve(line, attrs)] if line else [])
        rs.AddObjectsToGroup(new, rs.AddGroup())
        steps.created(new)
        made += 1
        doc.Views.Redraw()
    print(u"Sewing marks: %d edges → Parts::%s" % (made, NAME))


if __name__ == "__main__":
    main()
