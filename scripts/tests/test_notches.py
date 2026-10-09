# -*- coding: utf-8 -*-
"""Check of pattern/Notches (positions by mode, notch shapes, notches on the cut line moving with Seams)
in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_notches.txt next to it."""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_notches.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pattern"))
    for m in ("ZipCover", "click_undo", "Seams", "Notches"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import Notches as N
    S = sys.modules["Seams"]  # the Seams that Notches uses
    from click_undo import Steps

    Z, tol = Vector3d.ZAxis, 0.001
    def pl(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))
    def pos(mode, click, **kw):
        o = dict(N.DEFAULTS)
        o.update(kw)
        return [round(s, 6) for s in N.positions(1000.0, mode, click, o)]
    def ends(c):
        return set((round(p.X, 6), round(p.Y, 6)) for p in (c.PointAtStart, c.PointAtEnd))

    # positions: the click's third of the edge sets From (Start / Middle / End)
    assert pos("Single", 123) == [123]  # Distance 0 — at the click
    assert pos("Single", 10, dist=100.0) == [100] and pos("Single", 990, dist=100.0) == [900]
    assert pos("Single", 600, dist=100.0) == [600] and pos("Single", 400, dist=100.0) == [400]  # Middle → click side
    assert pos("Single", 10, dist=10.0, pct=True) == [100]
    assert pos("Mid", 10) == [500]
    assert pos("Evenly", 10, first=50.0, last=50.0, count=3) == [50, 500, 950]
    assert pos("Evenly", 900, first=100.0, last=0.0, count=3) == [0, 450, 900]  # First from the corner nearer the click
    assert pos("Evenly", 10, first=100.0, last=100.0, count=1) == [500]
    assert pos("Repeat", 500, pos=0.0, every=200.0) == [100, 300, 500, 700, 900]
    assert pos("Repeat", 500, pos=100.0, every=200.0) == [0, 200, 400, 600, 800, 1000]
    assert pos("Repeat", 10, pos=0.0, every=300.0) == [200, 500, 800]  # from the middle wherever the click is
    assert pos("Repeat", 990, pos=50.0, every=200.0) == [50, 250, 450, 550, 750, 950]

    # shapes at base (50, 60), outside +Y
    b, o = Point3d(50, 60, 0), Vector3d(0, 1, 0)
    assert ends(N.notch(b, o, Z, "Slit", "In", 6, 5)) == {(50, 60), (50, 55)}
    assert ends(N.notch(b, o, Z, "Slit", "Out", 6, 5)) == {(50, 60), (50, 65)}
    assert ends(N.notch(b, o, Z, "Slit", "Center", 6, 5)) == {(50, 57.5), (50, 62.5)}
    v = N.notch(b, o, Z, "V", "In", 6, 5)
    ok, vp = v.TryGetPolyline()
    assert ok and sorted((round(p.X, 6), round(p.Y, 6)) for p in vp) == [(47, 60), (50, 55), (53, 60)]

    # knife V for the circular blade (cuts c = 3 past both ends of a line): Depth 3, Move 1 → legs 7, width ≈ 12.65;
    # each leg extended by 3 at both ends must run exactly edge point → apex (nothing behind the edge)
    def blade(c, over=3.0):
        u = c.PointAtEnd - c.PointAtStart
        u.Unitize()
        return set((round(p.X, 3), round(p.Y, 3)) for p in (c.PointAtStart - u * over, c.PointAtEnd + u * over))
    w, m = N.knife_width(3.0, 3.0, 1.0)
    assert abs(w - 2 * math.sqrt(40)) < 1e-9 and m == 1.0
    legs = N.knife(b, o, Z, 3.0, w, 3.0, 1.0)
    assert len(legs) == 2 and all(abs(c.GetLength() - 1.0) < 1e-9 for c in legs)
    assert [blade(c) for c in legs] == [{(43.675, 60), (50, 57)}, {(56.325, 60), (50, 57)}], [blade(c) for c in legs]
    w, m = N.knife_width(8.0, 3.0, 1.0)  # deeper than 2·3 + 1: the legs meet straight — one slit, move 2
    assert (w, m) == (0.0, 2.0)
    legs = N.knife(b, o, Z, 8.0, w, 3.0, m)
    assert len(legs) == 1 and blade(legs[0]) == {(50, 60), (50, 52)}

    old = sc.doc, rs.GetObjects, N.ask
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        pid = doc.Objects.AddCurve(pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)))
        g = doc.Groups.Add()
        doc.Groups.AddToGroup(g, pid)

        def seam(click, width):
            sc.sticky.update({"Seams_mode": 0, "Seams_width": width, "Seams_angle": 30.0})
            st = Steps(doc)
            st.start()
            assert S.apply(doc, pid, click, st, tol) is None

        def notches():
            return sorted((o for o in doc.Objects if o.Attributes.GetUserString(N.NOTCH)),
                          key=lambda o: (round(o.Geometry.PointAtStart.X, 3), round(o.Geometry.PointAtStart.Y, 3)))

        seam(Point3d(50, 61, 0), 10.0)  # top edge: seam 10 → cut line y = 70
        seam(Point3d(101, 30, 0), 10.0)  # right edge: seam 10 → cut line x = 110

        clicks = [
            ({"mode": 1, "tool": 1, "kdepth": 3.0, "over": 3.0, "move": 1.0}, Point3d(50, 61, 0)),  # Mid, knife V

            ({"mode": 3, "pos": 0.0, "every": 20.0, "tool": 0}, Point3d(-1, 30, 0)),  # left, no seam
            ({}, N.UNDO),  # the 3 left notches go
            ({"mode": 0, "dist": 2.0, "tool": 0, "style": 0, "place": 0, "depth": 5.0}, Point3d(99, 61, 0)),  # pen
            ({}, None),
        ]

        def fake_ask(gp, d):
            st, click = clicks.pop(0)
            sc.sticky.update(dict((N.STICKY + "_" + k, v) for k, v in st.items()))
            return click

        sc.sticky[N.STICKY + "_angle"] = 30.0
        rs.GetObjects = lambda *a, **k: [pid]
        N.ask = fake_ask
        N.main()

        def real(y):  # what ends up cut / drawn when the line runs at y: knife V legs (blade), pen slit
            return [{(43.675, y), (50, y - 3)}, {(56.325, y), (50, y - 3)}, {(98, y), (98, y - 5)}]

        def now():
            return [blade(n.Geometry) if n.Attributes.GetUserString("NotchTool") == "Cut" else
                    set((round(p.X, 3), round(p.Y, 3)) for p in (n.Geometry.PointAtStart, n.Geometry.PointAtEnd))
                    for n in notches()]

        ns = notches()
        assert now() == real(70), now()
        lay = [doc.Layers[n.Attributes.LayerIndex].Name for n in ns]
        assert lay == ["INT", "INT", "INK"], lay  # Tool Cut → INT (inner cuts), Mark → INK
        gs = [sorted(n.Attributes.GetGroupList() or []) for n in ns]
        assert all(len(x) == 2 and g in x for x in gs) and gs[0] == gs[1] != gs[2], gs  # panel group + one per click
        assert [(n.Attributes.GetUserString(N.NOTCH), n.Attributes.GetUserString("NotchPlace")) for n in ns] == \
            [("V", "In"), ("V", "In"), ("Slit", "In")]

        seam(Point3d(50, 61, 0), 20.0)  # top seam 20 → notches out to y = 80 (the one by the corner too, not sideways)
        assert now() == real(80), now()
        seam(Point3d(101, 30, 0), 0.0)  # right seam off: top notches stay
        assert now() == real(80)
        seam(Point3d(50, 61, 0), 0.0)  # no seam left: cut line deleted, notches back on the sew line
        assert not [o for o in doc.Objects if o.Attributes.GetUserString(S.KEY)]
        assert now() == real(60), now()

        # one click, several notches (bottom edge, Repeat from the middle) — one group of their own
        before = set(n.Id for n in notches())
        clicks = [({"mode": 3, "pos": 0.0, "every": 20.0}, Point3d(50, -1, 0)), ({}, None)]
        N.main()
        new = [n for n in notches() if n.Id not in before]
        assert len(new) == 5, len(new)  # 10, 30, 50, 70, 90
        own = set(tuple(sorted(n.Attributes.GetGroupList())) for n in new)
        assert len(own) == 1 and g in list(own)[0] and len(list(own)[0]) == 2, own
        assert not any(set(list(own)[0]) - {g} <= set(x) for x in gs)  # not the group of an earlier click

        # option Standard (knife only): the plotter standard back into sticky and the option fields
        class FakeGP(object):  # the command line: picks options by name, then a point
            def __init__(self, picks):
                self.picks, self.names = picks, []
            def ClearCommandOptions(self):
                self.names = []
            def SetCommandPrompt(self, text):
                pass
            def add(self, name, *a):
                self.names.append(name)
                return len(self.names)
            AddOption = AddOptionList = AddOptionDouble = AddOptionToggle = AddOptionInteger = add
            def Get(self):
                pick = self.picks.pop(0)
                if pick == "point":
                    return Rhino.Input.GetResult.Point
                self.i = self.names.index(pick) + 1
                return Rhino.Input.GetResult.Option
            def OptionIndex(self):
                return self.i
            def Point(self):
                return Point3d(1, 2, 0)

        sc.sticky.update({N.STICKY + "_tool": 0})
        ask = old[2]  # the real one (N.ask is the fake click list here)
        gp = FakeGP(["point"])
        ask(gp, doc)
        assert "Standard" not in gp.names  # pen: no Standard
        sc.sticky.update(dict((N.STICKY + "_" + k, v) for k, v in {"tool": 1, "mode": 0, "pos": 7.0, "every": 123.0,
                         "kdepth": 5.0, "over": 3.0, "move": 1.0, "angle": 45.0}.items()))
        gp = FakeGP(["Standard", "point"])
        assert ask(gp, doc) == Point3d(1, 2, 0)
        assert "Position" in gp.names  # mode switched to Repeat, its options shown
        got = dict((k, N.opt(k, doc)) for k in N.STANDARD)
        assert got == N.STANDARD, got  # survives the write-back of the option fields after the next Get
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, N.ask = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
