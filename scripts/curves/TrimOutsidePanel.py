# -*- coding: utf-8 -*-
"""Trims 2D curves by a closed panel contour: everything outside the panel is deleted.
Pieces lying exactly on the panel contour are kept."""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

Outside = Rhino.Geometry.PointContainment.Outside


def trim_to_panel(crv, panel, plane, tol):
    """Returns a list of pieces inside the panel (or None if the whole curve is inside)."""
    params = []
    for e in Rhino.Geometry.Intersect.Intersection.CurveCurve(crv, panel, tol, tol) or []:
        params.append(e.ParameterA)
        if e.IsOverlap:
            params.append(e.OverlapA.T1)
    pieces = crv.Split(params) if params else None
    if not pieces:
        pieces = [crv]
    inside = [p for p in pieces
              if panel.Contains(p.PointAtNormalizedLength(0.5), plane, tol) != Outside]
    if len(inside) == len(pieces) and len(pieces) == 1:
        return None
    return inside


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
        inside = trim_to_panel(rs.coercecurve(oid), panel, plane, tol)
        if inside is None:
            continue
        attrs = sc.doc.Objects.FindId(oid).Attributes  # layer, colour, linetype
        for p in inside:
            sc.doc.Objects.AddCurve(p, attrs)
        sc.doc.Objects.Delete(oid, True)
        changed += 1
    rs.EnableRedraw(True)
    print("Curves trimmed / deleted: {}".format(changed))


if __name__ == "__main__":
    main()
