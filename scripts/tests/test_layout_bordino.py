# -*- coding: utf-8 -*-
"""End to end: real Bordino parts on a panel turned 30° (edges at 30° and 120°) + a Pettola; LayoutBordino on the whole
selection → only the two bordini, copies along X reading left to right, stacked touching down from the click, longest
first; a second run skips them, LayoutParts skips them too.
Rhino 8: DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_layout_bordino.txt next to it."""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_layout_bordino.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Plane, Point3d, Polyline, PolylineCurve, TextEntity, Transform, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ZipCover", "ZipStops", "Bordino", "LayoutParts", "LayoutBordino", "PatternTextStyles",
              "click_undo"):
        sys.modules.pop(m, None)
    import Bordino as B
    import LayoutBordino as L
    import LayoutParts as LP

    doc = Rhino.RhinoDoc.CreateHeadless(None)
    sc.doc = doc
    sc.sticky.update({"Parts_up": 10000.0, "ZipCover_angle": 30.0, "Bordino": 35.0, "Bordino_plus": 60.0,
                      "Pettola": 100.0, "Pettola_plus": 60.0})
    rs.ViewCPlane = lambda *a, **k: Plane.WorldXY
    turn = Transform.Rotation(math.radians(30), Vector3d.ZAxis, Point3d.Origin)
    pl = PolylineCurve(Polyline([Point3d(*p) for p in ((0, 0, 0), (500, 0, 0), (500, 300, 0), (0, 300, 0), (0, 0, 0))]))
    pl.Transform(turn)
    pid = doc.Objects.AddCurve(pl)

    def click(x, y):
        p = Point3d(x, y, 0)
        p.Transform(turn)
        return p

    def make(kind, c):
        rs.GetObject = lambda *a, **k: pid
        seq = [c, None]
        B.ask = lambda *a: seq.pop(0)
        B.main(kind)

    make("Bordino", click(250, 1))     # bottom edge 500 → strip 560 × 35 at 30°
    make("Bordino", click(499, 150))   # right edge 300 → strip 360 × 35 at 120°
    make("Pettola", click(250, 299))   # not a bordino → not taken

    every = [o.Id for o in doc.Objects]
    rs.GetObjects = lambda *a, **k: every
    rs.GetPoint = lambda *a, **k: Point3d(0, -5000, 0)
    L.main()
    copies = [o for o in doc.Objects if o.Attributes.GetUserString(LP.KEY)]
    lay = set(doc.Layers[o.Attributes.LayerIndex].FullPath for o in copies)
    assert lay == {"Parts::Bordino::Layout"}, lay
    rects = sorted([o.Geometry for o in copies if isinstance(o.Geometry, Rhino.Geometry.Curve)],
                   key=lambda c: -c.GetBoundingBox(True).Max.Y)
    texts = [o.Geometry for o in copies if isinstance(o.Geometry, TextEntity)]
    assert len(rects) == 2 and len(texts) == 2, (len(rects), len(texts))
    tol = 1e-6
    y = -5000.0
    for c, length in zip(rects, (560.0, 360.0)):  # longest first, touching
        bb = c.GetBoundingBox(True)
        assert abs(bb.Min.X) < tol and abs(bb.Max.Y - y) < tol, (bb.Min, bb.Max, y)
        assert abs(bb.Max.X - bb.Min.X - length) < tol and abs(bb.Max.Y - bb.Min.Y - 35.0) < tol, (bb.Min, bb.Max)
        y -= 35.0
    for t in texts:
        assert t.PlainText == "B3.5", t.PlainText
        assert t.Plane.XAxis.X > 1 - tol, t.Plane.XAxis  # along X, left to right
        o = t.Plane.Origin
        assert any(r.GetBoundingBox(True).Contains(o) for r in rects), o  # inside its strip
    groups = set(tuple(o.Attributes.GetGroupList() or []) for o in copies)
    assert len(groups) == 2, groups  # each strip with its label
    n = len(copies)
    L.main()  # again: already laid out
    assert len([o for o in doc.Objects if o.Attributes.GetUserString(LP.KEY)]) == n
    new, skipped = LP.layout(doc, every, 10.0, Plane.WorldXY, Point3d(0, -8000, 0), 20.0)
    assert skipped == 2, skipped  # LayoutParts: the bordini are already on the canvas
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
