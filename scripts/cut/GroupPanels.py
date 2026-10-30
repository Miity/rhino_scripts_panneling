# -*- coding: utf-8 -*-
"""Group every closed curve on layer CUT (a panel) together with everything lying inside it.

Select the panels and their contents (window); nested closed CUT curves count as contents
of the outer panel (holes), not as panels. One group per panel; existing groups, layers and
selection of the objects are kept (an object can belong to several groups).
Objects not inside any panel are left alone.
"""
import rhinoscriptsyntax as rs
import Rhino
import scriptcontext as sc

HELP = "GroupPanels: select panels (closed curves on CUT) with their contents, Enter. No options."


def on_cut(oid):
    return rs.ObjectLayer(oid).split("::")[-1].upper() == "CUT"


def probe(oid):
    """A point standing for the object: curve midpoint, point location, else bbox centre."""
    if rs.IsCurve(oid):
        c = rs.coercecurve(oid)
        return c.PointAtNormalizedLength(0.5)
    if rs.IsPoint(oid):
        return rs.coerce3dpoint(oid)
    box = rs.BoundingBox(oid)
    return (box[0] + box[6]) * 0.5 if box else None


def inside(panel, pt, tol):
    ok, plane = panel.TryGetPlane(tol)
    if not ok:
        return False
    res = panel.Contains(pt, plane, tol)
    return res in (Rhino.Geometry.PointContainment.Inside, Rhino.Geometry.PointContainment.Coincident)


def main():
    print(HELP)
    ids = rs.GetObjects("Select panels with their contents", preselect=True)
    if not ids:
        return
    tol = sc.doc.ModelAbsoluteTolerance
    closed = [i for i in ids if rs.IsCurve(i) and rs.IsCurveClosed(i) and on_cut(i)]
    curves = dict((i, rs.coercecurve(i)) for i in closed)
    # outer panels: closed CUT curves not inside another one
    panels = [i for i in closed
              if not any(j != i and inside(curves[j], curves[i].PointAtNormalizedLength(0.5), tol) for j in closed)]
    if not panels:
        print("No closed curves on layer CUT in the selection.")
        return
    members = dict((p, [p]) for p in panels)
    for oid in ids:
        if oid in members:
            continue
        pt = probe(oid)
        if pt is None:
            continue
        for p in panels:
            if inside(curves[p], pt, tol):
                members[p].append(oid)
                break
    sc.doc.Views.RedrawEnabled = False
    made = 0
    for p, objs in members.items():
        if len(objs) > 1:
            g = rs.AddGroup()
            rs.AddObjectsToGroup(objs, g)
            made += 1
    sc.doc.Views.RedrawEnabled = True
    print("Panels: %d, groups made: %d (panels with nothing inside are skipped)." % (len(panels), made))


if __name__ == "__main__":
    main()
