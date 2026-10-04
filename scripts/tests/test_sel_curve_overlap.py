# -*- coding: utf-8 -*-
"""Перевірка sel_curve_overlap.shorter_overlaps у Rhino 8 (потрібен RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <цей файл>
Результат пишеться в test_sel_curve_overlap.txt поруч."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_sel_curve_overlap.txt"), "w")
try:
    from Rhino.Geometry import LineCurve, Point3d, Polyline, PolylineCurve
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "cut"))
    import sel_curve_overlap as M

    def pl(*pts):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in pts]))

    crvs = [
        LineCurve(Point3d(0, 0, 0), Point3d(1000, 0, 0)),     # 0 довга лінія
        pl((0, 0), (300, 0.002), (1000, 0)),                  # 1 та сама, вершина зсунута на 0.002 (як у p1.3dm)
        LineCurve(Point3d(200, 0, 0), Point3d(400, 0, 0)),    # 2 коротша під довгою
        LineCurve(Point3d(0, 0, 0), Point3d(1000, 0, 0)),     # 3 точний дублікат 0
        LineCurve(Point3d(0, 1, 0), Point3d(1000, 1, 0)),     # 4 паралельна на 1 мм — окрема
        LineCurve(Point3d(500, -50, 0), Point3d(500, 50, 0)), # 5 перетин — окрема
        pl((0, 100), (50, 100.08), (100, 100)),               # 6 і 7: дві апроксимації однієї кривої, 0.08 мм
        pl((0, 100), (25, 100.03), (75, 100.03), (100, 100)),
    ]
    hits = M.shorter_overlaps(crvs, 0.001, M.OVERLAP_TOL_MM, M.MIN_OVERLAP_MM)
    # з {0,1,3} лишається одна (найдовша 1), з {6,7} — одна; 4 і 5 не чіпаємо
    assert 4 not in hits and 5 not in hits, hits
    assert 2 in hits, hits
    assert len(hits & {0, 1, 3}) == 2, hits
    assert len(hits & {6, 7}) == 1, hits
    out.write("OK %s\n" % sorted(hits))
except Exception:
    out.write(traceback.format_exc())
out.close()
