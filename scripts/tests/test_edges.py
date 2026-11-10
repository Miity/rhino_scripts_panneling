# -*- coding: utf-8 -*-
"""Check in Rhino 8 (needs RhinoCommon) that every script finds the same edges corner to corner — they all go through
curves/SplitCrvByAngle.py segments / breaks / runs: on a panel with DXF noise (a 0.03 mm stub at a corner, a 0.03 mm
sideways step in the middle of an edge) ZipCover.pick_edge, Seams.edges, ZipStops.curve_edge and JoinCorner.tail
take the whole edge, not the half up to the step. Run through Rhino MCP (run_python) or rhinocode;
the result is written to test_edges.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_edges.txt"), "w")
try:
    import Rhino
    import scriptcontext as sc
    from Rhino.Geometry import Point3d, Polyline, PolylineCurve, Vector3d
    for f in ("parts", "pattern", "curves"):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), f))
    for m in ("SplitCrvByAngle", "ZipCover", "ZipStops", "JoinCorner", "Seams"):
        sys.modules.pop(m, None)
    import SplitCrvByAngle as S
    import JoinCorner
    import Seams
    import ZipCover
    import ZipStops

    old = sc.doc
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
    sc.doc = doc
    try:
        tol = doc.ModelAbsoluteTolerance

        def pl(pts):
            return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in pts]))

        pts = [(0, 0), (500, 0), (500, 0.03), (1000, 0.03), (1000.02, 0.05), (1000.02, 600), (0, 600), (0, 0)]
        panel, click = pl(pts), Point3d(250, -5, 0)
        segs = S.segments(panel, tol)
        assert len(segs) == 5 and S.breaks(segs, True, 30.0) == [0, 2, 3, 4], (len(segs), S.breaks(segs, True, 30.0))
        assert [len(r) for r in S.runs(segs, True, [0, 2, 3, 4])] == [2, 1, 1, 1]
        assert [len(r) for r in S.runs(segs, False, [2])] == [2, 3] and S.runs(segs, True, []) == [segs]
        edge = ZipCover.pick_edge(panel, click, 30.0, tol)[3]
        seam = min(Seams.edges(Seams.loop(panel, Vector3d.ZAxis), 30.0, tol),
                   key=lambda e: e.PointAt(e.ClosestPoint(click)[1]).DistanceTo(click))
        piece = ZipStops.curve_edge(pl(pts[:6]), click, 30.0, tol)
        open_segs = JoinCorner.segments(pl(pts[:6]), tol)
        out.write("bottom edge: ZipCover %.2f, Seams %.2f, ZipStops (open curve) %.2f, JoinCorner tail %d of %d segments\n"
                  % (edge.GetLength(), seam.GetLength(), piece.GetLength(), JoinCorner.tail(open_segs, False, 30.0), len(open_segs)))
        assert abs(edge.GetLength() - 1000) < 0.01 and abs(seam.GetLength() - edge.GetLength()) < 1e-6
        assert abs(piece.GetLength() - 1000) < 0.01
        assert JoinCorner.tail(open_segs, False, 30.0) == 2 and JoinCorner.tail(open_segs, True, 30.0) == 1
    finally:
        sc.doc = old
        doc.Dispose()
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
