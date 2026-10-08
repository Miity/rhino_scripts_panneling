# -*- coding: utf-8 -*-
"""Merge two curves into one panel by their outer line; what ends up inside becomes open curves.
Select two or more curves in one plane: a closed panel and an open curve that together enclose an area
(e.g. a panel and its ZipCover / Rinforzo outline), or two panels that overlap, or open curves forming a loop.
The outer line of everything they enclose together becomes ONE closed curve; it replaces the panel (the first closed
curve; none closed — the first picked), so layer / groups / UserText / label stay. The other curves are deleted
and their groups merge into the panel's group.
Pieces that are NOT on the outer line (e.g. the old panel edge now inside) are cut off from the old curve and stay as
open curves: one per source curve, the source's layer and groups, UserText Part (panel number) removed. Drawing
is made of the original segments (lines stay lines, arcs stay arcs) — nothing is refitted.
Needs: the curves must touch or cross (ends within the document tolerance) so that they enclose an area.
Undo — Rhino's own (one step)."""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, Plane
from Rhino.Geometry.Intersect import Intersection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("JoinCorner", None)
from JoinCorner import merge_groups  # members of the dropped object's groups go into the kept object's group

KEY = "Part"  # UserText key of the panel number (Panels.py) — stays on the panel only


def plane_of(curves, tol):
    """Plane containing all curves (a straight line alone has no plane) or None."""
    pts = [p for c in curves for p in (c.PointAtStart, c.PointAtNormalizedLength(0.5), c.PointAtEnd)]
    plane = next((p for ok, p in (c.TryGetPlane(tol) for c in curves) if ok), None)
    if plane is None:
        result, plane = Plane.FitPlaneToPoints(pts)
        if result != Rhino.Geometry.PlaneFitResult.Success:
            return None
    return plane if all(abs(plane.DistanceTo(p)) <= tol for p in pts) else None


def break_params(src, border, tol):
    """Parameters on src where it meets the border curve (points and ends of overlaps)."""
    ts = []
    for ev in Intersection.CurveCurve(src, border, tol, tol) or []:
        ts.append(ev.ParameterA)
        if ev.IsOverlap:
            ts += [ev.OverlapA.T0, ev.OverlapA.T1]
    return sorted(set(ts))


def pieces(src, border, tol):
    """src cut where it meets the border: [(piece, on_border)]. On border = the piece's inner points lie on it."""
    ts = break_params(src, border, tol)
    if src.IsClosed and ts:  # seam at a break, so every piece runs between two breaks
        src = src.DuplicateCurve()
        src.ChangeClosedCurveSeam(ts[0])
        ts = break_params(src, border, tol)
    d = src.Domain
    ts = [d.T0] + [t for t in ts if d.T0 + 1e-9 < t < d.T1 - 1e-9] + [d.T1]
    parts = [src.Trim(a, b) for a, b in zip(ts, ts[1:])]
    out = []
    for p in parts:
        if p is None or p.GetLength() <= tol:
            continue
        samples = [p.PointAtNormalizedLength(k / 4.0) for k in (1, 2, 3)]
        on = all(border.PointAt(border.ClosestPoint(s)[1]).DistanceTo(s) <= tol for s in samples)
        out.append((p, on))
    return out


def merge(curves, tol):
    """curves — [source curve]; the first one is the panel. Returns (outline, [(source index, [open pieces])]) or an
    error string."""
    plane = plane_of(curves, tol)
    if plane is None:
        return u"the curves are not in one plane"
    regions = Curve.CreateBooleanRegions(curves, plane, True, tol)  # combined: one region = everything they enclose
    if regions is None or regions.RegionCount == 0:
        return u"the curves do not enclose an area together (ends do not touch?)"
    border = [c for i in range(regions.RegionCount) for c in regions.RegionCurves(i)]
    if len(border) != 1:
        return u"the curves enclose separate areas (%d): they must form one panel" % len(border)
    border = border[0]
    on, inner = [], []
    for k, c in enumerate(curves):
        rest, mine = [], 0
        for p, is_on in pieces(c, border, tol):
            (on if is_on else rest).append(p)
            mine += is_on
        if not mine:
            return u"curve %d is not part of the outer line (it does not meet the others, or lies entirely inside)" % (k + 1)
        inner.append((k, rest))
    joined = Curve.JoinCurves(on, tol * 2)
    if len(joined) != 1 or not joined[0].IsClosed:
        return u"the outer line did not join into one closed curve (%d pieces)" % len(joined)
    outline = joined[0]
    ok, pl = outline.TryGetPolyline()  # a clean polyline if everything is straight (for PreparePanelCut)
    if ok:
        pl.ReduceSegments(tol)  # also drops the vertices left where the pieces were joined
        outline = Rhino.Geometry.PolylineCurve(pl)
    return outline, [(k, Curve.JoinCurves(rest, tol * 2)) for k, rest in inner if rest]


HELP = u"""Select the closed panel and the curve(s) to merge into it (Enter — done).
Result: one closed panel by the outer line; the old panel edge inside stays as an open curve."""  # printed at start


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select the panel and the curve(s) to merge (2 or more curves)", rs.filter.curve,
                        preselect=True)
    if not ids or len(ids) < 2:
        print(u"Select at least two curves")
        return
    tol = doc.ModelAbsoluteTolerance
    ids = sorted(ids, key=lambda i: not rs.IsCurveClosed(i))  # a closed curve first (stable: the picked order otherwise)
    curves = [rs.coercecurve(i) for i in ids]
    res = merge(curves, tol)
    if not isinstance(res, tuple):
        print(u"Merge Outline: not done — %s" % res)
        return
    outline, rest = res
    keep = ids[0]
    undo = doc.BeginUndoRecord(u"Merge Outline")
    try:
        new = []
        for k, parts in rest:  # open leftovers: source layer / groups, panel number removed
            attrs = doc.Objects.FindId(ids[k]).Attributes.Duplicate()
            attrs.DeleteUserString(KEY)
            new += [doc.Objects.AddCurve(p, attrs) for p in parts]
        for i in ids[1:]:
            merge_groups(keep, i)
            doc.Objects.Delete(i, True)
        doc.Objects.Replace(keep, outline)
    finally:
        doc.EndUndoRecord(undo)
    rs.UnselectAllObjects()
    rs.SelectObjects([keep] + [n for n in new if n])
    doc.Views.Redraw()
    print(u"Merge Outline: %d curves → one panel; open curves left inside: %d" % (len(ids), len(new)))


if __name__ == "__main__":
    main()
