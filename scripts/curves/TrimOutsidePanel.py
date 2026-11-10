# -*- coding: utf-8 -*-
"""Trims 2D curves by a closed panel contour: everything outside the panel is deleted.
Pieces lying exactly on the panel contour are kept.

Also a module: ``pieces`` / ``replace`` are used by cut/PreparePanelCut.py (lines trimmed at the cut contour)."""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

IN, ON, OUT = "in", "on", "out"


def pieces(curve, contours, plane, tol):
    """The curve cut where it meets the closed contours: a list of (piece, IN / ON / OUT).

    ON — the piece runs along a contour, IN — inside one of them, OUT — outside all.
    A curve that meets no contour comes back whole, as one piece.
    """
    params = []
    for contour in contours:
        for event in Rhino.Geometry.Intersect.Intersection.CurveCurve(curve, contour, tol, tol) or []:
            params.append(event.ParameterA)
            if event.IsOverlap:
                params.append(event.OverlapA[1])
    lo, hi = curve.Domain.T0, curve.Domain.T1
    params = sorted(set(round(t, 9) for t in params if lo + 1e-9 < t < hi - 1e-9))
    if params and curve.IsClosed:
        params.insert(0, lo)  # a closed curve cut at one parameter stays one piece
    parts = list(curve.Split(params) or []) if params else []
    out = []
    for piece in parts or [curve]:
        mid = piece.PointAtNormalizedLength(0.5)
        if any(c.PointAt(c.ClosestPoint(mid)[1]).DistanceTo(mid) <= tol for c in contours):
            where = ON
        elif any(c.Contains(mid, plane, tol) == Rhino.Geometry.PointContainment.Inside for c in contours):
            where = IN
        else:
            where = OUT
        out.append((piece, where))
    return out


def replace(object_id, keep, tol):
    """Replace the object by the kept pieces, touching ones joined (same layer, groups, attributes). Returns the new ids."""
    attributes = rs.coercerhinoobject(object_id).Attributes.Duplicate()
    new_ids = [sc.doc.Objects.AddCurve(c, attributes) for c in Rhino.Geometry.Curve.JoinCurves(keep, tol)] if keep else []
    sc.doc.Objects.Delete(object_id, True)
    return new_ids


def main():
    ids = rs.GetObjects("Select curves to trim", rs.filter.curve, preselect=True)
    if not ids:
        return
    panel_id = rs.GetObject("Select a panel (closed contour)", rs.filter.curve)
    if not panel_id:
        return
    panel = rs.coercecurve(panel_id)
    ok, plane = panel.TryGetPlane()
    if not (panel.IsClosed and ok):
        print("The panel must be a closed planar curve")
        return
    tol = sc.doc.ModelAbsoluteTolerance

    rs.EnableRedraw(False)
    changed = 0
    for oid in ids:
        if oid == panel_id:
            continue
        found = pieces(rs.coercecurve(oid), [panel], plane, tol)
        keep = [piece for piece, where in found if where != OUT]
        if len(keep) == len(found):
            continue
        replace(oid, keep, tol)
        changed += 1
    rs.EnableRedraw(True)
    print("Curves trimmed / deleted: {0}".format(changed))


if __name__ == "__main__":
    main()
