# -*- coding: utf-8 -*-
"""Перевірка JoinCorner.join у Rhino 8 (потрібен RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <цей файл>
Результат пишеться в test_join_corner.txt поруч."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_join_corner.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    import CopriZip
    import JoinCorner as M
    import importlib; importlib.reload(M)

    Z, tol = Vector3d.ZAxis, 0.001
    def poly(*p):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p + (p[0],)]))
    def area(c):
        return AreaMassProperties.Compute(c).Area

    # прямокутник 100×60: клапан W=10 зверху, шов W=20 зліва → L з виповненим кутом 20×10
    pan = poly((0, 0), (100, 0), (100, 60), (0, 60))
    top = CopriZip.flap(pan, Point3d(50, 61, 0), 10, 30, Z, tol)[0]
    left = CopriZip.flap(pan, Point3d(-1, 30, 0), 20, 30, Z, tol)[0]
    j = M.join(top, left, Point3d(-10, 65, 0), tol)
    assert not isinstance(j, str), j
    assert j.IsClosed and abs(area(j) - (1000 + 1200 + 200)) < 1e-3, area(j)
    ok, pl = j.TryGetPolyline()
    assert ok and pl.Count - 1 == 6, pl.Count  # L: 6 вершин, без зайвих на прямих
    assert M.join(left, top, Point3d(-10, 65, 0), tol).IsClosed  # порядок не важливий
    # клік на самій деталі (не між торцями і не між ребрами) — помилка
    assert isinstance(M.join(top, left, Point3d(50, 65, 0), tol), str)

    # скошений кут (трапеція) з різними W: площа = сума + виріз, зовнішній кут — перетин офсетів
    pan = poly((0, 0), (100, 0), (120, 60), (-20, 60))
    top = CopriZip.flap(pan, Point3d(50, 61, 0), 10, 30, Z, tol)[0]
    right = CopriZip.flap(pan, Point3d(111, 30, 0), 15, 30, Z, tol)[0]
    j = M.join(top, right, Point3d(128, 64, 0), tol)
    assert not isinstance(j, str), j
    assert j.IsClosed and area(j) > area(top) + area(right), (area(j), area(top) + area(right))
    # без вирізу між деталями: обидві деталі — частини результату
    assert abs(j.GetBoundingBox(True).Max.Y - 70) < 1e-6
    ok, pl = j.TryGetPolyline()
    assert ok and pl.Count - 1 == 6, pl.Count

    # як p1.3dm: кривий бік полілінією з дрібних сегментів, W 30 зверху і 20 збоку.
    # Пара «ребро + ребро» тут дає крихітне заповнення — без кліку легко взяти не ту.
    import math
    side = [(-5 * math.sin(math.pi * k / 20), 60 - 3 * k) for k in range(21)]
    pan = poly(*([(100, 60), (100, 0)] + side[::-1][:-1] + [(0, 60)]))
    top = CopriZip.flap(pan, Point3d(50, 61, 0), 30, 30, Z, tol)[0]
    left = CopriZip.flap(pan, Point3d(-6, 30, 0), 20, 30, Z, tol)[0]
    j = M.join(top, left, Point3d(-5, 75, 0), tol)
    # мінімум заповнення тут вибрав би пару ребер — тож перевіряємо, що взято саме виріз
    assert not isinstance(j, str), j
    gap = area(j) - area(top) - area(left)
    assert j.IsClosed and 300 < gap < 900, gap  # виріз ≈ 20 × 30
    assert abs(j.GetBoundingBox(True).Max.Y - 90) < 1e-6

    # деталі без спільного кута
    bottom = CopriZip.flap(poly((0, 0), (100, 0), (100, 60), (0, 60)), Point3d(50, -1, 0), 10, 30, Z, tol)[0]
    assert isinstance(M.join(bottom, top, Point3d(0, 0, 0), tol), str)
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
