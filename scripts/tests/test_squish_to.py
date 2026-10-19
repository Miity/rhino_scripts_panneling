# -*- coding: utf-8 -*-
"""Check of pattern/SquishTo (3D marks onto the squished surface wherever it is now: moved, turned, mirrored;
the link's 3D side shifted from the 3D surface — fitted onto the selected one, of several; marks off the panel skipped;
marks already there not placed again, only the new ones selected; only the surface selected — the visible marks on it;
no 3D surface / wrong one / DupBorder curve refused) in Rhino 8:
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_squish_to.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_squish_to.txt"), "w")
try:
    import math
    import System
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import (Curve, GeometryBase, NurbsSurface, Plane, Point, Point3d, SquishParameters, Squisher,
                                TextDot, Transform, Vector3d)
    from System.Collections.Generic import List
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pattern"))
    sys.modules.pop("SquishTo", None)  # live Rhino keeps old module versions
    import SquishTo as M

    tol = 0.001
    old = sc.doc, rs.GetObjects, rs.GetObject
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        doc.ModelAbsoluteTolerance = tol
        sc.doc = doc
        # doubly curved, no symmetry: a twisted quad with a bulge
        srf = NurbsSurface.CreateFromCorners(Point3d(0, 0, 0), Point3d(1000, 0, 150), Point3d(1200, 700, 0),
                                             Point3d(-100, 600, 300))
        srf = srf.Rebuild(3, 3, 6, 6)
        srf.Points.SetPoint(3, 3, srf.Points.GetControlPoint(3, 3).Location + Vector3d(0, 0, 250))
        d0, d1 = srf.Domain(0), srf.Domain(1)
        at = lambda u, v: srf.PointAt(d0.ParameterAt(u), d1.ParameterAt(v))
        iso = srf.IsoCurve(1, d0.ParameterAt(0.5)).Trim(d1.ParameterAt(0.3), d1.ParameterAt(0.8))
        geos = [Point(at(0.3, 0.2)), TextDot("B", at(0.7, 0.6)), iso]

        # Squish now (as the command did once), marks squished along — the reference
        sp = SquishParameters.Default
        sp.SaveMapping = True
        ml, res = List[GeometryBase](), List[GeometryBase]()
        for g in geos:
            ml.Add(g)
        flat = Squisher().SquishSurface(sp, srf, ml, res)
        xf = Transform.Translation(Vector3d(3000, -500, 0)) * Transform.Rotation(math.radians(37), Vector3d.ZAxis,
                                                                                 Point3d.Origin) * Transform.Mirror(Plane.WorldYZ)
        fid = doc.Objects.AddBrep(flat)
        doc.Objects.Transform(fid, xf, True)

        # the 3D model (surface + marks) sits 5 m away from where the link's 3D side is (seen in a real drawing)
        v = Vector3d(5572, -12427, 0)
        mv = Transform.Translation(v)
        sid = doc.Objects.AddSurface(srf)
        other = doc.Objects.AddSurface(NurbsSurface.CreateFromCorners(Point3d(0, 0, 0), Point3d(900, 0, 0),
                                                                      Point3d(900, 900, 0), Point3d(0, 900, 0)))
        for i in (sid, other):
            doc.Objects.Transform(i, mv, True)
        moved = [g.Duplicate() for g in geos] + [Point(at(0.5, 0.5) + Vector3d(0, 0, 40))]  # 40 mm off — skipped
        for g in moved:
            g.Transform(mv)
        marks = [doc.Objects.AddPoint(moved[0].Location), doc.Objects.AddTextDot(moved[1]), doc.Objects.AddCurve(moved[2]),
                 doc.Objects.AddPoint(moved[3].Location)]
        li = doc.Layers.Add("Buttons", System.Drawing.Color.Red)
        a = doc.Objects.FindId(marks[0]).Attributes.Duplicate()
        a.LayerIndex = li
        a.AddToGroup(doc.Groups.Add())
        doc.Objects.ModifyAttributes(marks[0], a, True)

        exp = [xf * res[0].Location, xf * res[1].Point, xf * res[2].PointAtStart, xf * res[2].PointAtEnd]
        mid = res[2].DuplicateCurve()
        mid.Transform(xf)

        def check(name, d, fid):
            added, skipped, dups = M.transfer(d, marks, fid, tol, [other, sid])
            assert skipped == 1 and len(added) == 3 and dups == 0, (name, skipped, len(added), dups)
            g = [d.Objects.FindId(i).Geometry for i in added]
            got = [g[0].Location, g[1].Point, g[2].PointAtStart, g[2].PointAtEnd]
            e = max(x.DistanceTo(y) for x, y in zip(got, exp))
            dev = max(mid.PointAt(mid.ClosestPoint(p)[1]).DistanceTo(p) for p in
                      [g[2].PointAt(t) for t in g[2].DivideByCount(50, True)])
            assert e < 0.3 and dev < 0.3, (name, e, dev)
            sel = sorted(o.Id for o in d.Objects.GetSelectedObjects(False, False))
            assert sel == sorted(added), name
            o = d.Objects.FindId(added[0])
            assert o.Attributes.LayerIndex == li and not list(o.Attributes.GetGroupList() or []), name
            out.write("%s: marks off %.4f mm, curve off %.4f mm\n" % (name, e, dev))
            for i in added:
                d.Objects.Delete(i, True)

        check("moved, turned, mirrored", doc, fid)

        # main
        assert not isinstance(M.transfer(doc, marks, fid, tol, []), tuple)  # no 3D surface
        assert not isinstance(M.transfer(doc, marks, fid, tol, [other]), tuple)  # not the squished one
        rs.GetObjects = lambda *a, **k: marks + [sid]
        rs.GetObject = lambda *a, **k: fid
        before = set(o.Id for o in doc.Objects)
        M.main()
        new = [o.Id for o in doc.Objects if o.Id not in before]
        assert len(new) == 3
        assert M.transfer(doc, marks, fid, tol, [sid])[1:] == (1, 3)  # again: all 3 already there
        assert not list(doc.Objects.GetSelectedObjects(False, False))  # nothing new — nothing selected

        # only the surface: the visible marks on it (a hidden one, one 40 mm off, one on the other surface — not)
        for i in new:
            doc.Objects.Delete(i, True)
        h = doc.Objects.AddPoint(moved[0].Location + Vector3d(0, 0, 0))
        doc.Objects.Hide(h, True)
        doc.Objects.AddPoint(mv * Point3d(450, 450, 0))  # on the other surface
        rs.GetObjects = lambda *a, **k: [sid]
        before = set(o.Id for o in doc.Objects)
        M.main()
        new = [o.Id for o in doc.Objects if o.Id not in before]
        assert len(new) == 3, len(new)
        assert sorted(o.Id for o in doc.Objects.GetSelectedObjects(False, False)) == sorted(new)
        assert M.transfer(doc, [], fid, tol, [sid])[1:] == (0, 3)
        # a mark added on the 3D since: only it is placed
        doc.Objects.AddPoint(at(0.6, 0.3) + v)
        added, skipped, dups = M.transfer(doc, [], fid, tol, [sid, other])
        assert (len(added), dups) == (1, 3), (len(added), dups)

        # DupBorder curve refused
        b = Curve.JoinCurves(doc.Objects.FindId(fid).Geometry.DuplicateNakedEdgeCurves(True, False))[0]
        r = M.transfer(doc, marks, doc.Objects.AddCurve(b), tol, [sid])
        assert not isinstance(r, tuple), r
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, rs.GetObject = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
