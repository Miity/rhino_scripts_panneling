# -*- coding: utf-8 -*-
"""Check of ReducePoints.reduce in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_reduce_points.txt next to it."""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_reduce_points.txt"), "w")
try:
    from Rhino.Geometry import Point3d, Polyline, PolylineCurve
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "curves"))
    sys.modules.pop("ReducePoints", None)
    import ReducePoints as M

    def dev(a, b):
        """Largest distance from the vertices of a to curve b."""
        return max(b.PointAt(b.ClosestPoint(p)[1]).DistanceTo(p) for p in a.TryGetPolyline()[1])

    # closed panel: top with a vertex every unit (collinear), a half-circle cut-out (R 50) sampled every 0.5°, sharp corners
    poly = [Point3d(0, 0, 0), Point3d(0, 100, 0)] + [Point3d(i, 100, 0) for i in range(1, 200)] + [Point3d(200, 100, 0), Point3d(200, 50, 0)] \
        + [Point3d(150 + 50 * math.cos(math.radians(t * 0.5)), 50 + 50 * math.sin(math.radians(t * 0.5)) * -1, 0) for t in range(0, 181)] \
        + [Point3d(100, 50, 0), Point3d(100, 0, 0), Point3d(0, 0, 0)]
    crv = PolylineCurve(Polyline(poly))
    assert crv.IsClosed
    cs = [Point3d(0, 0, 0), Point3d(0, 100, 0), Point3d(200, 100, 0), Point3d(200, 50, 0), Point3d(100, 50, 0), Point3d(100, 0, 0)]

    new = M.reduce(crv, 0.1, 5.0, False)
    pl = list(new.TryGetPolyline()[1])
    assert new.IsClosed and len(pl) < 60, len(pl)
    for c in cs:  # every corner still a vertex, untouched
        assert min(c.DistanceTo(p) for p in pl) < 1e-9, c
    assert dev(crv, new) <= 0.1 + 1e-9 and dev(new, crv) <= 1e-6, (dev(crv, new), dev(new, crv))
    assert abs(new.GetLength() - crv.GetLength()) < 1.0

    sm = M.reduce(crv, 0.1, 5.0, True)
    assert sm is not None and sm.IsClosed and dev(crv, sm) <= 0.3, (dev(crv, sm) if sm else None)
    assert sm.SpanCount < 40, sm.SpanCount

    # open curve: ends stay
    op = PolylineCurve(Polyline([Point3d(i, 0.001 * (i % 2), 0) for i in range(50)]))
    r = M.reduce(op, 0.1, 5.0, False)
    assert not r.IsClosed and r.PointAtStart.DistanceTo(op.PointAtStart) < 1e-9 and r.PointAtEnd.DistanceTo(op.PointAtEnd) < 1e-9
    assert r.TryGetPolyline()[1].Count <= 3
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
