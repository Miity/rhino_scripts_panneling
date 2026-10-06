# -*- coding: utf-8 -*-
"""Перевірка ReinfD.d_shape у Rhino 8 (потрібен RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <цей файл>
Результат пишеться в test_reinf_d.txt поруч."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_reinf_d.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ReinfD"):  # живий Rhino тримає старі версії модулів
        sys.modules.pop(m, None)
    import ReinfD as M

    Z, tol = Vector3d.ZAxis, 0.001
    # центр D (0,0), низ (0,-100), R 50: прямокутник 100×100 + півколо R50 вгору → y від -100 до 50
    c = M.d_shape(Point3d(0, 0, 0), Point3d(0, -100, 0), 50, Z, tol)
    assert c.IsClosed
    assert abs(AreaMassProperties.Compute(c).Area - (10000 + 3.14159265 * 2500 / 2)) < 1e-2
    bb = c.GetBoundingBox(True)
    assert abs(bb.Min.Y + 100) < 1e-6 and abs(bb.Max.Y - 50) < 1e-6 and abs(bb.Max.X - 50) < 1e-6, bb
    assert M.d_shape(Point3d(0, 0, 0), Point3d(0, 0, 0), 50, Z, tol) is None
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
