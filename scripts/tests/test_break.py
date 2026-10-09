# -*- coding: utf-8 -*-
"""Check of pattern/Break (break points split panel edges for Seams / Notches) in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_break.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_break.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import AreaMassProperties, Circle, NurbsCurve, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pattern"))
    for m in ("ZipCover", "click_undo", "Seams", "Notches", "Break"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import Notches as N
    import Break as B
    S = sys.modules["Seams"]  # the Seams that Break uses
    from click_undo import Steps

    Z, tol = Vector3d.ZAxis, 0.001
    def pl(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))

    # edges(): break points are corners; one at a corner adds nothing; a circle is split too
    rect = S.loop(pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)), Z)
    assert len(S.edges(rect, 30, tol, [Point3d(50, 60, 0), Point3d(0, 30, 0)])) == 6
    assert len(S.edges(rect, 30, tol, [Point3d(100, 0, 0)])) == 4
    circ = S.loop(NurbsCurve.CreateFromCircle(Circle(Point3d(0, 0, 0), 50)), Z)
    assert len(S.edges(circ, 30, tol, [Point3d(50, 0, 0)])) == 1  # one break — still the whole loop
    two = S.edges(circ, 30, tol, [Point3d(50, 0, 0), Point3d(-50, 0, 0)])
    assert len(two) == 2 and abs(two[0].GetLength() - two[1].GetLength()) < 1e-6

    old = sc.doc, rs.GetObjects, B.ask
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        pid = doc.Objects.AddCurve(pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)))
        g = doc.Groups.Add()
        doc.Groups.AddToGroup(g, pid)

        # main(): add (50, 60) and (0, 30), a click on (50, 60) removes it, Undo brings it back
        clicks = [Point3d(50, 61, 0), Point3d(0.5, 30, 0), Point3d(50.5, 60.2, 0), B.UNDO, None]
        B.ask = lambda gp, d: clicks.pop(0)
        sc.sticky["Break_pick"] = 3.0
        rs.GetObjects = lambda *a, **k: [pid]
        B.main()
        bs = S.break_objects(doc)
        assert sorted((round(o.Geometry.Location.X, 6), round(o.Geometry.Location.Y, 6)) for o in bs) == [(0, 30), (50, 60)]
        assert all(doc.Layers[o.Attributes.LayerIndex].FullPath == "Pattern::Breaks" for o in bs)
        assert all(list(o.Attributes.GetGroupList() or []) == [g] for o in bs)  # moves with the panel

        # Seams: the two halves of the top edge get their own widths — 20 on the left, 10 on the right
        sc.sticky.update({"Seams_mode": 0, "Seams_angle": 30.0})
        for click, w in ((Point3d(25, 61, 0), 20.0), (Point3d(75, 61, 0), 10.0)):
            sc.sticky["Seams_width"] = w
            st = Steps(doc)
            st.start()
            assert S.apply(doc, pid, click, st, tol) is None
        cuts = [o for o in doc.Objects if o.Attributes.GetUserString(S.KEY)]
        assert len(cuts) == 1 and round(AreaMassProperties.Compute(cuts[0].Geometry).Area, 3) == 7500  # 6000+1000+500

        # Notches: Mid of the right half of the top edge — at x = 75, on its cut line (y = 70)
        sc.sticky.update({"Notches_mode": 1, "Notches_tool": 0, "Notches_style": 0, "Notches_place": 0,
                          "Notches_depth": 5.0, "Notches_angle": 30.0})
        assert N.place(doc, pid, Point3d(75, 61, 0), tol) == 1
        n = [o for o in doc.Objects if o.Attributes.GetUserString(N.NOTCH)][0].Geometry
        assert set((round(p.X, 6), round(p.Y, 6)) for p in (n.PointAtStart, n.PointAtEnd)) == {(75, 70), (75, 65)}
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, B.ask = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
