# -*- coding: utf-8 -*-
"""Check of pattern/SquishJoined (every surface squished alone, pieces joined along common sides: not joined in 3D,
one normal flipped, a lone piece) in Rhino 8:
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_squish_joined.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_squish_joined.txt"), "w")
try:
    import re
    import Rhino
    import scriptcontext as sc
    from Rhino.Geometry import (AreaMassProperties, Arc, Brep, Curve, LineCurve, Point3d, Squisher, Surface,
                                Vector3d)
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pattern"))
    sys.modules.pop("SquishJoined", None)  # live Rhino keeps old module versions
    import SquishJoined as S

    doc = Rhino.RhinoDoc.CreateHeadless(None)
    doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
    old = sc.doc
    sc.doc = doc
    try:
        lay = doc.Layers.Add("Cover", Rhino.Display.Color4f.Black.AsSystemColor())
        att = Rhino.DocObjects.ObjectAttributes()
        att.LayerIndex = lay
        # a half tube cut in two halves (common straight side) + two flat ends (common arc side, a bend of 90°)
        arc0 = Arc(Point3d(0, -800, 0), Point3d(0, 0, 600), Point3d(0, 800, 0)).ToNurbsCurve()
        arc1 = arc0.DuplicateCurve()
        arc1.Translate(Vector3d(1000, 0, 0))
        arc2 = arc0.DuplicateCurve()
        arc2.Translate(Vector3d(2000, 0, 0))
        half1 = Surface.CreateExtrusion(arc0, Vector3d(1000, 0, 0)).ToBrep()
        half2 = Surface.CreateExtrusion(arc1, Vector3d(1000, 0, 0)).ToBrep()
        poly = Brep.JoinBreps([half1, half2], 0.01)[0]  # the two halves as one polysurface
        end0 = Brep.CreatePlanarBreps(Curve.JoinCurves([arc0, LineCurve(arc0.PointAtEnd, arc0.PointAtStart)])[0], 0.01)[0]
        end2 = Brep.CreatePlanarBreps(Curve.JoinCurves([arc2, LineCurve(arc2.PointAtEnd, arc2.PointAtStart)])[0], 0.01)[0]
        end2.Flip()  # normal the other way
        lone = Brep.CreatePlanarBreps(Curve.JoinCurves([LineCurve(Point3d(5000, 0, 0), Point3d(5500, 0, 0)),
                                                        LineCurve(Point3d(5500, 0, 0), Point3d(5500, 300, 0)),
                                                        LineCurve(Point3d(5500, 300, 0), Point3d(5000, 0, 0))])[0], 0.01)[0]
        ids = []
        for name, b in (("poly", poly), ("end0", end0), ("end2", end2), ("lone", lone)):
            att.Name = name
            ids.append(doc.Objects.AddBrep(b, att))
        r = S.run(doc, ids, Point3d(0, -5000, 0))
        assert isinstance(r, tuple), r
        new, lines = r
        out.write(u"\n".join(lines) + u"\n")
        assert len(new) == 5, len(new)
        objs = [doc.Objects.FindId(i) for i in new]
        assert all(o.Attributes.LayerIndex == lay for o in objs), "layer"
        assert all(len(o.Attributes.GetGroupList() or []) == 1 for o in objs), "one group"
        assert all(Squisher.Is2dPatternSquished(o.Geometry) for o in objs), "Squish link lost"
        assert all(abs(o.Geometry.GetBoundingBox(True).Max.Z) < 0.01 for o in objs), "flat"
        num = lambda key: float(re.search(key + r"[^0-9]*([0-9.]+) mm", u"\n".join(lines)).group(1))
        assert num(u"sides 2D − 3D up to") < 1.0, "side lengths"
        assert u"3 joined" in lines[0], lines[0]  # halves + each end onto its half — no ring here
        assert u"1 pieces have no common side" in u"\n".join(lines)
        # joined pieces must not lie over each other
        outl = [Curve.JoinCurves(o.Geometry.DuplicateNakedEdgeCurves(True, False))[0] for o in objs]
        for a in range(4):
            for b in range(a + 1, 4):
                x = Curve.CreateBooleanIntersection(outl[a], outl[b], 0.01)
                ov = sum(AreaMassProperties.Compute(c).Area for c in x) if x else 0.0
                assert ov < 0.005 * AreaMassProperties.Compute(outl[a]).Area, "pieces %d, %d overlap %.0f" % (a, b, ov)
        # the two halves meet along the straight side: their outlines touch there
        h = sorted(range(4), key=lambda k: -AreaMassProperties.Compute(objs[k].Geometry).Area)[:2]
        d = min(outl[h[0]].PointAt(t).DistanceTo(outl[h[1]].PointAt(outl[h[1]].ClosestPoint(outl[h[0]].PointAt(t))[1]))
                for t in outl[h[0]].DivideByCount(200, True))
        assert d < 0.01, "halves apart %.3f" % d
        # turned like the model from Top: the tube runs along X (2000 long), end0 on the left, end2 on the right
        cx = lambda o: AreaMassProperties.Compute(o.Geometry).Centroid.X
        halves = [o for o in objs if o.Attributes.Name == "poly"]
        bb = halves[0].Geometry.GetBoundingBox(True)
        bb.Union(halves[1].Geometry.GetBoundingBox(True))
        assert abs(bb.Max.X - bb.Min.X - 2000) < 5, "not along X: %.0f" % (bb.Max.X - bb.Min.X)
        e0 = [o for o in objs if o.Attributes.Name == "end0"][0]
        e2 = [o for o in objs if o.Attributes.Name == "end2"][0]
        assert cx(e0) < bb.Min.X + 1 and cx(e2) > bb.Max.X - 1, "ends swapped / turned"
        out.write(u"OK\n")
    finally:
        sc.doc = old
        doc.Dispose()
except Exception:
    out.write(traceback.format_exc())
out.close()
