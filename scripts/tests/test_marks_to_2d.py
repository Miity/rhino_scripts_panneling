# -*- coding: utf-8 -*-
"""Check of pattern/MarksTo2D (marks on a 3D surface squished and fitted onto its 2D panel: turned, moved, mirrored,
an edge changed, panel in another plane; symmetric panel — several fits; marks off the surface skipped) in Rhino 8:
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_marks_to_2d.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_marks_to_2d.txt"), "w")
try:
    import math
    import System
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import (NurbsSurface, Plane, Point, Point3d, Polyline, PolylineCurve, TextDot, Transform,
                                Vector3d)
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pattern"))
    sys.modules.pop("MarksTo2D", None)  # live Rhino keeps old module versions
    import MarksTo2D as M

    tol = 0.001
    old = sc.doc, rs.GetObjects, rs.GetObject
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        # doubly curved, no symmetry: a twisted quad with a bulge
        srf = NurbsSurface.CreateFromCorners(Point3d(0, 0, 0), Point3d(1000, 0, 150), Point3d(1200, 700, 0),
                                             Point3d(-100, 600, 300))
        srf = srf.Rebuild(3, 3, 6, 6)
        srf.Points.SetPoint(3, 3, srf.Points.GetControlPoint(3, 3).Location + Vector3d(0, 0, 250))
        sid = doc.Objects.AddSurface(srf)
        brep = rs.coercebrep(sid)
        uv = [(0.3, 0.2), (0.7, 0.6), (0.5, 0.9)]
        d0, d1 = srf.Domain(0), srf.Domain(1)
        pts = [srf.PointAt(d0.ParameterAt(u), d1.ParameterAt(v)) for u, v in uv]
        marks = [doc.Objects.AddPoint(pts[0]), doc.Objects.AddTextDot(TextDot("B", pts[1])),
                 doc.Objects.AddCurve(srf.IsoCurve(1, d0.ParameterAt(0.5)).Trim(d1.ParameterAt(0.3), d1.ParameterAt(0.8))),
                 doc.Objects.AddPoint(pts[2] + Vector3d(0, 0, 40))]  # 40 mm above — skipped

        flat, res = M.squish(brep.Faces[0], [doc.Objects.FindId(m).Geometry for m in marks[:3]])
        src = flat.Faces[0].OuterLoop.To3dCurve()

        def expect(xf):  # squished marks moved like the panel
            return [xf * res[0].Location, xf * res[1].Point, xf * res[2].PointAtStart, xf * res[2].PointAtEnd]

        def got(ids):
            g = [doc.Objects.FindId(i).Geometry for i in ids]
            return [g[0].Location, g[1].Point, g[2].PointAtStart, g[2].PointAtEnd]

        def check(name, panel_crv, xf, err):
            pid = doc.Objects.AddCurve(panel_crv)
            r = M.transfer(doc, sid, marks, pid, tol)
            assert isinstance(r, tuple), (name, r)
            place, meds, skipped = r
            ids = place(0)
            assert skipped == 1 and len(ids) == 3, (name, skipped, len(ids))
            d = max(a.DistanceTo(b) for a, b in zip(got(ids), expect(xf)))
            assert d < err, (name, d, meds)
            out.write("%s: off %.4f mm, fits %s\n" % (name, d, ["%.3f" % m for m in meds]))
            return ids

        # 1. turned 37°, moved, mirrored
        xf = Transform.Translation(Vector3d(3000, -500, 0)) * Transform.Rotation(math.radians(37), Vector3d.ZAxis,
                                                                                 Point3d.Origin) * Transform.Mirror(Plane.WorldYZ)
        p = src.DuplicateCurve()
        p.Transform(xf)
        check("rigid + mirror", p, xf, 0.01)

        # 2. one stretch of the edge pushed out 30 mm (edited since): the rest still fits
        xf2 = Transform.Translation(Vector3d(-2000, 1500, 0)) * Transform.Rotation(math.radians(-120), Vector3d.ZAxis,
                                                                                   Point3d.Origin)
        q = [src.PointAt(t) for t in src.DivideByCount(400, True)]
        cen = Rhino.Geometry.AreaMassProperties.Compute(src).Centroid
        q = [x + (x - cen) / (x - cen).Length * 30 if 40 <= i < 90 else x for i, x in enumerate(q)]
        e = PolylineCurve(Polyline(q + [q[0]]))
        e.Transform(xf2)
        check("edge changed", e, xf2, 0.5)

        # 3. panel in a vertical plane
        xf3 = Transform.PlaneToPlane(Plane.WorldXY, Plane(Point3d(0, 5000, 0), Vector3d.XAxis, Vector3d.ZAxis))
        p3 = src.DuplicateCurve()
        p3.Transform(xf3)
        check("vertical plane", p3, xf3, 0.01)

        # 4. symmetric panel (flat rectangle): several fits, Next cycles them
        r = NurbsSurface.CreateFromCorners(Point3d(0, 0, 0), Point3d(800, 0, 0), Point3d(800, 400, 0), Point3d(0, 400, 0))
        rid = doc.Objects.AddSurface(r)
        mk = [doc.Objects.AddPoint(Point3d(100, 100, 0))]
        pr = doc.Objects.AddCurve(PolylineCurve(Polyline([Point3d(x, y + 9000, 0) for x, y in
                                                          ((0, 0), (800, 0), (800, 400), (0, 400), (0, 0))])))
        place, meds, _ = M.transfer(doc, rid, mk, pr, tol)
        assert len(meds) == 4, meds  # turned 180°, mirrored ×2
        spots = set()
        for i in range(4):
            g = doc.Objects.FindId(place(i)[0]).Geometry.Location
            spots.add((round(g.X), round(g.Y - 9000)))
        assert spots == {(100, 100), (700, 100), (100, 300), (700, 300)}, spots
        assert len([o for o in doc.Objects if isinstance(o.Geometry, Point) and o.Geometry.Location.Y > 8000]) == 1

        # 5. main, layer of the 3D mark kept, no groups
        g = doc.Groups.Add()
        doc.Groups.AddToGroup(g, marks[0])
        li = doc.Layers.Add("Buttons", System.Drawing.Color.Red)
        a = doc.Objects.FindId(marks[0]).Attributes.Duplicate()
        a.LayerIndex = li
        doc.Objects.ModifyAttributes(marks[0], a, True)
        pid = doc.Objects.AddCurve(p)
        before = set(o.Id for o in doc.Objects)
        rs.GetObjects = lambda *a, **k: [sid] + marks
        rs.GetObject = lambda *a, **k: pid
        M.main()
        new = [o for o in doc.Objects if o.Id not in before]
        assert len(new) == 3, len(new)
        assert sorted(o.Id for o in doc.Objects.GetSelectedObjects(False, False)) == sorted(o.Id for o in new)
        pt = [o for o in new if isinstance(o.Geometry, Point)][0]
        assert pt.Attributes.LayerIndex == li and not list(pt.Attributes.GetGroupList() or []), pt.Attributes.LayerIndex
        assert pt.Geometry.Location.DistanceTo(expect(xf)[0]) < 0.01
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, rs.GetObject = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
