# -*- coding: utf-8 -*-
"""Labels layers: texts / TextDots of Parts::<Name> go to Labels::<Name> (same colour), numbering sees both
(old drawings keep texts in Parts), StripsFromCurves end to end.
Rhino 8: DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_labels.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_labels.txt"), "w")
try:
    import Rhino
    import System
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import LineCurve, Plane, Point3d, TextEntity
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("PatternTextStyles", "DotToPanelText", "click_undo", "ZipCover", "ZipStops", "StripsFromCurves"):
        sys.modules.pop(m, None)  # live Rhino keeps old module versions
    import ZipStops as Z
    import StripsFromCurves as F
    P = sys.modules["PatternTextStyles"]

    assert P.label_layer("Parts::Zip") == "Labels::Zip" and P.label_layer("Parts::Panels::Dots") == "Labels::Panels::Dots"
    assert P.label_layer("Labels::Zip", P.PARTS) == "Parts::Zip" and P.label_layer("INK") == "INK"

    old = sc.doc, rs.GetObjects, rs.GetReal, rs.GetPoint, P.get_number, rs.ViewCPlane
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        rs.AddLayer("Parts")
        rs.AddLayer("Zip", System.Drawing.Color.Red, parent="Parts")
        a = doc.CreateDefaultAttributes()
        a.LayerIndex = doc.Layers.FindByFullPath("Parts::Zip", -1)
        a.SetUserString(Z.KEY, "Z3")
        doc.Objects.AddText(TextEntity.Create("Z3", Plane.WorldXY, doc.DimStyles.Current, False, 0, 0), a)  # old drawing
        assert Z.next_number("Zip") == 4

        t = P.label_attrs(doc, a)
        assert doc.Layers[t.LayerIndex].FullPath == "Labels::Zip" and t.GetUserString(Z.KEY) == "Z3"
        assert rs.LayerColor("Labels::Zip").ToArgb() == System.Drawing.Color.Red.ToArgb()
        t.SetUserString(Z.KEY, "Z7")
        doc.Objects.AddText(TextEntity.Create("Z7", Plane.WorldXY, doc.DimStyles.Current, False, 0, 0), t)
        assert Z.next_number("Zip") == 8  # new texts in Labels counted too
        assert len(P.by_layer("Labels::Zip")) == len(P.by_layer("Parts::Zip")) == 2
        ink = doc.CreateDefaultAttributes()
        ink.LayerIndex = doc.Layers.Add("INK", System.Drawing.Color.Blue)
        assert P.label_attrs(doc, ink).LayerIndex == ink.LayerIndex  # not a Parts layer — as it is

        line = doc.Objects.AddCurve(LineCurve(Point3d(0, 0, 0), Point3d(300, 0, 0)))
        rs.GetObjects = lambda *x, **k: [line]
        P.get_number = lambda *x, **k: 50.0
        rs.GetReal = lambda *x, **k: 0.0
        rs.GetPoint = lambda *x, **k: Point3d(0, -100, 0)
        rs.ViewCPlane = lambda *x, **k: Plane.WorldXY  # headless: no view
        F.main()
        got = sorted((type(o.Geometry).__name__, doc.Layers[o.Attributes.LayerIndex].FullPath) for o in doc.Objects
                     if doc.Layers[o.Attributes.LayerIndex].FullPath.endswith("Strips"))
        assert got == [("PolylineCurve", "Parts::Strips"), ("TextDot", "Labels::Strips"), ("TextEntity", "Labels::Strips")], got
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects, rs.GetReal, rs.GetPoint, P.get_number, rs.ViewCPlane = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
