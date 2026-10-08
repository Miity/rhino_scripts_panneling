# -*- coding: utf-8 -*-
"""Check of ReinfD.d_shape in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_reinf_d.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_reinf_d.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ReinfD"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import ReinfD as M

    Z, tol = Vector3d.ZAxis, 0.001
    # D centre (0,0), bottom (0,-100), R 50: rectangle 100×100 + half-circle R50 up → y from -100 to 50
    c = M.d_shape(Point3d(0, 0, 0), Point3d(0, -100, 0), 100, 50, Z, tol)
    assert c.IsClosed
    assert abs(AreaMassProperties.Compute(c).Area - (10000 + 3.14159265 * 2500 / 2)) < 1e-2
    bb = c.GetBoundingBox(True)
    assert abs(bb.Min.Y + 100) < 1e-6 and abs(bb.Max.Y - 50) < 1e-6 and abs(bb.Max.X - 50) < 1e-6, bb
    assert M.d_shape(Point3d(0, 0, 0), Point3d(0, 0, 0), 100, 50, Z, tol) is None
    # W 150, R 50: rectangle 150×100 + half-ellipse 75×50 → area 15000 + π·75·50/2, width exactly 150
    c = M.d_shape(Point3d(0, 0, 0), Point3d(0, -100, 0), 150, 50, Z, tol)
    assert c.IsClosed
    assert abs(AreaMassProperties.Compute(c).Area - (15000 + 3.14159265 * 75 * 50 / 2)) < 1e-1
    bb = c.GetBoundingBox(True)
    assert abs(bb.Max.Y - 50) < 1e-6 and abs(bb.Max.X - 75) < 1e-6 and abs(bb.Min.X + 75) < 1e-6, bb
    # D markup without bottom: two sides 100 + half-circle R50; add_part: full part 10000 up, markup in place
    import math
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    import ReinfCircle as RC
    c = M.d_shape(Point3d(0, 0, 0), Point3d(0, -100, 0), 100, 50, Z, tol)
    base = min(c.DuplicateSegments(), key=lambda g: g.PointAtNormalizedLength(0.5).DistanceTo(Point3d(0, -100, 0)))
    mk = RC.off_panel(c, [base], tol)
    assert len(mk) == 1 and not mk[0].IsClosed and abs(mk[0].GetLength() - (200 + math.pi * 50)) < 1e-3
    # RC: square panel, sector R100 at corner (0,0) → markup is only the arc π·100/2
    from Rhino.Geometry import Polyline, PolylineCurve, TextEntity
    sq = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(1000, 0, 0), Point3d(1000, 1000, 0),
                                 Point3d(0, 1000, 0), Point3d(0, 0, 0)]))
    sector = RC.piece([sq], Point3d(0, 0, 0), Point3d(10, 10, 0), 100, Z, tol)
    mk = RC.off_panel(sector, [sq], tol)
    assert len(mk) == 1 and abs(mk[0].GetLength() - math.pi * 50) < 1e-3, [m.GetLength() for m in mk]
    te = TextEntity.Create("RD99", rs.WorldXYPlane(), sc.doc.DimStyles.Current, False, 0, 0)
    view_cplane = rs.ViewCPlane
    rs.ViewCPlane = lambda *a: rs.WorldXYPlane()  # rhinocode: sc.doc is headless, no view to take the CPlane from
    try:
        full, markup = RC.add_part(sc.doc, [c], te, mk, sc.doc.CreateDefaultAttributes())
    finally:
        rs.ViewCPlane = view_cplane
    try:
        dy = sc.sticky.get(RC.UP_KEY, RC.UP)  # option Up, may be changed in this session
        assert len(full) == 2 and len(markup) == 2
        assert abs(rs.BoundingBox(full[0])[0].Y - (-100 + dy)) < 1e-6
        assert abs(rs.BoundingBox(markup[0])[0].Y) < 1e-6
        assert rs.ObjectGroups(full[0]) == rs.ObjectGroups(full[1]) != rs.ObjectGroups(markup[0])
    finally:
        rs.DeleteObjects(full + markup)
    rs.ViewCPlane = lambda *a: rs.WorldXYPlane()
    try:
        full, markup = RC.add_part(sc.doc, [c], te, mk, sc.doc.CreateDefaultAttributes(), False)  # Layout=No
    finally:
        rs.ViewCPlane = view_cplane
    try:
        assert markup == [] and abs(rs.BoundingBox(full[0])[0].Y + 100) < 1e-6
    finally:
        rs.DeleteObjects(full)
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
