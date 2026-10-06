# -*- coding: utf-8 -*-
"""Check of SplitPanelsToMaterial in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_split_panels_to_material.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_split_panels_to_material.txt"), "w")
try:
    import Rhino
    from Rhino.Geometry import AreaMassProperties, LineCurve, Point3d, Polyline
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "cut"))
    import SplitPanelsToMaterial as M
    try:
        from importlib import reload
    except ImportError:
        pass
    reload(M)

    doc = Rhino.RhinoDoc.CreateHeadless(None)
    # material 0..1000 along Y; panel 100×1100 sticks out 100 upward
    top = LineCurve(Point3d(-500, 1000, 0), Point3d(500, 1000, 0))
    bottom = LineCurve(Point3d(-500, 0, 0), Point3d(500, 0, 0))
    panel = Polyline([Point3d(0, 0, 0), Point3d(100, 0, 0), Point3d(100, 1100, 0),
                      Point3d(0, 1100, 0), Point3d(0, 0, 0)]).ToPolylineCurve()
    pid = doc.Objects.AddCurve(panel)
    ink = doc.Objects.AddPoint(Point3d(50, 1050, 0))  # must move together with the piece
    stay = doc.Objects.AddPoint(Point3d(50, 985, 0))   # between the seam and the line — stays
    assert M.run(doc, [pid], M.material_frames([top, bottom]), 50.0, 10.0) == (1, 1)

    curves = [o.Geometry for o in doc.Objects if isinstance(o.Geometry, Rhino.Geometry.Curve)]
    closed = sorted((c for c in curves if c.IsClosed), key=lambda c: c.GetBoundingBox(True).Min.Y)
    main, off = [c.GetBoundingBox(True) for c in closed]
    assert abs(main.Max.Y - 1000) < 1e-6 and abs(main.Min.Y) < 1e-6          # along the material line
    assert abs(off.Min.Y - 1030) < 1e-6 and abs(off.Max.Y - 1150) < 1e-6     # 980 + 50 .. 1100 + 50
    assert abs(AreaMassProperties.Compute(closed[1]).Area - 100 * 120) < 1e-3
    seams = sorted(round(c.PointAtStart.Y, 6) for c in curves if not c.IsClosed)
    assert seams == [990.0, 1040.0], seams                                     # seam on both pieces
    assert abs(doc.Objects.FindId(ink).Geometry.Location.Y - 1100) < 1e-6
    assert abs(doc.Objects.FindId(stay).Geometry.Location.Y - 985) < 1e-6
    labels = sorted((o.Geometry.PlainText, round(o.Geometry.Plane.Origin.Y, 3)) for o in doc.Objects
                    if isinstance(o.Geometry, Rhino.Geometry.TextEntity))
    assert [t for t, y in labels] == ["A", "A"], labels
    assert 900 < labels[0][1] < 990 and 1040 < labels[1][1] < 1150, labels  # panel below the seam, piece above
    assert doc.Strings.GetValue("SplitPanelsToMaterial", "next_label") == "1"
    assert [M.letters(i) for i in (0, 1, 25, 26, 27)] == ["A", "B", "Z", "AA", "AB"]
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
