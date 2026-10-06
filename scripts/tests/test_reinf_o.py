# -*- coding: utf-8 -*-
"""Check of ReinfO.o_shape in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_reinf_o.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_reinf_o.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ReinfO"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import ReinfO as M

    Z, tol, pi = Vector3d.ZAxis, 0.001, 3.14159265
    # panel 500×300, centre at the top-right corner (500,300), click (450,250), Plus 0 → quarter circle R=√5000
    panel = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(500, 0, 0), Point3d(500, 300, 0),
                                    Point3d(0, 300, 0), Point3d(0, 0, 0)]))
    c, r = M.o_shape([panel], Point3d(500, 300, 0), Point3d(450, 250, 0), 0, Z, tol)
    assert c is not None and c.IsClosed and abs(r - 5000 ** 0.5) < 1e-6
    assert abs(AreaMassProperties.Compute(c).Area - pi * r * r / 4) < 1e-1
    # click on the panel edge itself (400,300) + Plus 50 → R=150, quarter circle inside, not outside
    c, r = M.o_shape([panel], Point3d(500, 300, 0), Point3d(400, 300, 0), 50, Z, tol)
    assert abs(r - 150) < 1e-6 and abs(AreaMassProperties.Compute(c).Area - pi * 150 * 150 / 4) < 1e-1
    bb = c.GetBoundingBox(True)
    assert bb.Max.Y < 300 + 1e-3 and bb.Max.X < 500 + 1e-3, bb
    # SA 10: cut — circle R150 trimmed by panel + 10 → sides 10 outside, the arc stays at R150
    cut, seams, r = M.reinf([panel], Point3d(500, 300, 0), Point3d(400, 300, 0), 50, 10, Z, tol)
    ob = cut.GetBoundingBox(True)
    assert cut.IsClosed and abs(r - 150) < 1e-6
    assert abs(ob.Max.Y - 310) < 1e-3 and abs(ob.Max.X - 510) < 1e-3, ob
    assert abs(ob.Min.X - (500 - 150)) < 1e-3 and abs(ob.Min.Y - (300 - 150)) < 1e-3, ob  # arc not moved
    # seam — two panel edges inside the circle (150 + 150), without the arc
    assert abs(sum(c.GetLength() for c in seams) - 300) < 1e-3, [c.GetLength() for c in seams]
    # label at the middle of arc R150 (angle 225°), tangent reads left to right, moved 5 towards the centre
    pl, va = M.arc_label(cut, Point3d(500, 300, 0), 150, Z, 5, tol)
    assert abs(pl.Origin.DistanceTo(Point3d(500, 300, 0)) - 145) < 1e-3, pl.Origin
    assert pl.XAxis.X > 0 and abs(pl.XAxis * (pl.Origin - Point3d(500, 300, 0))) < 1e-3, pl.XAxis
    # no boundary — full circle R = 100 + 50
    c, r = M.o_shape([], Point3d(0, 0, 0), Point3d(0, -100, 0), 50, Z, tol)
    assert c.IsClosed and abs(AreaMassProperties.Compute(c).Area - pi * 150 * 150) < 1e-1
    assert M.o_shape([panel], Point3d(0, 0, 0), Point3d(0, 0, 0), 50, Z, tol)[0] is None
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
