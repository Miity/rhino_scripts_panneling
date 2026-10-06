# -*- coding: utf-8 -*-
"""Check of Seam (part via ZipCover.flap, label, seam points) in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_seam.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_seam.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    import Seam as M

    import importlib; importlib.reload(M)  # live Rhino caches the module between runs
    import ZipCover
    Z, tol = Vector3d.ZAxis, 0.001
    # panel 100×60, click near the top edge → part 100×10 outside the panel (y 60..70)
    pan = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(100, 0, 0), Point3d(100, 60, 0),
                                  Point3d(0, 60, 0), Point3d(0, 0, 0)]))
    crv, edge, off, sq = ZipCover.flap(pan, Point3d(50, 61, 0), 10, 30, Z, tol)
    assert abs(AreaMassProperties.Compute(crv).Area - 1000) < 1e-3
    bb = crv.GetBoundingBox(True)
    assert abs(bb.Min.Y - 60) < 1e-6 and abs(bb.Max.Y - 70) < 1e-6, (bb.Min, bb.Max)
    pl = M.label_frame(edge, off, Z)
    assert 60 < pl.Origin.Y < 70, pl.Origin  # label inside the part
    assert M.sewing_lengths(100, 20) == [10, 30, 50, 70, 90]  # sewing_points logic is pulled in
    # seam points: edge copy + points, all in the attrs layer (Parts::Seam), not in the input line's layer
    import Rhino
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    import System
    seam = doc.Layers.Add("Seam", System.Drawing.Color.Black)
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = seam
    ids = M.add_sewing_points(doc, edge, 20, attrs)  # on the panel edge (y = 60)
    assert len(ids) == 6, len(ids)  # copy + 5 points (10, 30, 50, 70, 90)
    assert all(doc.Objects.FindId(i).Attributes.LayerIndex == seam for i in ids)
    assert all(abs(doc.Objects.FindId(i).Geometry.Location.Y - 60) < 1e-6 for i in ids[1:])
    doc.Dispose()
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
