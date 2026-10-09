# -*- coding: utf-8 -*-
"""Check of pattern/Notches (positions by mode, notch points on the sew line, groups, Undo)
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
    from Rhino.Geometry import Point, Point3d, Polyline, PolylineCurve
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pattern"))
    for m in ("ZipCover", "click_undo", "Seams", "Notches"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import Notches as N
    S = sys.modules["Seams"]  # the Seams that Notches uses
    from click_undo import Steps

    tol = 0.001
    def pl(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))
    def pos(mode, click, **kw):
        o = dict(N.DEFAULTS)
        o.update(kw)
        return [round(s, 6) for s in N.positions(1000.0, mode, click, o)]

    # positions: the click's third of the edge sets From (Start / Middle / End)
    assert pos("Single", 123) == [123]  # Distance 0 — at the click
    assert pos("Single", 10, dist=100.0) == [100] and pos("Single", 990, dist=100.0) == [900]
    assert pos("Single", 600, dist=100.0) == [600] and pos("Single", 400, dist=100.0) == [400]  # Middle → click side
    assert pos("Single", 10, dist=10.0, pct=True) == [100]
    assert pos("Mid", 10) == [500]
    assert pos("Evenly", 10, first=50.0, last=50.0, count=3) == [50, 500, 950]
    assert pos("Evenly", 900, first=100.0, last=0.0, count=3) == [0, 450, 900]  # First from the corner nearer the click
    assert pos("Evenly", 10, first=100.0, last=100.0, count=1) == [500]
    assert pos("Repeat", 500, every=200.0) == [100, 300, 500, 700, 900]
    assert pos("Repeat", 10, every=300.0) == [200, 500, 800]  # from the middle wherever the click is
    assert pos("Repeat", 990, every=250.0) == [0, 250, 500, 750, 1000]  # reaches the corners exactly
    assert pos("Repeat", 500, every=600.0) == [500]

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
                          key=lambda o: (round(o.Geometry.Location.X, 3), round(o.Geometry.Location.Y, 3)))

        def now():
            return [(round(n.Geometry.Location.X, 3), round(n.Geometry.Location.Y, 3)) for n in notches()]

        seam(Point3d(50, 61, 0), 10.0)  # top edge: seam 10 → cut line y = 70; the points stay on the sew line

        clicks = [
            ({"mode": 1}, Point3d(50, 61, 0)),  # Mid of the top edge
            ({"mode": 3, "every": 20.0}, Point3d(-1, 30, 0)),  # left edge: 10, 30, 50
            ({}, N.UNDO),  # the 3 left points go
            ({"mode": 0, "dist": 2.0}, Point3d(99, 61, 0)),  # Single, 2 from the right corner of the top edge
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
        assert now() == [(50, 60), (98, 60)], now()
        assert all(isinstance(n.Geometry, Point) and n.Attributes.GetUserString(N.NOTCH) == "Point" for n in ns)
        lay = set(doc.Layers[n.Attributes.LayerIndex].FullPath for n in ns)
        assert lay == {"Pattern::Notches"}, lay
        gs = [sorted(n.Attributes.GetGroupList() or []) for n in ns]
        assert all(len(x) == 2 and g in x for x in gs) and gs[0] != gs[1], gs  # panel group + one per click

        seam(Point3d(50, 61, 0), 20.0)  # Seams moves converted notches only: the points stay
        assert now() == [(50, 60), (98, 60)], now()

        # one click, several points (bottom edge, Repeat from the middle) — one group of their own
        before = set(n.Id for n in notches())
        clicks = [({"mode": 3, "every": 20.0}, Point3d(5, -1, 0)), ({}, None)]
        N.main()
        new = [n for n in notches() if n.Id not in before]
        assert sorted(round(n.Geometry.Location.X, 3) for n in new) == [10, 30, 50, 70, 90]
        own = set(tuple(sorted(n.Attributes.GetGroupList())) for n in new)
        assert len(own) == 1 and g in list(own)[0] and len(list(own)[0]) == 2, own
        assert not any(set(list(own)[0]) - {g} <= set(x) for x in gs)  # not the group of an earlier click
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, N.ask = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
