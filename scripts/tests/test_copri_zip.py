# -*- coding: utf-8 -*-
"""Перевірка CopriZip.flap у Rhino 8 (потрібен RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <цей файл>
Результат пишеться в test_copri_zip.txt поруч."""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_copri_zip.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    import CopriZip as M
    import importlib; importlib.reload(M)  # живий Rhino кешує модуль між запусками

    Z, tol = Vector3d.ZAxis, 0.001
    def poly(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p + (p[0],)]))
    def area(c):
        return AreaMassProperties.Compute(c).Area

    # трапеція, боки розходяться вгору (як центральна панель): верх 140, сусіди по (±20, 60)
    # клапан W=10 над верхом: кінці на продовженні боків → основи 140 і 146.667
    for pan in (poly((0, 0), (100, 0), (120, 60), (-20, 60)), poly((-20, 60), (120, 60), (100, 0), (0, 0))):
        crv, edge, off, sq = M.flap(pan, Point3d(50, 61, 0), 10, 30, Z, tol)
        assert crv.IsClosed and sq == 0 and crv.TryGetPolyline()[0]
        assert abs(area(crv) - (140 + 146.6667) / 2 * 10) < 1e-2, area(crv)
        assert abs(edge.GetLength() - 140) < 1e-6 and crv.GetBoundingBox(True).Max.Y > 69.99
        # Up=Yes: розмітка — клапан без ребра панелі (одна відкрита крива)
        import ReinfCircle
        mk = ReinfCircle.off_panel(crv, [pan], tol)
        assert len(mk) == 1 and not mk[0].IsClosed and abs(mk[0].GetLength() - (crv.GetLength() - 140)) < 1e-6

    # кривий верх полілінією з 20 дрібних сегментів (зломи < Angle) — ребро від кута до кута
    arc = [(100 - 5 * k, 50 - 10 * math.sin(math.pi * k / 20)) for k in range(21)]
    pan = poly(*([(0, 0), (100, 0)] + arc))
    crv, edge, off, sq = M.flap(pan, Point3d(50, 45, 0), 10, 30, Z, tol)
    assert abs(edge.PointAtStart.X - 100) < 1e-9 and abs(edge.PointAtEnd.X) < 1e-9
    assert crv.IsClosed and crv.TryGetPolyline()[0] and sq == 0
    assert 900 < area(crv) < 1100, area(crv)  # ≈ довжина ребра × W

    # панель — PolyCurve з дугою (як p1.3dm): ребро-лінія вгорі, сусід — дуга
    from Rhino.Geometry import Arc, ArcCurve, Curve, LineCurve
    pc = Curve.JoinCurves([LineCurve(Point3d(0, 0, 0), Point3d(100, 0, 0)),
                           ArcCurve(Arc(Point3d(100, 0, 0), Point3d(110, 30, 0), Point3d(100, 60, 0))),
                           LineCurve(Point3d(100, 60, 0), Point3d(0, 60, 0)),
                           LineCurve(Point3d(0, 60, 0), Point3d(0, 0, 0))], tol)[0]
    crv, edge, off, sq = M.flap(pc, Point3d(50, 61, 0), 10, 30, Z, tol)
    assert crv.IsClosed and abs(edge.GetLength() - 100) < 1e-6, edge.GetLength()
    assert crv.GetBoundingBox(True).Max.Y > 69.99 and 900 < area(crv) < 1200, area(crv)

    # «майже замкнена» полілінія з DXF (розрив 0.1 між кінцями) — замикається сама
    gap = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(100, 0, 0), Point3d(120, 60, 0),
                                  Point3d(-20, 60, 0), Point3d(0, 0.1, 0)]))
    crv, edge, off, sq = M.flap(gap, Point3d(50, 61, 0), 10, 30, Z, tol)
    assert crv.IsClosed and abs(edge.GetLength() - 140) < 1e-6

    # гострий сусід (< 30° від ребра) → перпендикулярний кінець
    pan = poly((0, 0), (100, 0), (100, 50), (0, 50), (-80, 10))
    crv, edge, off, sq = M.flap(pan, Point3d(50, 51, 0), 10, 20, Z, tol)
    assert sq == 1 and abs(area(crv) - 1000) < 1e-3, (sq, area(crv))

    # боки сходяться вгору, W завелике → продовження перетнулись → помилка-рядок
    assert not isinstance(M.flap(poly((0, 0), (100, 0), (55, 40), (45, 40)), Point3d(50, 41, 0), 50, 30, Z, tol), tuple)
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
