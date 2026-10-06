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
    # панель 500×300, центр у правому верхньому куті (500,300), клік (450,250), Plus 0 → чверть кола R=√5000
    panel = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(500, 0, 0), Point3d(500, 300, 0),
                                    Point3d(0, 300, 0), Point3d(0, 0, 0)]))
    c, r = M.o_shape([panel], Point3d(500, 300, 0), Point3d(450, 250, 0), 0, Z, tol)
    assert c is not None and c.IsClosed and abs(r - 5000 ** 0.5) < 1e-6
    assert abs(AreaMassProperties.Compute(c).Area - pi * r * r / 4) < 1e-1
    # клік на самому краї панелі (400,300) + Plus 50 → R=150, чверть кола всередині, не зовні
    c, r = M.o_shape([panel], Point3d(500, 300, 0), Point3d(400, 300, 0), 50, Z, tol)
    assert abs(r - 150) < 1e-6 and abs(AreaMassProperties.Compute(c).Area - pi * 150 * 150 / 4) < 1e-1
    bb = c.GetBoundingBox(True)
    assert bb.Max.Y < 300 + 1e-3 and bb.Max.X < 500 + 1e-3, bb
    # SA 10 назовні: чверть кола R150 → офсет більший, з усіх боків на 10 (bbox +10)
    o = M.outward(c, 10, Z, tol)
    ob = o.GetBoundingBox(True)
    assert o.IsClosed and abs(ob.Max.Y - 310) < 1e-3 and abs(ob.Max.X - 510) < 1e-3, ob
    assert AreaMassProperties.Compute(o).Area > AreaMassProperties.Compute(c).Area
    # без межі — повне коло R = 100 + 50
    c, r = M.o_shape([], Point3d(0, 0, 0), Point3d(0, -100, 0), 50, Z, tol)
    assert c.IsClosed and abs(AreaMassProperties.Compute(c).Area - pi * 150 * 150) < 1e-1
    assert M.o_shape([panel], Point3d(0, 0, 0), Point3d(0, 0, 0), 50, Z, tol)[0] is None
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
