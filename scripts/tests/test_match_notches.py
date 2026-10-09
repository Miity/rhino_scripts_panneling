# -*- coding: utf-8 -*-
"""Check of pattern/MatchNotches (notches of edge A onto edge B from the clicked corners, duplicates kept, past the end
skipped, B → A when A has none, Undo) in Rhino 8 (needs RhinoCommon):
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
    for m in ("ZipCover", "click_undo", "Seams", "Notches", "MatchNotches"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import Notches as N
    import MatchNotches as M

    tol = 0.001
    def rect(x0, w, h):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in ((x0, 0), (x0 + w, 0), (x0 + w, h), (x0, h), (x0, 0))]))

    old = sc.doc, rs.GetObjects, M.ask
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        pa = doc.Objects.AddCurve(rect(0, 100, 60))
        pb = doc.Objects.AddCurve(rect(200, 105, 60))
        pc = doc.Objects.AddCurve(rect(400, 60, 60))
        gb = doc.Groups.Add()
        doc.Groups.AddToGroup(gb, pb)
        ids = [pa, pb, pc]

        sc.sticky.update({"Notches_mode": 3, "Notches_every": 20.0, "Notches_angle": 30.0})
        assert N.place(doc, pa, Point3d(50, 61, 0), tol) == 5  # top of A: x = 10..90

        def xs(x0, x1):
            return sorted(round(o.Geometry.Location.X, 3) for o in doc.Objects
                          if o.Attributes.GetUserString(M.NOTCH) and x0 <= o.Geometry.Location.X <= x1)

        def pair(ca, cb):
            return M.match(doc, M.pick(doc, ids, ca, tol), M.pick(doc, ids, cb, tol), tol)

        # A from its left top corner onto B from its right top corner: mirrored along B, difference +5
        n, past, la, lb = pair(Point3d(1, 61, 0), Point3d(304, 61, 0))
        assert (n, past, round(la, 6), round(lb, 6)) == (5, 0, 100, 105), (n, past, la, lb)
        assert xs(200, 305) == [215, 235, 255, 275, 295], xs(200, 305)
        gs = [list(o.Attributes.GetGroupList() or []) for o in doc.Objects if 200 <= o.Geometry.GetBoundingBox(True).Min.X < 306
              and o.Attributes.GetUserString(M.NOTCH)]
        assert all(len(g) == 2 and gb in g for g in gs) and len(set(tuple(g) for g in gs)) == 1, gs
        lay = set(doc.Layers[o.Attributes.LayerIndex].FullPath for o in doc.Objects if o.Attributes.GetUserString(M.NOTCH))
        assert lay == {"Pattern::Notches"}, lay

        assert pair(Point3d(1, 61, 0), Point3d(304, 61, 0))[0] == 0  # again: those on B are kept, no duplicates
        # C has none: clicked first, still copied from A onto C; top of C is 60 long — 70, 90 past the end
        n, past, la, lb = pair(Point3d(401, 61, 0), Point3d(1, 61, 0))
        assert (n, past) == (3, 2) and round(la, 6) == 100 and round(lb, 6) == 60, (n, past, la, lb)
        assert xs(400, 460) == [410, 430, 450], xs(400, 460)

        # main: one seam (A bottom from the left ← no notches there: nothing), then A top onto C bottom, Undo, Enter
        before = xs(-1, 1000)
        clicks = [Point3d(1, -1, 0), Point3d(401, -1, 0), Point3d(99, 61, 0), Point3d(459, -1, 0), M.UNDO, None]
        rs.GetObjects = lambda *a, **k: ids
        M.ask = lambda prompt: clicks.pop(0)
        M.main()
        assert not clicks and xs(-1, 1000) == before, xs(-1, 1000)
        clicks = [Point3d(99, 61, 0), Point3d(459, -1, 0), None]  # from A's right top corner, C's right bottom one
        M.main()
        bottom = sorted(round(o.Geometry.Location.X, 3) for o in doc.Objects
                        if o.Attributes.GetUserString(M.NOTCH) and abs(o.Geometry.Location.Y) < 1e-6)
        assert bottom == [410, 430, 450], bottom  # 90, 70, 50 from x = 100 → 460 − 10, 30, 50
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, M.ask = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
