# -*- coding: utf-8 -*-
"""End to end: PartPanel adds " P<n>" to the labels of parts up (Rinforzo, Bordino, TubePockets) from where they sit on
the panels; Bordino (lying over the neighbour panel) gets its own panel; markup and fascia strips untouched; a repeated
run and a renumbered panel replace the number; LayoutParts keeps it on the canvas.
Rhino 8: DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_part_panel.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_part_panel.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import LineCurve, Plane, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ZipCover", "ZipStops", "Rinforzo", "Bordino", "TubePockets", "LayoutParts", "PartPanel",
              "DotToPanelText", "PatternTextStyles", "click_undo"):
        sys.modules.pop(m, None)
    import Bordino as B
    import LayoutParts as L
    import PartPanel as PP
    import Rinforzo as R
    import TubePockets as T

    doc = Rhino.RhinoDoc.CreateHeadless(None)
    sc.doc = doc
    tol = doc.ModelAbsoluteTolerance
    rs.ViewCPlane = lambda *a, **k: Plane.WorldXY
    sc.sticky.update({R.STICKY: 60.0, R.STICKY + "_plus": 100.0, R.STICKY + "_layout": True, R.UP_KEY: 10000.0,
                      "ZipCover_angle": 30.0, "Bordino": 35.0, "Bordino_plus": 60.0, "Pettola": 100.0,
                      "Pettola_plus": 60.0})

    def rect(x0, y0, x1, y1):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))]))

    def layer(name):
        if not rs.IsLayer("Parts"):
            rs.AddLayer("Parts")
        if not rs.IsLayer("Parts::" + name):
            rs.AddLayer(name, parent="Parts")
        a = doc.CreateDefaultAttributes()
        a.LayerIndex = doc.Layers.FindByFullPath("Parts::" + name, -1)
        return a

    def panel(crv, n):
        a = layer("Panels")
        a.SetUserString("Part", n)
        return doc.Objects.AddCurve(crv, a)

    p4 = panel(rect(0, 0, 500, 300), "P4")
    p5 = panel(rect(0, -300, 500, 0), "P5")  # shares the bottom edge of P4
    # Rinforzo and Bordino on the bottom edge of P4 (the bordino part lies over P5)
    rs.GetObject = lambda *a, **k: p4
    seq = [Point3d(250, 5, 0), None]
    R.ask = lambda gp: seq.pop(0)
    R.main()
    seq2 = [Point3d(250, 5, 0), None]
    B.ask = lambda *a: seq2.pop(0)
    B.main()
    # tube pocket on the bottom edge of P5, part up
    edge = LineCurve(Point3d(0, -300, 0), Point3d(500, -300, 0))
    toward = Point3d(250, -260, 0)
    res = T.pocket(edge, toward, 300, 100, 20, True, Vector3d.ZAxis, tol)
    T.add_pocket(doc, res + (toward,), 100, 20, True, 9, layer("Pockets"), Vector3d.ZAxis, tol, False, 0,
                 Vector3d(0, 10000, 0))
    # a fascia strip lying over P4 — no place on a panel, skipped
    sa = layer("Strips")
    rs.AddObjectsToGroup([doc.Objects.AddCurve(rect(100, 100, 300, 150), sa),
                          doc.Objects.AddText(Rhino.Geometry.TextEntity.Create(
                              u"F5  l=20", Plane(Point3d(150, 120, 0), Vector3d.ZAxis), doc.DimStyles.Current, False, 0, 0),
                              sa)], rs.AddGroup())

    def labels():
        """sorted (text, up?) of all texts"""
        return sorted((o.Geometry.PlainText, o.Geometry.GetBoundingBox(True).Min.Y > 5000)
                      for o in doc.Objects if rs.IsText(o.Id))

    everything = [o.Id for o in doc.Objects]
    rs.GetObjects = lambda *a, **k: everything
    PP.main()
    first = labels()
    assert (u"R6 P4", True) in first and (u"R6", False) in first, first  # part up / markup on the panel
    assert (u"B3.5 P4", True) in first, first  # not P5, although the bordino part lies over P5
    assert first.count((u"B3.5", False)) == 2, first  # the part next to the panel and the label on it — untouched
    assert (u"T9 P5", True) in first and (u"T9", False) in first, first
    assert (u"F5  l=20", False) in first, first
    PP.main()  # again: the number is replaced, not added
    assert labels() == first, labels()
    rs.SetUserText(p4, "Part", "P7")  # renumbered panel
    PP.main()
    again = labels()
    assert (u"R6 P7", True) in again and (u"B3.5 P7", True) in again and (u"T9 P5", True) in again, again
    up = [o for o in doc.Objects if rs.IsText(o.Id) and o.Geometry.PlainText == u"R6 P7"][0]
    assert up.Attributes.GetUserString(PP.KEY) == u"P7"
    assert L.short(up).PlainText == u"R6 P7"  # the canvas keeps the panel number
    out.write("%s\nOK\n" % again)
except Exception:
    out.write(traceback.format_exc())
out.close()
