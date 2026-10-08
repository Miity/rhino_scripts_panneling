# -*- coding: utf-8 -*-
"""Check of sewing_points (Battute: marks on an edge corner to corner, centre tick) in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_sewing_points.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_sewing_points.txt"), "w")
try:
    from Rhino.Geometry import LineCurve, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ZipCover", "sewing_points"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import sewing_points as M

    Z, tol = Vector3d.ZAxis, 0.001
    def pl(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))
    assert M.sewing_lengths(100, 20) == [10, 30, 50, 70, 90]

    # closed panel 100×60, both orientations: top edge only (not the whole contour), tick from (50, 60) into the panel
    for pan in (pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)), pl((0, 0), (0, 60), (100, 60), (100, 0), (0, 0))):
        pts, tick = M.marks(pan, Point3d(50, 61, 0), 20, 10, 30, Z, tol)
        assert sorted(round(p.Location.X, 6) for p in pts) == [10, 30, 50, 70, 90]
        assert all(abs(p.Location.Y - 60) < 1e-6 for p in pts)
        ends = {(round(tick.PointAtStart.X, 6), round(tick.PointAtStart.Y, 6)), (round(tick.PointAtEnd.X, 6), round(tick.PointAtEnd.Y, 6))}
        assert ends == {(50, 60), (50, 50)}, ends

    # "almost closed" DXF panel (gap 0.1) is still a panel
    pts, tick = M.marks(pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0.1)), Point3d(101, 30, 0), 20, 10, 30, Z, tol)
    assert sorted(round(p.Location.Y, 6) for p in pts) == [10, 30, 50]  # right edge 60: centre 30 ± 20
    assert abs(tick.PointAtEnd.X - 90) < 1e-6 or abs(tick.PointAtStart.X - 90) < 1e-6  # into the panel (x < 100)

    # open L-curve: only the piece near the click; tick symmetric across it
    pts, tick = M.marks(pl((0, 0), (100, 0), (100, 50)), Point3d(50, 1, 0), 20, 10, 30, Z, tol)
    assert sorted(round(p.Location.X, 6) for p in pts) == [10, 30, 50, 70, 90]
    assert {round(tick.PointAtStart.Y, 6), round(tick.PointAtEnd.Y, 6)} == {-5, 5}

    # curve without corners — the whole curve; Tick 0 — no tick
    pts, tick = M.marks(LineCurve(Point3d(0, 0, 0), Point3d(40, 0, 0)), Point3d(5, 1, 0), 20, 0, 30, Z, tol)
    assert sorted(round(p.Location.X, 6) for p in pts) == [0, 20, 40] and tick is None
    # main(): panel + curve selected, click near the panel top → only marks of that edge, one group, Parts::SewingMarks
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    old_doc, old_get = sc.doc, rs.GetObjects
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        sc.doc = doc
        pid = doc.Objects.AddCurve(pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)))
        cid = doc.Objects.AddCurve(LineCurve(Point3d(0, 200, 0), Point3d(40, 200, 0)))
        rs.GetObjects = lambda *x, **k: [pid, cid]
        clicks = [Point3d(50, 61, 0), Point3d(20, 201, 0), "undo", None]  # 2nd click (the curve) undone
        M.ask = lambda gp: clicks.pop(0)
        sc.sticky.update({"SewingMarks_step": 20.0, "SewingMarks_tick": 10.0, "SewingMarks_angle": 30.0})
        M.main()
        new = [o for o in doc.Objects if o.Id not in (pid, cid)]
        assert len(new) == 6, len(new)  # 5 points + tick
        assert all(doc.Layers[o.Attributes.LayerIndex].FullPath == "Parts::SewingMarks" for o in new)
        assert len(set(tuple(o.Attributes.GetGroupList()) for o in new)) == 1
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects = old_doc, old_get
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
