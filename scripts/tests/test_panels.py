# -*- coding: utf-8 -*-
"""Check of Panels.classify in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_panels.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_panels.txt"), "w")
try:
    from Rhino.Geometry import Interval, Plane, Rectangle3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    import Panels as M
    try:
        from importlib import reload
    except ImportError:
        pass
    M = reload(M)
    reload(M.D)  # Rhino keeps the module in memory between runs

    R = lambda x0, y0, x1, y1: Rectangle3d(Plane.WorldXY, Interval(x0, x1), Interval(y0, y1)).ToNurbsCurve()
    curves = [
        R(300, 0, 400, 80),     # 0: bottom row, right
        R(0, 0, 100, 90),       # 1: bottom row, left (top slightly above 0 — same row)
        R(200, 200, 300, 300),  # 2: top row, right
        R(0, 150, 150, 300),    # 3: top row, left
        R(20, 170, 60, 210),    # 4: hole in 3
        R(30, 180, 40, 190),    # 5: hole in hole 4 → also belongs to 3
    ]
    r = M.classify(curves, Plane.WorldXY, 0.001)
    assert r == [(3, [4, 5]), (2, []), (1, []), (0, [])], r

    # text goes inside the trapezoid near the click (DotToPanelText logic via Panels.D) and is removed
    import scriptcontext as sc
    from Rhino.Geometry import Point3d, PolylineCurve, PointContainment
    doc = sc.doc
    trap = PolylineCurve([Point3d(0, 0, 0), Point3d(400, 0, 0), Point3d(300, 300, 0), Point3d(100, 300, 0), Point3d(0, 0, 0)])
    ds = M.D.pts.ensure_styles(doc)[20]
    tid = M.D.place_text(doc, "P7", trap, Point3d(290, 290, 0), ds, doc.CreateDefaultAttributes(), doc.ModelAbsoluteTolerance)
    assert tid, "text was not placed"
    bb = doc.Objects.FindId(tid).Geometry.GetBoundingBox(True)
    doc.Objects.Delete(tid, True)
    for c in bb.GetCorners()[:4]:
        assert trap.Contains(c, Plane.WorldXY, 0.001) == PointContainment.Inside, c
    assert bb.Max.X > 200 and bb.Max.Y > 200, bb  # top-right corner, near the click
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
