# -*- coding: utf-8 -*-
"""Check of pattern/ConvertNotches (notch shapes; notch points of Notches and older battute → a format, and back;
notches moving with Seams) in Rhino 8:
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_convert_notches.txt next to it."""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_convert_notches.txt"), "w")
try:
    import Rhino
    import System
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Circle, LineCurve, Point, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pattern"))
    for m in ("ZipCover", "click_undo", "Seams", "Notches", "PointsToCrosses", "ConvertNotches"):
        sys.modules.pop(m, None)  # live Rhino keeps old module versions
    import ConvertNotches as C
    S = sys.modules["Seams"]  # the Seams that ConvertNotches uses
    import Notches as N
    from click_undo import Steps

    tol = 0.001
    def pl(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))
    def r3(p):
        return (round(p.X, 3), round(p.Y, 3))
    def ends(c):
        return set((round(p.X, 6), round(p.Y, 6)) for p in (c.PointAtStart, c.PointAtEnd))
    Z = Vector3d.ZAxis

    # shapes at base (50, 60), outside +Y
    b, o = Point3d(50, 60, 0), Vector3d(0, 1, 0)
    assert ends(C.notch(b, o, Z, "Slit", "In", 6, 5)) == {(50, 60), (50, 55)}
    assert ends(C.notch(b, o, Z, "Slit", "Out", 6, 5)) == {(50, 60), (50, 65)}
    assert ends(C.notch(b, o, Z, "Slit", "Center", 6, 5)) == {(50, 57.5), (50, 62.5)}
    v = C.notch(b, o, Z, "V", "In", 6, 5)
    ok, vp = v.TryGetPolyline()
    assert ok and sorted((round(p.X, 6), round(p.Y, 6)) for p in vp) == [(47, 60), (50, 55), (53, 60)]

    # knife V for the circular blade (cuts c = 3 past both ends of a line): Depth 3, Move 1 → legs 7, width ≈ 12.65;
    # each leg extended by 3 at both ends must run exactly edge point → apex (nothing behind the edge)
    def blade(c, over=3.0):
        u = c.PointAtEnd - c.PointAtStart
        u.Unitize()
        return set((round(p.X, 3), round(p.Y, 3)) for p in (c.PointAtStart - u * over, c.PointAtEnd + u * over))
    w, m = C.knife_width(3.0, 3.0, 1.0)
    assert abs(w - 2 * math.sqrt(40)) < 1e-9 and m == 1.0
    legs = C.knife(b, o, Z, 3.0, w, 3.0, 1.0)
    assert len(legs) == 2 and all(abs(c.GetLength() - 1.0) < 1e-9 for c in legs)
    assert [blade(c) for c in legs] == [{(43.675, 60), (50, 57)}, {(56.325, 60), (50, 57)}], [blade(c) for c in legs]
    w, m = C.knife_width(8.0, 3.0, 1.0)  # deeper than 2·3 + 1: the legs meet straight — one slit, move 2
    assert (w, m) == (0.0, 2.0)
    legs = C.knife(b, o, Z, 8.0, w, 3.0, m)
    assert len(legs) == 1 and blade(legs[0]) == {(50, 60), (50, 52)}

    # option Standard: the plotter's knife values back into sticky
    sc.sticky.update({"ConvertNotches_kdepth": 5.0, "ConvertNotches_over": 3.0, "ConvertNotches_angle": 45.0})

    old = sc.doc, rs.GetObjects, C.ask
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        pid = doc.Objects.AddCurve(pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)))
        g = doc.Groups.Add()
        doc.Groups.AddToGroup(g, pid)
        sc.sticky.update({"Seams_mode": 0, "Seams_width": 10.0, "Seams_angle": 30.0})
        st = Steps(doc)
        st.start()
        assert S.apply(doc, pid, Point3d(50, 61, 0), st, tol) is None  # top seam 10 → cut line y = 70
        cid = [o.Id for o in doc.Objects if o.Attributes.GetUserString(S.KEY)][0]

        # older battute: points on the top edge + the centre tick (Parts::SewingMarks, one group); a seam circle
        # 10 mm inside the top edge; a point far away
        sew = Rhino.DocObjects.ObjectAttributes()
        sew.LayerIndex = doc.Layers.Add("Parts", System.Drawing.Color.Black)
        lay = Rhino.DocObjects.Layer()
        lay.Name, lay.ParentLayerId = "SewingMarks", doc.Layers[sew.LayerIndex].Id
        sew.LayerIndex = doc.Layers.Add(lay)
        olds = [doc.Objects.Add(Point(Point3d(20, 60, 0)), sew), doc.Objects.Add(Point(Point3d(50, 60, 0)), sew),
                doc.Objects.AddCurve(LineCurve(Point3d(50, 60, 0), Point3d(50, 50, 0)), sew)]
        h = doc.Groups.Add()
        for i in olds:
            doc.Groups.AddToGroup(h, i)
        circle = doc.Objects.AddCircle(Circle(Point3d(80, 50, 0), 2))
        far = doc.Objects.Add(Point(Point3d(500, 500, 0)))
        C.use_standard(doc)
        assert dict((k, C.opt(k, doc)) for k in C.STANDARD) == C.STANDARD
        # notch points by Notches: the middle of the right edge, the middle of the bottom edge
        sc.sticky.update({"Notches_mode": 1, "Notches_angle": 30.0})
        assert N.place(doc, pid, Point3d(101, 30, 0), tol) == 1
        assert N.place(doc, pid, Point3d(50, -1, 0), tol) == 1
        made = [o.Id for o in doc.Objects if o.Attributes.GetUserString(N.NOTCH)]
        assert len(made) == 2 and all(isinstance(doc.Objects.FindId(i).Geometry, Point) for i in made)

        def notches():
            return [o for o in doc.Objects if o.Attributes.GetUserString(N.NOTCH)]

        def run(settings, ids):
            sc.sticky.update(dict(("ConvertNotches_" + k, v) for k, v in settings.items()))
            rs.GetObjects = lambda *a, **k: ids
            C.ask = lambda d: True
            C.main()

        # 1. everything → knife V (Overcut 1, Move 3, Depth 2): width 2·√21, on the cut line where there is one
        run({"tool": 1, "kdepth": 2.0, "over": 1.0, "move": 3.0, "keep": False, "reach": 20.0, "angle": 30.0},
            [pid, cid, circle, far] + olds + made)
        ns = notches()
        assert len(ns) == 10, len(ns)  # 5 spots: top 20, 50 (point + tick), 80 (circle), right, bottom
        assert all(doc.Layers[n.Attributes.LayerIndex].Name == "INT" for n in ns)
        h2 = math.sqrt(21)  # half width
        def blade(c):  # what the circular blade cuts: the line + 1 at both ends
            u = c.PointAtEnd - c.PointAtStart
            u.Unitize()
            return frozenset((r3(c.PointAtStart - u), r3(c.PointAtEnd + u)))
        want = set()
        for (bx, by), (ox, oy) in (((20, 70), (0, 1)), ((50, 70), (0, 1)), ((80, 70), (0, 1)),
                                   ((100, 30), (1, 0)), ((50, 0), (0, -1))):
            apex = (round(bx - ox * 2, 3), round(by - oy * 2, 3))
            for s in (1, -1):
                want.add(frozenset(((round(bx + oy * s * h2, 3), round(by - ox * s * h2, 3)), apex)))
        got = set(blade(n.Geometry) for n in ns)
        assert got == want, (sorted(got), sorted(want))
        ids = set(o.Id for o in doc.Objects)
        assert far in ids and not (set(olds + made + [circle]) & ids)  # far one skipped; originals replaced
        for n in ns:  # groups kept + the panel's
            gl = set(n.Attributes.GetGroupList() or [])
            assert g in gl
            if abs(n.Geometry.PointAtStart.Y - 70) < 3 and n.Geometry.PointAtStart.X < 60:  # top 20 / 50
                assert h in gl, gl

        # 2. back to pen slits In 5 — the knife V centres found again from their legs
        run({"tool": 0, "style": 0, "place": 0, "depth": 5.0}, [pid] + [n.Id for n in ns])
        ns = notches()
        got = sorted(sorted([r3(n.Geometry.PointAtStart), r3(n.Geometry.PointAtEnd)]) for n in ns)
        assert got == sorted(sorted(p) for p in ([(20, 70), (20, 65)], [(50, 70), (50, 65)], [(80, 70), (80, 65)],
                                                 [(100, 30), (95, 30)], [(50, 0), (50, 5)])), got
        assert all(doc.Layers[n.Attributes.LayerIndex].Name == "INK" for n in ns)

        # 3. Seams moves them: top seam 20 → the top slits out to y = 80, the others stay
        st = Steps(doc)
        st.start()
        sc.sticky["Seams_width"] = 20.0
        assert S.apply(doc, pid, Point3d(50, 61, 0), st, tol) is None
        got = sorted(sorted([r3(n.Geometry.PointAtStart), r3(n.Geometry.PointAtEnd)]) for n in notches())
        assert got == sorted(sorted(p) for p in ([(20, 80), (20, 75)], [(50, 80), (50, 75)], [(80, 80), (80, 75)],
                                                 [(100, 30), (95, 30)], [(50, 0), (50, 5)])), got
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, C.ask = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
