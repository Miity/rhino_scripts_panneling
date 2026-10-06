# -*- coding: utf-8 -*-
"""Check of OffsetRigid.shift in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_offset_rigid.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_offset_rigid.txt"), "w")
try:
    from Rhino.Geometry import Arc, ArcCurve, Plane, Point3d, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "curves"))
    import OffsetRigid as M

    Z = Vector3d.ZAxis
    # upper half-arc R=50 centred at (0,0): apex (0,50), the normal there — the Y axis
    arc = ArcCurve(Arc(Plane.WorldXY, 50.0, 3.141592653589793))
    ok, t = arc.ClosestPoint(Point3d(0, 50, 0))
    up = M.shift(arc, t, Z, Point3d(3, 80, 0), 20.0)      # click outside → +Y
    down = M.shift(arc, t, Z, Point3d(-3, 10, 0), 20.0)   # click inside → −Y
    assert (up - Vector3d(0, 20, 0)).Length < 1e-9, up
    assert (down - Vector3d(0, -20, 0)).Length < 1e-9, down
    # copy of the same shape: radius unchanged
    c = arc.DuplicateCurve(); c.Translate(up)
    ok, a = c.TryGetArc()
    assert ok and abs(a.Radius - 50.0) < 1e-9, a.Radius
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
