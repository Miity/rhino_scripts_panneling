# -*- coding: utf-8 -*-
"""Check of StripsFromCurves.strips in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_strips_from_curves.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_strips_from_curves.txt"), "w")
try:
    from Rhino.Geometry import LineCurve, Point3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    import StripsFromCurves as M

    L = lambda a, b: LineCurve(Point3d(*a), Point3d(*b))
    # two lines with a common point are NOT merged: each curve is its own strip
    r = M.strips([L((0, 0, 0), (100, 0, 0)), L((100, 0, 0), (100, 50, 0)), L((500, 0, 0), (530, 0, 0))])
    lens = sorted(round(x[0], 6) for x in r)
    assert lens == [30, 50, 100], lens
    assert abs(r[0][1].X - 50) < 1e-6  # TextDot at the middle of the curve
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
