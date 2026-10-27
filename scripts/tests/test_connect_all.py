# -*- coding: utf-8 -*-
"""Check of ConnectAll.connect in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_connect_all.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_connect_all.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Polyline, PolylineCurve
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "curves"))
    sys.modules.pop("ConnectAll", None)
    import ConnectAll as M

    tol = 0.001
    def pl(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))

    # square of four sides, gaps 0.4 (overlap at one corner, gap at others), shuffled order and directions
    sides = [pl((0.3, 0), (10, 0.2)), pl((10.2, 0.4), (10, 10.3)), pl((10.2, 10), (-0.1, 10)), pl((0, 10.4), (0.2, 0.3))]
    sides[3].Reverse()
    items, free = M.connect([sides[2], sides[0], sides[3], sides[1]], 2.0, 30.0, tol)
    assert len(items) == 1 and not free and items[0][0].IsClosed, (len(items), free)
    assert sorted(items[0][1]) == [0, 1, 2, 3]
    assert abs(AreaMassProperties.Compute(items[0][0]).Area - 100) < 2, AreaMassProperties.Compute(items[0][0]).Area

    # the 8 polylines of p1.3dm (mm, gaps 0.03 - 1.1) → one closed curve
    P = [[(14263.843, 8973.955), (15756.873, 8974.164)], [(13164.73, 8450.329), (13343.162, 8433.75)],
         [(16677.35, 8397.23), (16835.281, 8407.503)], [(16205.385, 11364.637), (13843.313, 11378.053)],
         [(13344.019, 8434.477), (14263.038, 8973.421)], [(13843.262, 11377.996), (13164.814, 8450.692)],
         [(15757.656, 8973.616), (16676.548, 8397.781)], [(16835.257, 8407.618), (16205.41, 11364.628)]]
    items, free = M.connect([pl(*p) for p in P], 2.0, 30.0, tol)
    assert len(items) == 1 and not free and items[0][0].IsClosed, (len(items), free)

    # DXF stubs: sides ending with 0.05 mm hooks / overlaps at the corners — no micro zigzag in the result
    def shortest(c):
        return min(s.GetLength() for s in c.DuplicateSegments())
    stubs = [pl((0.3, 0), (10, 0), (10.03, 0.04)), pl((10.0, 0.5), (10, 10), (9.96, 10.03)),
             pl((10.02, 10.0), (0, 10), (-0.03, 9.96), (0.01, 9.95)), pl((0, 9.7), (0, 0.05), (0.04, 0.02))]
    items, free = M.connect(stubs, 2.0, 30.0, tol)
    assert len(items) == 1 and not free and items[0][0].IsClosed, (len(items), free)
    assert shortest(items[0][0]) >= 0.1, [round(s.GetLength(), 4) for s in items[0][0].DuplicateSegments()]

    # a partner farther than Gap is left alone
    items, free = M.connect([pl((0, 0), (10, 0)), pl((15, 0), (20, 0))], 2.0, 30.0, tol)
    assert len(items) == 2 and len(free) == 4
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
