# -*- coding: utf-8 -*-
"""Check of JoinCorner (join, main with group merge) in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_join_corner.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_join_corner.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Curve, LineCurve, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ZipCover", "JoinCorner"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import ZipCover
    from ReinfCircle import off_panel
    import JoinCorner as M

    Z, tol = Vector3d.ZAxis, 0.001
    def pl(*p, **k):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in (p + (p[0],) if k.get("closed") else p)]))

    # ZipCover markups at the top-left corner of a 100×60 panel: top W=10, left W=20 → notch at (0, 60)
    pan = pl((0, 0), (100, 0), (100, 60), (0, 60), closed=True)
    top, = off_panel(ZipCover.flap(pan, Point3d(50, 61, 0), 10, 30, Z, tol)[0], [pan], tol)
    left, = off_panel(ZipCover.flap(pan, Point3d(-1, 30, 0), 20, 30, Z, tol)[0], [pan], tol)
    ends = [(top, top.PointAtEnd.DistanceTo(Point3d(0, 60, 0)) < 1), (left, left.PointAtEnd.DistanceTo(Point3d(0, 60, 0)) < 1)]
    j = M.join(ends, Point3d(-5, 65, 0), 30, tol)
    assert isinstance(j, Curve) and not j.IsClosed, j
    assert abs(j.GetLength() - 220) < 1e-6, j.GetLength()  # 10 + 120 (top to x=-20) + 70 + 20
    assert {(round(p.X), round(p.Y)) for p in (j.PointAtStart, j.PointAtEnd)} == {(100, 60), (0, 0)}
    assert any(p.DistanceTo(Point3d(-20, 70, 0)) < 1e-6 for p in j.TryGetPolyline()[1])  # outer corner

    # frame: one open curve around a square, gap at the corner (0, 0) → closes
    fr = pl((0, 2), (0, 10), (10, 10), (10, 0), (2, 0))
    j = M.join([(fr, False), (fr, True)], Point3d(0.5, 0.5, 0), 30, tol)
    assert j.IsClosed and abs(AreaMassProperties.Compute(j).Area - 100) < 1e-6

    # four markups around a panel (all ending exactly on the panel corners): the 3rd corner closes the 4th too —
    # no zigzag through the panel corner left (it used to close there and the 4th corner could not be clicked)
    pan = pl((0, 0), (100, 0), (100, 60), (0, 60), closed=True)
    marks = [off_panel(ZipCover.flap(pan, c, w, 30, Z, tol)[0], [pan], tol)[0]
             for c, w in ((Point3d(50, 61, 0), 20), (Point3d(-1, 30, 0), 20), (Point3d(101, 30, 0), 20), (Point3d(50, -1, 0), 10))]
    def ends_at(c, p):
        return c.PointAtEnd.DistanceTo(p) < c.PointAtStart.DistanceTo(p)
    j = marks[0]
    for m, corner, click in ((marks[1], Point3d(0, 60, 0), Point3d(-5, 65, 0)), (marks[2], Point3d(100, 60, 0), Point3d(105, 65, 0)),
                             (marks[3], Point3d(100, 0, 0), Point3d(105, -5, 0))):
        j = M.join([(j, ends_at(j, corner)), (m, ends_at(m, corner))], click, 30, tol)
        assert isinstance(j, Curve), j
    assert j.IsClosed, "the last corner was not closed"
    assert abs(AreaMassProperties.Compute(j).Area - 140 * 90) < 1e-3, AreaMassProperties.Compute(j).Area  # x -20..120, y -10..80
    assert min(pan.PointAt(pan.ClosestPoint(p)[1]).DistanceTo(p) for p in j.TryGetPolyline()[1]) > 9.99  # off the panel

    # crossing lines → trimmed at the crossing, joined
    a, b = LineCurve(Point3d(0, 0, 0), Point3d(12, 0, 0)), LineCurve(Point3d(10, -2, 0), Point3d(10, 10, 0))
    j = M.join([(a, True), (b, False)], Point3d(11, -1, 0), 30, tol)
    assert abs(j.GetLength() - 20) < 1e-6, j.GetLength()

    # parallel lines → error string
    c = LineCurve(Point3d(0, 5, 0), Point3d(12, 5, 0))
    assert not isinstance(M.join([(a, True), (c, True)], Point3d(12, 2, 0), 30, tol), Curve)

    # main(): the second curve is deleted, its group (label) merges into the first's group
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    old_doc, old_get = sc.doc, rs.GetObjects
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        sc.doc = doc
        ia, ib = doc.Objects.AddCurve(top), doc.Objects.AddCurve(left)
        ta = doc.Objects.AddTextDot("ZC 10", Point3d(50, 65, 0))
        tb = doc.Objects.AddTextDot("SA 20", Point3d(-10, 30, 0))
        rs.AddObjectsToGroup([ia, ta], rs.AddGroup())
        rs.AddObjectsToGroup([ib, tb], rs.AddGroup())
        rs.GetObjects = lambda *x, **k: [ia, ib, ta, tb]
        clicks = [Point3d(-5, 65, 0), None]
        M.ask = lambda gp: clicks.pop(0)
        sc.sticky["JoinCorner_angle"] = 30.0
        M.main()
        assert doc.Objects.FindId(ib) is None and abs(doc.Objects.FindId(ia).Geometry.GetLength() - 220) < 1e-6
        g = rs.ObjectGroups(ia)[0]
        assert set(rs.ObjectsByGroup(g)) == {ia, ta, tb}, rs.ObjectsByGroup(g)
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects = old_doc, old_get
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
