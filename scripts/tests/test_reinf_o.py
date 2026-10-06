# -*- coding: utf-8 -*-
"""Перевірка ReinfO.o_shape у Rhino 8 (потрібен RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <цей файл>
Результат пишеться в test_reinf_o.txt поруч."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_reinf_o.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ReinfO"):  # живий Rhino тримає старі версії модулів
        sys.modules.pop(m, None)
    import ReinfO as M

    Z, tol, pi = Vector3d.ZAxis, 0.001, 3.14159265
    # панель 500×300, центр у правому верхньому куті (500,300), точка (450,250) → чверть кола R=√5000
    panel = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(500, 0, 0), Point3d(500, 300, 0),
                                    Point3d(0, 300, 0), Point3d(0, 0, 0)]))
    c, r = M.o_shape([panel], Point3d(500, 300, 0), Point3d(450, 250, 0), Z, tol)
    assert c is not None and c.IsClosed and abs(r - 5000 ** 0.5) < 1e-6
    assert abs(AreaMassProperties.Compute(c).Area - pi * r * r / 4) < 1e-1
    # без межі — повне коло
    c, r = M.o_shape([], Point3d(0, 0, 0), Point3d(0, -100, 0), Z, tol)
    assert c.IsClosed and abs(AreaMassProperties.Compute(c).Area - pi * 10000) < 1e-1
    assert M.o_shape([panel], Point3d(0, 0, 0), Point3d(0, 0, 0), Z, tol)[0] is None
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
