# -*- coding: utf-8 -*-
"""Check of ReinfCircle.corners / piece in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_reinf_circle.txt next to it."""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_reinf_circle.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, LineCurve, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    import ReinfCircle as M

    Z, tol, r = Vector3d.ZAxis, 0.001, 40.0
    quarter = math.pi * r * r / 4

    def area(c):
        return AreaMassProperties.Compute(c).Area

    # square panel 100: click inside near corner (0,0) → quarter circle
    sq = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(100, 0, 0), Point3d(100, 100, 0),
                                 Point3d(0, 100, 0), Point3d(0, 0, 0)]))
    click = Point3d(10, 8, 0)
    c0 = min(M.corners([sq], tol), key=lambda p: p.DistanceTo(click))
    assert c0.DistanceTo(Point3d(0, 0, 0)) < 1e-6, c0
    pc = M.piece([sq], c0, click, r, Z, tol)
    assert pc and pc.IsClosed and abs(area(pc) - quarter) < 0.01, area(pc) if pc else None
    # click outside the panel → rest of the circle (3/4)
    pc = M.piece([sq], c0, Point3d(-5, -5, 0), r, Z, tol)
    assert pc and abs(area(pc) - 3 * quarter) < 0.01, area(pc) if pc else None

    # two short lines (20 < R) meeting at (0,0): both sides of the corner
    a = LineCurve(Point3d(0, 0, 0), Point3d(20, 0, 0))
    b = LineCurve(Point3d(0, 0, 0), Point3d(0, 20, 0))
    c0 = min(M.corners([a, b], tol), key=lambda p: p.DistanceTo(Point3d(3, 3, 0)))
    assert c0.DistanceTo(Point3d(0, 0, 0)) < 1e-6, c0
    pc = M.piece([a, b], c0, Point3d(3, 3, 0), r, Z, tol)
    assert pc and abs(area(pc) - quarter) < 0.01, area(pc) if pc else None
    pc = M.piece([a, b], c0, Point3d(-3, 3, 0), r, Z, tol)  # opposite side — also a quarter (lines extended)
    assert pc and abs(area(pc) - quarter) < 0.01, area(pc) if pc else None

    # panel with a 60° corner: sector = 1/6 of the circle
    tri = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(100, 0, 0),
                                  Point3d(50, 50 * math.sqrt(3), 0), Point3d(0, 0, 0)]))
    pc = M.piece([tri], Point3d(0, 0, 0), Point3d(10, 3, 0), r, Z, tol)
    assert pc and abs(area(pc) - math.pi * r * r / 6) < 0.01, area(pc) if pc else None
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
