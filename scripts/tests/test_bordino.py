# -*- coding: utf-8 -*-
"""End to end: Bordino part next to the panel (rectangle W × edge + Plus, outside, clear of a curved edge) and its label
B<w> in the order Z<n> R<w> B<w> for every run order of ZipStops / Rinforzo / Bordino, also after a flip.
Rhino 8: DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_bordino.txt next to it."""
import itertools
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_bordino.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import (Arc, ArcCurve, Curve, LineCurve, Plane, Point3d, PointContainment, Transform,
                                Vector3d)
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ZipCover", "ZipStops", "Rinforzo", "Bordino", "sewing_points", "DotToPanelText",
              "PatternTextStyles", "click_undo"):
        sys.modules.pop(m, None)
    import Bordino as B
    import Rinforzo as R
    import ZipStops as Z

    def fresh(turn, bulge):
        """500 × 300 panel; bottom edge straight or an arc bulging 40 down (out of the panel)."""
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        sc.doc = doc
        bottom = (ArcCurve(Arc(Point3d(0, 0, 0), Point3d(250, -40, 0), Point3d(500, 0, 0))) if bulge
                  else LineCurve(Point3d(0, 0, 0), Point3d(500, 0, 0)))
        rest = [LineCurve(Point3d(*a), Point3d(*b)) for a, b in
                (((500, 0, 0), (500, 300, 0)), ((500, 300, 0), (0, 300, 0)), ((0, 300, 0), (0, 0, 0)))]
        pl = Curve.JoinCurves([bottom] + rest, 0.001)[0]
        pl.Transform(turn)
        return doc, doc.Objects.AddCurve(pl), pl

    sc.sticky[Z.ANGLE] = 30.0
    sc.sticky.update({R.STICKY: 60.0, R.STICKY + "_plus": 100.0, R.STICKY + "_layout": True, R.UP_KEY: 10000.0,
                      "ZipCover_angle": 30.0, B.STICKY: 35.0, B.STICKY + "_plus": 60.0})
    rs.ViewCPlane = lambda *a, **k: Plane.WorldXY

    def run_zip(doc, pid, click):
        rs.GetObjects = lambda *a, **k: [pid]
        Z.D.pts.get_number = lambda *a, **k: 10.0
        seq = [(click, "Zip", 40.0), (None, "Zip", 40.0), (None, "Zip", 40.0)]
        Z.ask_click = lambda *a, **k: seq.pop(0)
        Z.flip_stage = lambda doc: None
        Z.main()

    def run_rinforzo(doc, pid, click):
        rs.GetObject = lambda *a, **k: pid
        seq = [click, None]
        R.ask = lambda gp: seq.pop(0)
        R.main()

    def run_bordino(doc, pid, click):
        rs.GetObject = lambda *a, **k: pid
        seq = [click, None]
        B.ask = lambda gp: seq.pop(0)
        B.main()

    def right_of(doc, zid, rid):
        """text rid starts just after the end of text zid along its reading direction, on the same line"""
        xf = Transform.PlaneToPlane(doc.Objects.FindId(zid).Geometry.Plane, Plane.WorldXY)
        a, b = [doc.Objects.Transform(i, xf, False) for i in (zid, rid)]
        ba, bb = [doc.Objects.FindId(i).Geometry.GetBoundingBox(True) for i in (a, b)]
        for i in (a, b):
            doc.Objects.Delete(i, True)
        h = ba.Max.Y - ba.Min.Y
        gap, common = bb.Min.X - ba.Max.X, min(ba.Max.Y, bb.Max.Y) - max(ba.Min.Y, bb.Min.Y)
        return 0 <= gap < h and common > 0.5 * h

    def texts(doc):
        return {o.Geometry.PlainText: o.Id for o in doc.Objects if rs.IsText(o.Id)}

    runs = {"zip": run_zip, "rinforzo": run_rinforzo, "bordino": run_bordino}
    for deg, bulge in ((0, False), (38, False), (0, True), (38, True)):
        turn = Transform.Rotation(deg * 3.141592653589793 / 180, Vector3d.ZAxis, Point3d.Origin)
        click = Point3d(250, -5 - (40 if bulge else 0), 0)
        click.Transform(turn)
        for order in itertools.permutations(("zip", "rinforzo", "bordino")):
            doc, pid, pl = fresh(turn, bulge)
            for name in order:
                runs[name](doc, pid, click)
            t = texts(doc)
            assert "Z1" in t and "R6" in t and "B3.5" in t, (deg, order, sorted(t))
            assert right_of(doc, t["Z1"], t["R6"]) and right_of(doc, t["R6"], t["B3.5"]), (deg, bulge, order)
            Z.flip_label(doc, t["Z1"], doc.ModelAbsoluteTolerance)
            assert right_of(doc, t["Z1"], t["R6"]) and right_of(doc, t["R6"], t["B3.5"]), (deg, bulge, order, "flip")
            # the part: rectangle 35 × (edge + 60), outside the panel, not crossing it
            edge_len = (Arc(Point3d(0, 0, 0), Point3d(250, -40, 0), Point3d(500, 0, 0)).Length if bulge else 500.0)
            lab = [k for k in t if k.startswith("B3.5  l=")]
            assert lab == ["B3.5  l=%g" % round((edge_len + 60) / 10.0, 1)], (lab, edge_len)
            rect = [o.Geometry for o in doc.Objects if o.Attributes.LayerIndex == doc.Layers.FindByFullPath("Parts::Bordino", -1)
                    and isinstance(o.Geometry, Curve)]
            assert len(rect) == 1 and abs(rect[0].GetLength() - 2 * (35 + edge_len + 60)) < 1e-6, [c.GetLength() for c in rect]
            assert not Rhino.Geometry.Intersect.Intersection.CurveCurve(rect[0], pl, 0.001, 0.001).Count
            c = rect[0].GetBoundingBox(True).Center
            assert pl.Contains(c, Plane.WorldXY, 0.001) == PointContainment.Outside
            out.write("%d°, %s, %s: OK\n" % (deg, "arc" if bulge else "line", " → ".join(order)))
    # bordino without a zip: label inside the panel near the edge, B alone
    doc, pid, pl = fresh(Transform.Identity, False)
    run_bordino(doc, pid, Point3d(250, -5, 0))
    t = texts(doc)
    assert sorted(t) == ["B3.5", "B3.5  l=56"], sorted(t)
    p = doc.Objects.FindId(t["B3.5"]).Geometry.GetBoundingBox(True).Center
    assert pl.Contains(p, Plane.WorldXY, 0.001) == PointContainment.Inside and p.Y < 30, p
    out.write("no zip: %s\nOK\n" % sorted(t))
except Exception:
    out.write(traceback.format_exc())
out.close()
