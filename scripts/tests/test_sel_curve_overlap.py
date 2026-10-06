# -*- coding: utf-8 -*-
"""Check of sel_curve_overlap.shorter_overlaps in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_sel_curve_overlap.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_sel_curve_overlap.txt"), "w")
try:
    from Rhino.Geometry import LineCurve, Point3d, Polyline, PolylineCurve
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "cut"))
    import sel_curve_overlap as M

    def pl(*pts):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in pts]))

    crvs = [
        LineCurve(Point3d(0, 0, 0), Point3d(1000, 0, 0)),     # 0 long line
        pl((0, 0), (300, 0.002), (1000, 0)),                  # 1 the same, vertex moved by 0.002 (as in p1.3dm)
        LineCurve(Point3d(200, 0, 0), Point3d(400, 0, 0)),    # 2 shorter under the long one
        LineCurve(Point3d(0, 0, 0), Point3d(1000, 0, 0)),     # 3 exact duplicate of 0
        LineCurve(Point3d(0, 1, 0), Point3d(1000, 1, 0)),     # 4 parallel at 1 mm — separate
        LineCurve(Point3d(500, -50, 0), Point3d(500, 50, 0)), # 5 crossing — separate
        pl((0, 100), (50, 100.08), (100, 100)),               # 6 and 7: two approximations of one curve, 0.08 mm
        pl((0, 100), (25, 100.03), (75, 100.03), (100, 100)),
    ]
    hits = M.shorter_overlaps(crvs, 0.001, M.OVERLAP_TOL_MM, M.MIN_OVERLAP_MM)
    # from {0,1,3} one remains (the longest, 1), from {6,7} — one; 4 and 5 are not touched
    assert 4 not in hits and 5 not in hits, hits
    assert 2 in hits, hits
    assert len(hits & {0, 1, 3}) == 2, hits
    assert len(hits & {6, 7}) == 1, hits
    out.write("OK %s\n" % sorted(hits))
except Exception:
    out.write(traceback.format_exc())
out.close()
