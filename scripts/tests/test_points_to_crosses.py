# -*- coding: utf-8 -*-
"""Check of PointsToCrosses, shape Edge (seam marks → lines to the panel edge) in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_points_to_crosses.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_points_to_crosses.txt"), "w")
try:
    import Rhino
    import System
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Circle, Point, Point3d, Polyline, PolylineCurve
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "markup"))
    sys.modules.pop("PointsToCrosses", None)  # live Rhino keeps old module versions
    import PointsToCrosses as M

    def pl(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))

    old = sc.doc, rs.SelectedObjects, rs.GetObjects, rs.GetString, rs.GetBoolean
    try:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
        sc.doc = doc
        ink = Rhino.DocObjects.ObjectAttributes()
        ink.LayerIndex = doc.Layers.Add("INK", System.Drawing.Color.Blue)
        cut = doc.Objects.AddCurve(pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)))  # cut line
        seam = doc.Objects.AddCurve(pl((10, 10), (90, 10), (90, 50), (10, 50), (10, 10)))  # seam line 1 cm inside
        hole = doc.Objects.AddCircle(Circle(Point3d(50, 30, 0), 15))  # panel hole: not a mark, not touched
        top = doc.Objects.AddCircle(Circle(Point3d(50, 50, 0), 2), ink)  # on the seam, 10 below the top edge
        g = doc.Groups.Add()
        doc.Groups.AddToGroup(g, top)
        left = doc.Objects.Add(Point(Point3d(10, 30, 0)), ink)  # point on the seam, 10 right of the left edge
        on_cut = doc.Objects.AddCircle(Circle(Point3d(100, 30, 0), 2), ink)  # already on the cut line: skipped
        everything = [cut, seam, hole, top, left, on_cut]
        rs.SelectedObjects = lambda *a, **k: everything  # window over the whole panel
        rs.GetObjects = lambda *a, **k: [cut, seam, hole, top, on_cut]  # contours: window, curve filter (seam, marks ignored)
        rs.GetString = lambda *a, **k: "Edge"
        rs.GetBoolean = lambda *a, **k: [True]  # delete originals
        M.points_to_crosses()

        lines = [o for o in doc.Objects if isinstance(o.Geometry, Rhino.Geometry.LineCurve)]
        ends = sorted((round(o.Geometry.PointAtStart.X, 6), round(o.Geometry.PointAtStart.Y, 6),
                       round(o.Geometry.PointAtEnd.X, 6), round(o.Geometry.PointAtEnd.Y, 6)) for o in lines)
        # top: (50, 50) → (50, 60) on the top edge; left: (10, 30) → (0, 30); on_cut: no line (not inward to the seam)
        assert ends == [(10, 30, 0, 30), (50, 50, 50, 60)], ends
        assert all(o.Attributes.LayerIndex == ink.LayerIndex for o in lines)  # mark's layer
        top_line = [o for o in lines if abs(o.Geometry.PointAtStart.Y - 50) < 1e-6][0]
        assert list(top_line.Attributes.GetGroupList() or []) == [g]  # stays in the mark's group
        ids = set(o.Id for o in doc.Objects)
        assert cut in ids and seam in ids and hole in ids and on_cut in ids  # contours, hole, skipped mark kept
        assert not ({top, left} & ids)  # marks replaced
        doc.Dispose()
    finally:
        sc.doc, rs.SelectedObjects, rs.GetObjects, rs.GetString, rs.GetBoolean = old
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
