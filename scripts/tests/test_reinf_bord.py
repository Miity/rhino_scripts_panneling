# -*- coding: utf-8 -*-
"""Перевірка ReinfBord.bordino у Rhino 8 (потрібен RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <цей файл>
Результат пишеться в test_reinf_bord.txt поруч."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_reinf_bord.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "Seam", "CopriZip", "ReinfBord"):  # живий Rhino тримає старі версії модулів
        sys.modules.pop(m, None)
    import ReinfBord as M

    Z, tol = Vector3d.ZAxis, 0.001
    def poly(*xy):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in xy + (xy[0],)]))
    area = lambda c: AreaMassProperties.Compute(c).Area
    # прямокутник 500×300, праве ребро, H 60 → смуга 60×300 всередині
    panel = poly((0, 0), (500, 0), (500, 300), (0, 300))
    cut, seams, edge, off = M.bordino(panel, Point3d(510, 150, 0), 60, 0, 30, Z, tol)
    bb = cut.GetBoundingBox(True)
    assert cut.IsClosed and abs(area(cut) - 18000) < 1e-2 and not seams, area(cut)
    assert abs(bb.Min.X - 440) < 1e-3 and abs(bb.Max.X - 500) < 1e-3, bb
    # той самий бік, панель за годинниковою (інший напрям обходу) — теж усередину
    panel_cw = poly((0, 0), (0, 300), (500, 300), (500, 0))
    cut = M.bordino(panel_cw, Point3d(510, 150, 0), 60, 0, 30, Z, tol)[0]
    assert abs(area(cut) - 18000) < 1e-2
    # SA 10: різ 70×300, шов — лінія x=440 довжиною 300
    cut, seams, _, _ = M.bordino(panel, Point3d(510, 150, 0), 60, 10, 30, Z, tol)
    assert abs(area(cut) - 21000) < 1e-2 and len(seams) == 1 and abs(seams[0].GetLength() - 300) < 1e-3
    assert abs(seams[0].PointAtStart.X - 440) < 1e-3
    # скіс (як на фото): верх горизонтальний, праве ребро похиле → смуга обрізана верхом і низом, всередині панелі
    panel = poly((0, 0), (400, 0), (500, 300), (0, 300))
    cut = M.bordino(panel, Point3d(460, 150, 0), 60, 0, 30, Z, tol)[0]
    bb = cut.GetBoundingBox(True)
    assert cut.IsClosed and bb.Min.Y > -1e-3 and bb.Max.Y < 300 + 1e-3 and bb.Max.X < 500 + 1e-3, bb
    L = (100 ** 2 + 300 ** 2) ** 0.5
    assert abs(area(cut) - 60 * L) < 1, area(cut)  # паралелограм між горизонталями
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
