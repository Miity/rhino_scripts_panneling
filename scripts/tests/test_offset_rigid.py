# -*- coding: utf-8 -*-
"""Перевірка OffsetRigid.shift у Rhino 8 (потрібен RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <цей файл>
Результат пишеться в test_offset_rigid.txt поруч."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_offset_rigid.txt"), "w")
try:
    from Rhino.Geometry import Arc, ArcCurve, Plane, Point3d, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "curves"))
    import OffsetRigid as M

    Z = Vector3d.ZAxis
    # верхня півдуга R=50 з центром у (0,0): вершина (0,50), нормаль там — вісь Y
    arc = ArcCurve(Arc(Plane.WorldXY, 50.0, 3.141592653589793))
    ok, t = arc.ClosestPoint(Point3d(0, 50, 0))
    up = M.shift(arc, t, Z, Point3d(3, 80, 0), 20.0)      # клік зовні → +Y
    down = M.shift(arc, t, Z, Point3d(-3, 10, 0), 20.0)   # клік усередині → −Y
    assert (up - Vector3d(0, 20, 0)).Length < 1e-9, up
    assert (down - Vector3d(0, -20, 0)).Length < 1e-9, down
    # копія тієї ж форми: радіус не змінився
    c = arc.DuplicateCurve(); c.Translate(up)
    ok, a = c.TryGetArc()
    assert ok and abs(a.Radius - 50.0) < 1e-9, a.Radius
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
