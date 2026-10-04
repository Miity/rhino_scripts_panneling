# -*- coding: utf-8 -*-
"""Перевірка ReinfCircle.corners / piece у Rhino 8 (потрібен RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <цей файл>
Результат пишеться в test_reinf_circle.txt поруч."""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_reinf_circle.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, LineCurve, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    import ReinfCircle as M

    Z, tol, r = Vector3d.ZAxis, 0.001, 40.0
    quarter = math.pi * r * r / 4

    def area(c):
        return AreaMassProperties.Compute(c).Area

    # панель-квадрат 100: клік усередині біля кута (0,0) → чверть кола
    sq = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(100, 0, 0), Point3d(100, 100, 0),
                                 Point3d(0, 100, 0), Point3d(0, 0, 0)]))
    click = Point3d(10, 8, 0)
    c0 = min(M.corners([sq], tol), key=lambda p: p.DistanceTo(click))
    assert c0.DistanceTo(Point3d(0, 0, 0)) < 1e-6, c0
    pc = M.piece([sq], c0, click, r, Z, tol)
    assert pc and pc.IsClosed and abs(area(pc) - quarter) < 0.01, area(pc) if pc else None
    # клік за межами панелі → решта кола (3/4)
    pc = M.piece([sq], c0, Point3d(-5, -5, 0), r, Z, tol)
    assert pc and abs(area(pc) - 3 * quarter) < 0.01, area(pc) if pc else None

    # дві короткі лінії (20 < R), що сходяться в (0,0): обидва боки кута
    a = LineCurve(Point3d(0, 0, 0), Point3d(20, 0, 0))
    b = LineCurve(Point3d(0, 0, 0), Point3d(0, 20, 0))
    c0 = min(M.corners([a, b], tol), key=lambda p: p.DistanceTo(Point3d(3, 3, 0)))
    assert c0.DistanceTo(Point3d(0, 0, 0)) < 1e-6, c0
    pc = M.piece([a, b], c0, Point3d(3, 3, 0), r, Z, tol)
    assert pc and abs(area(pc) - quarter) < 0.01, area(pc) if pc else None
    pc = M.piece([a, b], c0, Point3d(-3, 3, 0), r, Z, tol)  # протилежний бік — теж чверть (лінії продовжені)
    assert pc and abs(area(pc) - quarter) < 0.01, area(pc) if pc else None

    # панель з кутом 60°: сектор = 1/6 кола
    tri = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(100, 0, 0),
                                  Point3d(50, 50 * math.sqrt(3), 0), Point3d(0, 0, 0)]))
    pc = M.piece([tri], Point3d(0, 0, 0), Point3d(10, 3, 0), r, Z, tol)
    assert pc and abs(area(pc) - math.pi * r * r / 6) < 0.01, area(pc) if pc else None
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
