# -*- coding: utf-8 -*-
"""End to end: Rinforzo label R<w> right after the ZipStops number on the same edge, in both run orders, flip, canvas part;
a level panel and a turned one (turned text); the zip on the panel edge or on a zip line inside the strip (old edge after
ZipCover).
Rhino 8: DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_rinforzo_zip.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_rinforzo_zip.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import LineCurve, Plane, Point3d, Polyline, PolylineCurve, Transform, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ZipCover", "ZipStops", "Rinforzo", "sewing_points", "DotToPanelText", "PatternTextStyles",
              "click_undo"):
        sys.modules.pop(m, None)
    import Rinforzo as R
    import ZipStops as Z

    def fresh(turn):
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        sc.doc = doc
        pts = [Point3d(x, y, 0) for x, y in ((0, 0), (500, 0), (500, 300), (0, 300), (0, 0))]
        pl = PolylineCurve(Polyline(pts))
        pl.Transform(turn)
        line = LineCurve(Point3d(0, 30, 0), Point3d(500, 30, 0))  # zip line 3 cm inside, within the 6 cm strip
        line.Transform(turn)
        return doc, doc.Objects.AddCurve(pl), doc.Objects.AddCurve(line)

    sc.sticky[Z.ANGLE] = 30.0
    sc.sticky.update({R.STICKY: 60.0, R.STICKY + "_plus": 100.0, R.STICKY + "_layout": True, R.UP_KEY: 10000.0,
                      "ZipCover_angle": 30.0})
    rs.ViewCPlane = lambda *a, **k: Plane.WorldXY
    def run_zip(doc, pid, click):
        rs.GetObjects = lambda *a, **k: [pid]
        click = zip_click
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

    def texts(doc):
        res = {}
        for o in doc.Objects:
            if rs.IsText(o.Id):
                res[o.Geometry.PlainText] = o
        return res

    def right_of(doc, zid, rid):
        """text rid starts just after the end of text zid along its reading direction, on the same line:
        copies of both turned flat (they keep their style), world boxes compared"""
        xf = Transform.PlaneToPlane(doc.Objects.FindId(zid).Geometry.Plane, Plane.WorldXY)
        a, b = [doc.Objects.Transform(i, xf, False) for i in (zid, rid)]
        ba, bb = [doc.Objects.FindId(i).Geometry.GetBoundingBox(True) for i in (a, b)]
        for i in (a, b):
            doc.Objects.Delete(i, True)
        h = ba.Max.Y - ba.Min.Y
        gap, common = bb.Min.X - ba.Max.X, min(ba.Max.Y, bb.Max.Y) - max(ba.Min.Y, bb.Min.Y)
        return 0 <= gap < h and common > 0.5 * h, (round(gap, 2), round(h, 2), round(common, 2))

    for deg, on in ((0, "edge"), (38, "edge"), (0, "line"), (38, "line")):
        turn = Transform.Rotation(deg * 3.141592653589793 / 180, Vector3d.ZAxis, Point3d.Origin)
        click = Point3d(250, -5, 0)
        click.Transform(turn)
        zip_click = Point3d(250, -5 if on == "edge" else 25, 0)
        zip_click.Transform(turn)
        for order in ("zip first", "rinforzo first"):
            doc, pid, lid = fresh(turn)
            for run in ((run_zip, run_rinforzo) if order == "zip first" else (run_rinforzo, run_zip)):
                run(doc, lid if on == "line" and run is run_zip else pid, click)
            t = {o.Geometry.PlainText: o.Id for o in doc.Objects if rs.IsText(o.Id)}
            names = sorted(t)
            assert "Z1" in names and "R6" in names, (deg, order, names)
            # markup R6 in place on the panel; the canvas copy of the part has "Z1 R6"
            ok, d = right_of(doc, t["Z1"], t["R6"])
            assert ok, (deg, order, d)
            assert "Z1 R6" in names, (deg, order, names)
            # the canvas part got the zip: strip outline + 2 stops + the line between them, up on the canvas
            up = [o for o in doc.Objects if o.Geometry.GetBoundingBox(True).Min.Y > 5000 and rs.IsCurve(o.Id)]
            assert len(up) >= 4, (deg, order, len(up))  # + the zip line stop to stop: 500 − 2 × Trim 40
            assert any(abs(o.Geometry.GetLength() - 420) < 1e-3 for o in up), (deg, on, order, [o.Geometry.GetLength() for o in up])
            # flip the number: the label follows it
            Z.flip_label(doc, t["Z1"], doc.ModelAbsoluteTolerance)
            ok, d2 = right_of(doc, t["Z1"], t["R6"])
            assert ok, (deg, order, "flip", d2)
            out.write("%d°, zip on %s, %s: %s, gap / height / common %s\n" % (deg, on, order, names, d))
    # zip on another edge (top) — the strip on the bottom edge keeps its label where it was, the canvas part only "R6"
    for order in ("zip first", "rinforzo first"):
        doc, pid, lid = fresh(Transform.Identity)
        zip_click, click = Point3d(250, 305, 0), Point3d(250, -5, 0)
        for run in ((run_zip, run_rinforzo) if order == "zip first" else (run_rinforzo, run_zip)):
            run(doc, pid, click)
        t = {o.Geometry.PlainText: o.Id for o in doc.Objects if rs.IsText(o.Id)}
        assert sorted(t) == ["R6", "Z1"] and not right_of(doc, t["Z1"], t["R6"])[0], (order, sorted(t))
        out.write("other edge, %s: %s\n" % (order, sorted(t)))
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
