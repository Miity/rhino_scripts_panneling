# -*- coding: utf-8 -*-
"""Check of JoinCorner.join in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_join_corner.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_join_corner.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    import ZipCover
    import JoinCorner as M
    import importlib; importlib.reload(M)

    Z, tol = Vector3d.ZAxis, 0.001
    def poly(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p + (p[0],)]))
    def area(c):
        return AreaMassProperties.Compute(c).Area

    # rectangle 100×60: flap W=10 on top, seam W=20 on the left → L with a filled 20×10 corner
    pan = poly((0, 0), (100, 0), (100, 60), (0, 60))
    top = ZipCover.flap(pan, Point3d(50, 61, 0), 10, 30, Z, tol)[0]
    left = ZipCover.flap(pan, Point3d(-1, 30, 0), 20, 30, Z, tol)[0]
    j, = M.join(top, left, Point3d(-10, 65, 0), tol)
    assert j.IsClosed and abs(area(j) - (1000 + 1200 + 200)) < 1e-3, area(j)
    ok, pl = j.TryGetPolyline()
    assert ok and pl.Count - 1 == 6, pl.Count  # L: 6 vertices, no extra ones on straight lines
    assert M.join(left, top, Point3d(-10, 65, 0), tol)[0].IsClosed  # order does not matter
    # click on the part itself (not between the ends and not between the edges) — error
    assert isinstance(M.join(top, left, Point3d(50, 65, 0), tol), str)

    # slanted corner (trapezoid) with different W: area = sum + notch, outer corner — intersection of offsets
    pan = poly((0, 0), (100, 0), (120, 60), (-20, 60))
    top = ZipCover.flap(pan, Point3d(50, 61, 0), 10, 30, Z, tol)[0]
    right = ZipCover.flap(pan, Point3d(111, 30, 0), 15, 30, Z, tol)[0]
    j, = M.join(top, right, Point3d(128, 64, 0), tol)
    assert j.IsClosed and area(j) > area(top) + area(right), (area(j), area(top) + area(right))
    # without the notch between parts: both parts are pieces of the result
    assert abs(j.GetBoundingBox(True).Max.Y - 70) < 1e-6
    ok, pl = j.TryGetPolyline()
    assert ok and pl.Count - 1 == 6, pl.Count

    # as p1.3dm: curved side as a polyline of small segments, W 30 on top and 20 on the side.
    # The pair "edge + edge" gives a tiny fill here — without the click it is easy to take the wrong one.
    import math
    side = [(-5 * math.sin(math.pi * k / 20), 60 - 3 * k) for k in range(21)]
    pan = poly(*([(100, 60), (100, 0)] + side[::-1][:-1] + [(0, 60)]))
    top = ZipCover.flap(pan, Point3d(50, 61, 0), 30, 30, Z, tol)[0]
    left = ZipCover.flap(pan, Point3d(-6, 30, 0), 20, 30, Z, tol)[0]
    j, = M.join(top, left, Point3d(-5, 75, 0), tol)
    # minimum fill would pick the pair of edges here — so check that the notch is taken
    
    gap = area(j) - area(top) - area(left)
    assert j.IsClosed and 300 < gap < 900, gap  # notch ≈ 20 × 30
    assert abs(j.GetBoundingBox(True).Max.Y - 90) < 1e-6

    # parts without a common corner
    bottom = ZipCover.flap(poly((0, 0), (100, 0), (100, 60), (0, 60)), Point3d(50, -1, 0), 10, 30, Z, tol)[0]
    assert isinstance(M.join(bottom, top, Point3d(0, 0, 0), tol), str)
    # frame: 4 parts around a rectangle, different W; 3 corners → one part, the 4th corner — with itself
    pan = poly((0, 0), (100, 0), (100, 60), (0, 60))
    fl = [ZipCover.flap(pan, c, w, 30, Z, tol)[0] for c, w in
          ((Point3d(50, 61, 0), 10), (Point3d(-1, 30, 0), 20), (Point3d(50, -1, 0), 5), (Point3d(101, 30, 0), 15))]
    a, = M.join(fl[0], fl[1], Point3d(-10, 65, 0), tol)
    a, = M.join(a, fl[2], Point3d(-10, -3, 0), tol)
    a, = M.join(a, fl[3], Point3d(110, -3, 0), tol)
    assert isinstance(M.join(a, a, Point3d(110, 65, 0), tol), str)  # no pair with itself
    outer, = M.join(a, None, Point3d(110, 65, 0), tol)  # frame closed → only the outer contour
    assert outer.IsClosed and abs(area(outer) - 135 * 75) < 1e-3, area(outer)
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
