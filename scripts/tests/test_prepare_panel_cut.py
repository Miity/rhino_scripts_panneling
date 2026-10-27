# -*- coding: utf-8 -*-
"""Check of cut/PreparePanelCut end to end in Rhino 8 (needs RhinoCommon): a panel with a spike at a corner and an ink
line with a spike → nothing on cut / ink has a micro segment or a spike (plotter knife).
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_prepare_panel_cut.txt next to it."""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_prepare_panel_cut.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "cut"))
    for m in ("JoinCorner", "click_undo", "PreparePanelCut"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import PreparePanelCut as M

    def pl(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))

    def bad(c):
        """Micro segments (< 0.5) or spikes (turn > 120° next to a segment < 1.5) of a polyline."""
        ok, p = c.TryGetPolyline()
        pts = list(p)
        segs = [pts[i].DistanceTo(pts[i + 1]) for i in range(len(pts) - 1)]
        out = [s for s in segs if s < 0.5]
        for i in range(1, len(pts) - 1):
            if math.degrees(Vector3d.VectorAngle(pts[i] - pts[i - 1], pts[i + 1] - pts[i])) > 120 and min(segs[i - 1], segs[i]) < 1.5:
                out.append(i)
        return out

    old = sc.doc, rs.GetObjects
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        # panel 100 × 60 with a 0.8 mm spike curling back at the corner (100, 0); an ink line with one at its bend
        panel = doc.Objects.AddCurve(pl((0, 0), (100, 0), (100.8, 0.3), (100.82, 0.2), (100.05, 0.05), (100, 60), (0, 60), (0, 0)))
        ink = doc.Objects.AddCurve(pl((10, 10), (50, 10), (50.8, 10.3), (50.82, 10.2), (50.05, 10.05), (50, 50)))
        answers = [[panel], [], [ink]]
        rs.GetObjects = lambda *a, **k: answers.pop(0)
        so, sys.stdout = sys.stdout, out
        try:
            M.main()
        finally:
            sys.stdout = so
        cut = [o for o in doc.Objects if doc.Layers[o.Attributes.LayerIndex].Name == "cut"]
        inked = [o for o in doc.Objects if doc.Layers[o.Attributes.LayerIndex].Name == "ink"]
        assert len(cut) == 1 and cut[0].Geometry.IsClosed and not bad(cut[0].Geometry), bad(cut[0].Geometry)
        assert len(inked) == 1 and inked[0].Id == ink and not bad(inked[0].Geometry), bad(inked[0].Geometry)
        doc.Dispose()
    finally:
        sc.doc, rs.GetObjects = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
