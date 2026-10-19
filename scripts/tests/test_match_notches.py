# -*- coding: utf-8 -*-
"""Check of pattern/MatchNotches (edge lengths of a seam, nothing added to the document, Undo on edge B) in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_match_notches.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_match_notches.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Point3d, Polyline, PolylineCurve
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pattern"))
    for m in ("ZipCover", "click_undo", "Seams", "MatchNotches"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import MatchNotches as M

    tol = 0.001
    def rect(x0, w, h):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in ((x0, 0), (x0 + w, 0), (x0 + w, h), (x0, h), (x0, 0))]))

    old = sc.doc, rs.GetObjects, M.ask
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        ids = [doc.Objects.AddCurve(rect(0, 100, 60)), doc.Objects.AddCurve(rect(200, 105, 60))]
        sc.sticky["MatchNotches_angle"] = 30.0

        a, b = M.pick(doc, ids, Point3d(50, 61, 0), tol), M.pick(doc, ids, Point3d(250, 61, 0), tol)
        assert a[0] == ids[0] and b[0] == ids[1]
        assert (round(M.length(a), 6), round(M.length(b), 6)) == (100, 105), (M.length(a), M.length(b))
        assert round(M.length(M.pick(doc, ids, Point3d(-1, 30, 0), tol)), 6) == 60  # left side of A

        # main: one seam, then edge A + Undo on B, then Enter — nothing is added
        n = doc.Objects.Count
        clicks = [Point3d(50, 61, 0), Point3d(250, 61, 0), Point3d(1, 30, 0), M.UNDO, None]
        rs.GetObjects = lambda *a, **k: ids
        M.ask = lambda prompt, undo: clicks.pop(0)
        M.main()
        assert not clicks and doc.Objects.Count == n, (clicks, doc.Objects.Count)
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, M.ask = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
