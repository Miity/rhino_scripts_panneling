# -*- coding: utf-8 -*-
"""Перевірка TubePockets.pocket у Rhino 8 (потрібен RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <цей файл>
Результат пишеться в test_tube_pockets.txt поруч."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_tube_pockets.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, LineCurve, Point3d, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    import TubePockets as M

    Z, tol = Vector3d.ZAxis, 0.001
    line = LineCurve(Point3d(0, 0, 0), Point3d(1000, 0, 0))
    # W 600 по центру, H 100 вгору, Trim 50, SA 10 вниз: трапеція (600+500)/2·100 + 600·10
    outline, seg, mark = M.pocket(line, Point3d(300, 40, 0), 600, 100, 50, 10, True, Z, tol)
    assert outline.IsClosed
    assert abs(AreaMassProperties.Compute(outline).Area - 61000) < 1e-3
    assert abs(seg.PointAtStart.X - 200) < 1e-6 and abs(seg.PointAtEnd.X - 800) < 1e-6
    assert abs(mark.PointAtStart.X - 500) < 1e-6 and abs(mark.PointAtStart.Y + 10) < 1e-6
    assert abs(mark.PointAtEnd.Y - 10) < 1e-6  # H/10 у карман
    bb = outline.GetBoundingBox(True)
    assert abs(bb.Min.Y + 10) < 1e-6 and abs(bb.Max.Y - 100) < 1e-6
    # W 0 — уся лінія; клік знизу → карман вниз, без SA
    outline, seg, mark = M.pocket(line, Point3d(300, -40, 0), 0, 100, 50, 0, False, Z, tol)
    assert abs(AreaMassProperties.Compute(outline).Area - 95000) < 1e-3 and mark is None
    assert outline.GetBoundingBox(True).Min.Y < -99
    # Trim завеликий → причина рядком
    assert not isinstance(M.pocket(line, Point3d(0, 40, 0), 80, 100, 50, 10, False, Z, tol), tuple)
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
