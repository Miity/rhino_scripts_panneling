# -*- coding: utf-8 -*-
"""Check of the ripresa (Break Type=Ripresa: mark + end notches; Notches / Match Notches measure the edge sewn,
without it; Seams does not see it) in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_ripresa.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_ripresa.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Point3d, Polyline, PolylineCurve
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pattern"))
    for m in ("ZipCover", "click_undo", "Seams", "Notches", "MatchNotches", "Break"):  # live Rhino keeps old versions
        sys.modules.pop(m, None)
    import Notches as N
    import MatchNotches as M
    import Break as B
    S = sys.modules["Seams"]

    tol = 0.001
    def pl(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))

    old = sc.doc, rs.GetObjects, B.ask
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        pa = doc.Objects.AddCurve(pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)))
        # B: top 50 + ripresa (250, 60) → (255, 64), 6.4 long, a 38.7° step at each end + 50 = 100 sewn
        pb = doc.Objects.AddCurve(pl((200, 0), (305, 0), (305, 64), (255, 64), (250, 60), (200, 60), (200, 0)))
        ids = [pa, pb]

        def notches():
            return sorted((round(o.Geometry.Location.X, 3), round(o.Geometry.Location.Y, 3)) for o in doc.Objects
                          if o.Attributes.GetUserString(S.NOTCH) == "Point")

        # Break Type=Ripresa: mark + notches at both ends; Undo takes them off; again — kept
        clicks = [Point3d(252.5, 62.5, 0), B.UNDO, Point3d(252.5, 62.5, 0), None]
        B.ask = lambda gp, d: clicks.pop(0)
        sc.sticky["Break_type"] = 1
        rs.GetObjects = lambda *a, **k: [pb]
        B.main()
        marks = [o for o in S.break_objects(doc) if o.Attributes.GetUserString(S.BREAK) == S.RIPRESA]
        assert len(marks) == 1 and notches() == [(250, 60), (255, 64)], notches()
        assert len(set(tuple(o.Attributes.GetGroupList() or []) for o in doc.Objects if o.Id != pa and o.Id != pb)) == 1

        lp = S.loop(doc.Objects.FindId(pb).Geometry, Rhino.Geometry.Vector3d.ZAxis)
        rips = S.riprese_on(doc, lp, 1.0)
        assert len(rips) == 1 and not S.breaks_on(doc, lp, 1.0)  # Seams does not see it
        assert len(S.edges(lp, 30, tol)) == 6 and len(S.edges(lp, 30, tol, (), rips)) == 4  # top runs through it
        sk = [(50, 50 + 41 ** 0.5)]
        assert S.to_real(50, sk) == 50 and abs(S.to_real(70, sk) - (70 + 41 ** 0.5)) < 1e-9
        assert S.to_sewn(52, sk) == 50 and abs(S.to_sewn(80, sk) - (80 - 41 ** 0.5)) < 1e-9

        # Notches Mid on B top: the sewn middle — at the ripresa (its end nearer the edge start; both sew together)
        sc.sticky.update({"Notches_mode": 1, "Notches_angle": 30.0})
        assert N.place(doc, pb, Point3d(220, 61, 0), tol) == 1
        assert notches() == [(250, 60), (255, 64), (255, 64)], notches()

        # Match Notches: A top 100, B top through the ripresa 100 sewn (ripresa out)
        sc.sticky["MatchNotches_angle"] = 30.0
        a, b = M.pick(doc, ids, Point3d(50, 61, 0), tol), M.pick(doc, ids, Point3d(220, 61, 0), tol)
        assert (round(M.length(a), 6), round(M.length(b), 6)) == (100, 100), (M.length(a), M.length(b))

        # click on the marked ripresa again: mark + its end notches go
        clicks = [Point3d(252.5, 62.5, 0), None]
        B.main()
        assert not S.break_objects(doc) and [p for p in notches() if p in ((250, 60), (255, 64))] == [], notches()
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, B.ask = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
