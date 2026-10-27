# -*- coding: utf-8 -*-
"""Check of cut/PreparePanelCut end to end in Rhino 8 (needs RhinoCommon): geometry goes 1:1 — a line with a spike
moved to ink keeps every point, the cut contour is the panel itself; a panel whose spike breaks the contour stops it
with the FindZigzags hint and nothing is created.
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_prepare_panel_cut.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_prepare_panel_cut.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Point3d, Polyline, PolylineCurve
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "cut"))
    sys.modules.pop("PreparePanelCut", None)  # live Rhino keeps old module versions
    import PreparePanelCut as M

    def pl(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))

    def points(c):
        return [(round(p.X, 6), round(p.Y, 6)) for p in c.TryGetPolyline()[1]]

    def run(doc, answers):
        rs.GetObjects = lambda *a, **k: answers.pop(0)
        so, sys.stdout = sys.stdout, out
        try:
            M.main()
        finally:
            sys.stdout = so
        return [[o for o in doc.Objects if doc.Layers[o.Attributes.LayerIndex].Name == n] for n in ("cut", "ink")]

    old = sc.doc, rs.GetObjects
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        # clean panel 100 × 60; an ink line with a 0.8 mm spike at its bend — moved as it is
        panel = doc.Objects.AddCurve(pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)))
        spike = pl((10, 10), (50, 10), (50.8, 10.3), (50.82, 10.2), (50.05, 10.05), (50, 50))
        ink = doc.Objects.AddCurve(spike)
        cut, inked = run(doc, [[panel], [], [ink]])
        assert len(cut) == 1 and sorted(points(cut[0].Geometry)[:-1]) == sorted(points(doc.Objects.FindId(panel).Geometry)[:-1]), points(cut[0].Geometry)
        assert len(inked) == 1 and inked[0].Id == ink and points(inked[0].Geometry) == points(spike), points(inked[0].Geometry)
        doc.Dispose()

        # a panel with a spike curling back at a corner: either stopped with the hint, or cut 1:1 with the spike
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        g = pl((0, 0), (100, 0), (100.8, 0.3), (100.82, 0.2), (100.05, 0.05), (100, 60), (0, 60), (0, 0))
        panel = doc.Objects.AddCurve(g)
        cut, inked = run(doc, [[panel], [], []])
        if cut:
            out.write("spike panel: cut %d points (panel %d)\n" % (len(points(cut[0].Geometry)), len(points(g))))
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
