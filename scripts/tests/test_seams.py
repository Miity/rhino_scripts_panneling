# -*- coding: utf-8 -*-
"""Check of pattern/Seams (seam allowance: cut line around the panel, corner styles) in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_seams.txt next to it."""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_seams.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import AreaMassProperties, Circle, NurbsCurve, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pattern"))
    for m in ("ZipCover", "click_undo", "Seams"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import Seams as M

    Z, tol = Vector3d.ZAxis, 0.001
    def pl(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))
    def area(c):
        return round(AreaMassProperties.Compute(c).Area, 3)
    def cut(panel, ws, styles):
        """ws: width per edge, or one number for all; styles: one style for all corners."""
        es = M.edges(M.loop(panel, Z), 30, tol)
        ws = ws if isinstance(ws, list) else [ws] * len(es)
        c = M.build(es, ws, [styles] * len(es), Z, tol)
        assert c is not None and c.IsClosed, (ws, styles)
        return c
    def top_only(panel):
        es = M.edges(M.loop(panel, Z), 30, tol)
        return [10.0 if abs(M.mid(e).Y - 60) < 1e-6 else 0.0 for e in es]

    # option values shown in the prompt must be valid Rhino option values
    for v in [M.label(p) for p in M.PRESETS_MM] + ["Off", M.label(12.5)] + M.STYLES + M.MODES:
        assert Rhino.Input.Custom.CommandLineOption.IsValidOptionValueName(v), v

    # rectangle 100×60, both orientations: all edges 10 → Extend square corners, Slant cut across, Return 90° back
    for rect in (pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)), pl((0, 0), (0, 60), (100, 60), (100, 0), (0, 0))):
        assert len(M.edges(M.loop(rect, Z), 30, tol)) == 4
        c = cut(rect, 10.0, "Extend")
        bb = c.GetBoundingBox(True)
        assert (round(bb.Min.X, 6), round(bb.Min.Y, 6), round(bb.Max.X, 6), round(bb.Max.Y, 6)) == (-10, -10, 110, 70)
        assert area(c) == 9600, area(c)
        assert area(cut(rect, 10.0, "Slant")) == 9400  # 4 corners: triangle 50 instead of square 100
        assert area(cut(rect, 10.0, "Return")) == 9200  # 4 corners without the square
        for style in M.STYLES:  # only the top edge: its seam ends flush with the side edges, any style
            assert area(cut(rect, top_only(rect), style)) == 7000, style

    # L-shape: the inner corner (40, 40) — seams cut where they cross; 5 outer corners by style
    L = pl((0, 0), (100, 0), (100, 40), (40, 40), (40, 100), (0, 100), (0, 0))
    assert area(cut(L, 10.0, "Extend")) == 10800  # 120×120 − 60×60
    assert area(cut(L, 10.0, "Return")) == 10300  # L 6400 + strips 4000 − overlap 100
    assert area(cut(L, 10.0, "Slant")) == 10550  # + 5 triangles of 50

    # sharp corner (≈ 5.7°): Extend goes at most one seam width per seam, not the long miter (≈ 200)
    sharp = pl((0, 0), (200, 0), (0, 20), (0, 0))
    assert cut(sharp, 10.0, "Extend").GetBoundingBox(True).Max.X < 225
    cut(sharp, 10.0, "Slant")

    # circle (no corners) — one closed edge, plain offset
    circ = NurbsCurve.CreateFromCircle(Circle(Point3d(0, 0, 0), 50))
    assert abs(area(cut(circ, 10.0, "Extend")) - math.pi * 60 * 60) < 1.0

    # stored data round trip
    assert [(p.X, v) for p, v in M.parse(M.dump([(Point3d(1.5, 2, 0), "10"), (Point3d(-3, 0, 0), "Slant")]))] \
        == [(1.5, "10"), (-3.0, "Slant")]

    # main(): clicks with Undo / All / Corner / Off on a grouped panel; one cut line on Pattern::Seams, rebuilt in place
    old = sc.doc, rs.GetObjects, M.ask
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        pid = doc.Objects.AddCurve(pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)))
        g = doc.Groups.Add()
        doc.Groups.AddToGroup(g, pid)
        before = doc.Objects.FindId(pid).Geometry.GetLength()

        def cuts():
            return [o for o in doc.Objects if o.Attributes.GetUserString(M.KEY)]

        def area_now():
            cs = cuts()
            assert len(cs) == 1, len(cs)
            return area(cs[0].Geometry)

        script = [
            ({"mode": 0, "width": 1}, Point3d(50, 61, 0), lambda: area_now() == 7000),  # top edge 10 mm
            ({}, M.UNDO, lambda: not cuts()),
            ({}, Point3d(50, 61, 0), lambda: area_now() == 7000),
            ({}, M.ALL, lambda: area_now() == 9600),  # every edge 10
            ({"mode": 1, "corner": 1}, Point3d(99, 59, 0), lambda: area_now() == 9550),  # corner (100, 60) Slant
            ({"mode": 0, "width": len(M.PRESETS_MM)}, Point3d(101, 30, 0), lambda: area_now() == 8800),  # right Off
        ]
        checks = []

        def fake_ask(gp, d):
            if checks:
                assert checks.pop()(), "after click %d" % (len(script) - len(todo) - 1)
            if not todo:
                return None
            st, click, check = todo.pop(0)
            sc.sticky.update(dict((M.STICKY + "_" + k, v) for k, v in st.items()))
            checks.append(check)
            return click

        todo = list(script)
        sc.sticky[M.STICKY + "_angle"] = 30.0
        rs.GetObjects = lambda *a, **k: [pid]
        M.ask = fake_ask
        M.main()
        cid = cuts()[0].Id
        assert doc.Layers[cuts()[0].Attributes.LayerIndex].FullPath == "Pattern::Seams"
        assert list(cuts()[0].Attributes.GetGroupList() or []) == [g]  # moves with the panel
        assert len(M.parse(cuts()[0].Attributes.GetUserString(M.KEY))) == 4

        # second run: the cut line itself selected too — not a panel; left edge 8 mm, same cut line object rebuilt
        todo = [({"mode": 0, "width": 0}, Point3d(-1, 30, 0), lambda: area_now() == 8640)]
        rs.GetObjects = lambda *a, **k: [pid, cid]
        M.main()
        assert [o.Id for o in cuts()] == [cid]
        assert doc.Objects.FindId(pid).Geometry.GetLength() == before  # panel not changed
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, M.ask = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
