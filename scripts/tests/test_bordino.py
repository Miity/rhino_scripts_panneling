# -*- coding: utf-8 -*-
"""End to end: Bordino part next to the panel (rectangle W × edge + Plus, outside, clear of a curved edge) and its label
B<w> in the order Z<n> R<w> B<w> for every run order of ZipStops / Rinforzo / Bordino, also after a flip; the zip on the
edge itself or on a zip line inside the panel (old edge after ZipCover), a zip of the neighbouring panel on the same
line is not taken. Without a zip R<w> B<w> Pt<w> still in a row, the first of them where it was made.
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
    from Rhino.Geometry import (Arc, ArcCurve, Curve, LineCurve, Plane, Point3d, PointContainment, Polyline,
                                PolylineCurve, Transform, Vector3d)
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ZipCover", "ZipStops", "Rinforzo", "Bordino", "DotToPanelText",
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
        line = LineCurve(Point3d(0, 30, 0), Point3d(500, 30, 0))  # zip line 3 cm inside (old edge after ZipCover)
        line.Transform(turn)
        return doc, doc.Objects.AddCurve(pl), pl, doc.Objects.AddCurve(line)

    sc.sticky[Z.ANGLE] = 30.0
    sc.sticky.update({R.STICKY: 60.0, R.STICKY + "_plus": 100.0, R.STICKY + "_layout": True, R.UP_KEY: 10000.0,
                      "ZipCover_angle": 30.0, "Bordino": 35.0, "Bordino_plus": 60.0, "Pettola": 100.0,
                      "Pettola_plus": 60.0})
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
        B.ask = lambda *a: seq.pop(0)
        B.main()

    def right_of(doc, zid, rid):
        """text rid starts just after the end of text zid along its reading direction as drawn (Draw forward turns
        text near upside down 180°: its first glyph is then at the plane end), on the same line"""
        z = doc.Objects.FindId(zid).Geometry
        cs = z.CreateCurves(z.GetDimensionStyle(doc.DimStyles.FindId(z.DimensionStyleId)), True)  # as on screen
        pl = z.Plane
        read = pl.XAxis if (cs[-1].PointAtStart - cs[0].PointAtStart) * pl.XAxis > 0 else -pl.XAxis  # first → last glyph
        xf = Transform.PlaneToPlane(Plane(pl.Origin, read, Vector3d.CrossProduct(pl.ZAxis, read)), Plane.WorldXY)
        a, b = [doc.Objects.Transform(i, xf, False) for i in (zid, rid)]
        ba, bb = [doc.Objects.FindId(i).Geometry.GetBoundingBox(True) for i in (a, b)]
        for i in (a, b):
            doc.Objects.Delete(i, True)
        h = ba.Max.Y - ba.Min.Y
        gap, common = bb.Min.X - ba.Max.X, min(ba.Max.Y, bb.Max.Y) - max(ba.Min.Y, bb.Min.Y)
        return 0 <= gap < h and common > 0.5 * h

    def texts(doc):
        """{text: id}; the Bordino / Rinforzo label on the panel as B3.5 / R6, the one on the part as part B3.5 / part R6"""
        a = lambda o, k: o.Attributes.GetUserString(k)
        return {("" if a(o, "BordEdge") or a(o, "RinfLine") or not o.Geometry.PlainText.startswith(("B", "Pt", "R"))
                 else "part ") + o.Geometry.PlainText: o.Id for o in doc.Objects if rs.IsText(o.Id)}

    def run_pettola(doc, pid, click):
        rs.GetObject = lambda *a, **k: pid
        seq = [click, None]
        B.ask = lambda *a: seq.pop(0)
        B.main("Pettola")

    runs = {"zip": run_zip, "rinforzo": run_rinforzo, "bordino": run_bordino, "pettola": run_pettola}
    for deg, bulge, on in ((0, False, "edge"), (38, False, "edge"), (0, True, "edge"), (38, True, "edge"),
                           (0, False, "line"), (38, False, "line")):
        turn = Transform.Rotation(deg * 3.141592653589793 / 180, Vector3d.ZAxis, Point3d.Origin)
        click = Point3d(250, -5 - (40 if bulge else 0), 0)
        click.Transform(turn)
        zip_click = Point3d(250, 25, 0) if on == "line" else click
        zip_click.Transform(turn if on == "line" else Transform.Identity)
        for order in itertools.permutations(("zip", "rinforzo", "bordino")):
            doc, pid, pl, lid = fresh(turn, bulge)
            for name in order:
                if name == "zip":
                    run_zip(doc, lid if on == "line" else pid, zip_click)
                else:
                    runs[name](doc, pid, click)
            t = texts(doc)
            assert "Z1" in t and "R6" in t and "B3.5" in t, (deg, order, sorted(t))
            assert right_of(doc, t["Z1"], t["R6"]) and right_of(doc, t["R6"], t["B3.5"]), (deg, bulge, on, order)
            Z.flip_label(doc, t["Z1"], doc.ModelAbsoluteTolerance)
            assert right_of(doc, t["Z1"], t["R6"]) and right_of(doc, t["R6"], t["B3.5"]), (deg, bulge, order, "flip")
            # the part: rectangle 35 × (edge + 60), outside the panel, not crossing it
            edge_len = (Arc(Point3d(0, 0, 0), Point3d(250, -40, 0), Point3d(500, 0, 0)).Length if bulge else 500.0)
            assert "part B3.5" in t and not [k for k in t if "l=" in k], sorted(t)
            rect_layer = doc.Layers.FindByFullPath("Parts::Bordino", -1)
            rect = [o.Geometry for o in doc.Objects if o.Attributes.LayerIndex == rect_layer
                    and isinstance(o.Geometry, Curve)]
            assert len(rect) == 2 and all(abs(c.GetLength() - 2 * (35 + edge_len + 60)) < 1e-6 for c in rect), \
                [c.GetLength() for c in rect]
            rect.sort(key=lambda c: c.GetBoundingBox(True).Center.Y)  # in place, then the copy Up (10000) up
            shift = rect[1].GetBoundingBox(True).Center - rect[0].GetBoundingBox(True).Center
            assert (shift - Vector3d(0, 10000, 0)).Length < 1e-6, shift
            up_text = [o for o in doc.Objects if rs.IsText(o.Id) and o.Geometry.PlainText == "B3.5"
                       and o.Geometry.GetBoundingBox(True).Min.Y > 5000]
            assert len(up_text) == 1, len(up_text)
            # the label on the panel, the part next to it, its label and the copy up — one group
            g = rs.ObjectGroups(t["B3.5"])
            ids = set(str(o.Id) for o in doc.Objects if o.Attributes.LayerIndex == rect_layer)
            assert len(ids) == 5 and len(g) == 1 and set(str(i) for i in rs.ObjectsByGroup(g[0])) == ids, (len(ids), g)
            assert not Rhino.Geometry.Intersect.Intersection.CurveCurve(rect[0], pl, 0.001, 0.001).Count
            c = rect[0].GetBoundingBox(True).Center
            assert pl.Contains(c, Plane.WorldXY, 0.001) == PointContainment.Outside
            out.write("%d°, %s edge, zip on %s, %s: OK\n" % (deg, "arc" if bulge else "straight", on, " → ".join(order)))
    # bordino without a zip: label inside the panel near the edge, B alone
    doc, pid, pl, lid = fresh(Transform.Identity, False)
    run_bordino(doc, pid, Point3d(250, -5, 0))
    t = texts(doc)
    assert sorted(t) == ["B3.5", "part B3.5"], sorted(t)
    p = doc.Objects.FindId(t["B3.5"]).Geometry.GetBoundingBox(True).Center
    assert pl.Contains(p, Plane.WorldXY, 0.001) == PointContainment.Inside and p.Y < 30, p
    out.write("no zip: %s\n" % sorted(t))
    # neighbour panel below shares the bottom edge and has the zip: its number is outside this panel — not taken
    doc, pid, pl, lid = fresh(Transform.Identity, False)
    below = doc.Objects.AddCurve(PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in
                                                         ((0, 0), (0, -200), (500, -200), (500, 0), (0, 0))])))
    run_zip(doc, below, Point3d(250, 5, 0))
    run_bordino(doc, pid, Point3d(250, 5, 0))
    t = texts(doc)
    assert not right_of(doc, t["Z1"], t["B3.5"]), sorted(t)
    out.write("zip of the neighbour panel: B3.5 stays on its own\n")
    # no zip: R6 B3.5 Pt10 of one edge still in a row, the first of them (in this order) stays where it was made;
    # a rinforzo of the neighbour panel on the same line is not taken
    for deg in (0, 95):
        turn = Transform.Rotation(deg * 3.141592653589793 / 180, Vector3d.ZAxis, Point3d.Origin)
        click = Point3d(250, -5, 0)
        click.Transform(turn)
        for order in list(itertools.permutations(("rinforzo", "bordino", "pettola"))) + [("pettola", "bordino")]:
            doc, pid, pl, lid = fresh(turn, False)
            made_at = {}  # label → its origin right after it was made
            for name in order:
                runs[name](doc, pid, click)
                code = {"rinforzo": "R6", "bordino": "B3.5", "pettola": "Pt10"}[name]
                made_at[code] = doc.Objects.FindId(texts(doc)[code]).Geometry.Plane.Origin
            t = texts(doc)
            chain = [c for c in ("R6", "B3.5", "Pt10") if c in t]
            assert len(chain) == len(order) and all(right_of(doc, t[a], t[b]) for a, b in zip(chain, chain[1:])), \
                (deg, order, sorted(t))
            assert doc.Objects.FindId(t[chain[0]]).Geometry.Plane.Origin.DistanceTo(made_at[chain[0]]) < 1e-6, \
                (deg, order, "moved")
            out.write("no zip, %d°, %s: %s\n" % (deg, " → ".join(order), " ".join(chain)))
    doc, pid, pl, lid = fresh(Transform.Identity, False)
    below = doc.Objects.AddCurve(PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in
                                                         ((0, 0), (0, -200), (500, -200), (500, 0), (0, 0))])))
    run_rinforzo(doc, below, Point3d(250, 5, 0))
    run_bordino(doc, pid, Point3d(250, 5, 0))
    t = texts(doc)
    assert not right_of(doc, t["R6"], t["B3.5"]), sorted(t)
    out.write("no zip, rinforzo of the neighbour panel: B3.5 stays on its own\n")
    # pettola on the same edge as the zip, R and B: Z1 R6 B3.5 Pt10 in any run order; own layer, W 100
    for order in (("zip", "rinforzo", "bordino", "pettola"), ("pettola", "bordino", "zip", "rinforzo"),
                  ("bordino", "pettola", "rinforzo", "zip")):
        doc, pid, pl, lid = fresh(Transform.Identity, False)
        for name in order:
            runs[name](doc, pid, Point3d(250, -5, 0))
        t = texts(doc)
        chain = ["Z1", "R6", "B3.5", "Pt10"]
        assert all(right_of(doc, t[a], t[b]) for a, b in zip(chain, chain[1:])), (order, sorted(t))
        Z.flip_label(doc, t["Z1"], doc.ModelAbsoluteTolerance)
        assert all(right_of(doc, t[a], t[b]) for a, b in zip(chain, chain[1:])), (order, "flip")
        lay = doc.Layers.FindByFullPath("Parts::Pettola", -1)
        rect = [o.Geometry for o in doc.Objects if o.Attributes.LayerIndex == lay and isinstance(o.Geometry, Curve)]
        assert len(rect) == 2 and all(abs(c.GetLength() - 2 * (100 + 500 + 60)) < 1e-6 for c in rect), len(rect)
        assert "part Pt10" in t, sorted(t)
        out.write("pettola, %s: %s\n" % (" → ".join(order), " ".join(chain)))
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
