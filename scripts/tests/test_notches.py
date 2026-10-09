# -*- coding: utf-8 -*-
"""Check of pattern/Notches (positions by mode, notch shapes, notches on the cut line moving with Seams)
in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_notches.txt next to it."""
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
    assert pos("Repeat", 500, pos=0.0, every=200.0, both=True) == [100, 300, 500, 700, 900]
    assert pos("Repeat", 500, pos=100.0, every=200.0, both=True) == [0, 200, 400, 600, 800, 1000]
    assert pos("Repeat", 600, pos=0.0, every=200.0, both=False) == [500, 700, 900]  # middle third, towards the click
    assert pos("Repeat", 10, pos=50.0, every=200.0) == [50, 250, 450, 650, 850]
    assert pos("Repeat", 990, pos=50.0, every=200.0) == [150, 350, 550, 750, 950]

    # shapes at base (50, 60), outside +Y
    b, o = Point3d(50, 60, 0), Vector3d(0, 1, 0)
    assert ends(N.notch(b, o, Z, "Slit", "In", 6, 5)) == {(50, 60), (50, 55)}
    assert ends(N.notch(b, o, Z, "Slit", "Out", 6, 5)) == {(50, 60), (50, 65)}
    assert ends(N.notch(b, o, Z, "Slit", "Center", 6, 5)) == {(50, 57.5), (50, 62.5)}
    v = N.notch(b, o, Z, "V", "In", 6, 5)
    ok, vp = v.TryGetPolyline()
    assert ok and sorted((round(p.X, 6), round(p.Y, 6)) for p in vp) == [(47, 60), (50, 55), (53, 60)]

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
            ({"mode": 1, "style": 0, "place": 0, "tool": 1, "depth": 5.0}, Point3d(50, 61, 0)),  # Mid, Slit In, Cut
            ({"mode": 3, "pos": 0.0, "every": 20.0, "both": True, "tool": 0}, Point3d(-1, 30, 0)),  # left, no seam
            ({}, N.UNDO),  # the 3 left notches go
            ({"mode": 0, "dist": 2.0}, Point3d(99, 61, 0)),  # Single 2 from the top-right corner (Start third)
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

        ns = notches()
        assert [ends(n.Geometry) for n in ns] == [{(50, 70), (50, 65)}, {(98, 70), (98, 65)}], [ends(n.Geometry) for n in ns]
        lay = [doc.Layers[n.Attributes.LayerIndex].Name for n in ns]
        assert lay == ["CUT", "INK"], lay  # Tool Cut → CUT, Mark → INK
        assert all(list(n.Attributes.GetGroupList() or []) == [g] for n in ns)  # move with the panel
        assert ns[0].Attributes.GetUserString("NotchPlace") == "In" and ns[0].Attributes.GetUserString(N.NOTCH) == "Slit"

        seam(Point3d(50, 61, 0), 20.0)  # top seam 20 → notches out to y = 80 (the one by the corner too, not sideways)
        assert [ends(n.Geometry) for n in notches()] == [{(50, 80), (50, 75)}, {(98, 80), (98, 75)}]
        seam(Point3d(101, 30, 0), 0.0)  # right seam off: top notches stay
        assert [ends(n.Geometry) for n in notches()] == [{(50, 80), (50, 75)}, {(98, 80), (98, 75)}]
        seam(Point3d(50, 61, 0), 0.0)  # no seam left: cut line deleted, notches back on the sew line
        assert not [o for o in doc.Objects if o.Attributes.GetUserString(S.KEY)]
        assert [ends(n.Geometry) for n in notches()] == [{(50, 60), (50, 55)}, {(98, 60), (98, 55)}]
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, N.ask = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
