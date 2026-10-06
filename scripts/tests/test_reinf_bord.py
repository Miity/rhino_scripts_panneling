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
    for m in ("ReinfCircle", "Seam", "CopriZip", "ReinfBord", "JoinCorner"):  # живий Rhino тримає старі версії модулів
        sys.modules.pop(m, None)
    import ReinfBord as M
    import JoinCorner

    Z, tol = Vector3d.ZAxis, 0.001
    def poly(*xy):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in xy + (xy[0],)]))
    area = lambda c: AreaMassProperties.Compute(c).Area
    # прямокутник 500×300, праве ребро, H 60 → смуга 60×300 всередині
    panel = poly((0, 0), (500, 0), (500, 300), (0, 300))
    cut, seams, edge, off, sq = M.bordino(panel, Point3d(510, 150, 0), 60, 0, 30, Z, tol)
    bb = cut.GetBoundingBox(True)
    assert cut.IsClosed and abs(area(cut) - 18000) < 1e-2 and not seams, area(cut)
    assert abs(bb.Min.X - 440) < 1e-3 and abs(bb.Max.X - 500) < 1e-3, bb
    # той самий бік, панель за годинниковою (інший напрям обходу) — теж усередину
    panel_cw = poly((0, 0), (0, 300), (500, 300), (500, 0))
    cut = M.bordino(panel_cw, Point3d(510, 150, 0), 60, 0, 30, Z, tol)[0]
    assert abs(area(cut) - 18000) < 1e-2
    # SA 10: різ 70×300, шов — лінія x=440 довжиною 300
    cut, seams, _, _, _ = M.bordino(panel, Point3d(510, 150, 0), 60, 10, 30, Z, tol)
    assert abs(area(cut) - 21000) < 1e-2 and len(seams) == 1 and abs(seams[0].GetLength() - 300) < 1e-3
    assert abs(seams[0].PointAtStart.X - 440) < 1e-3
    # скіс (як на фото): верх горизонтальний, праве ребро похиле → смуга обрізана верхом і низом, всередині панелі
    panel = poly((0, 0), (400, 0), (500, 300), (0, 300))
    cut = M.bordino(panel, Point3d(460, 150, 0), 60, 0, 30, Z, tol)[0]
    bb = cut.GetBoundingBox(True)
    assert cut.IsClosed and bb.Min.Y > -1e-3 and bb.Max.Y < 300 + 1e-3 and bb.Max.X < 500 + 1e-3, bb
    L = (100 ** 2 + 300 ** 2) ** 0.5
    assert abs(area(cut) - 60 * L) < 1, area(cut)  # паралелограм між горизонталями
    # підпис: на чверті ребра, з боку смуги біля внутрішньої лінії (x=440), текст росте до ребра
    rect = poly((0, 0), (500, 0), (500, 300), (0, 300))
    cut, _, edge, off, _ = M.bordino(rect, Point3d(510, 150, 0), 60, 0, 30, Z, tol)
    pl, va = M.label_place(edge, off, Z, 3)
    assert abs(pl.Origin.X - 443) < 1e-3 and abs(pl.Origin.Y - 75) < 1e-3, pl.Origin
    import Rhino
    TV = Rhino.DocObjects.TextVerticalAlignment
    assert (va == TV.Bottom) == (pl.YAxis.X > 0), (va, pl.YAxis)
    # сусіднє ребро — ламана (злам 4.8° < Angle, через 20 від кута): торець іде по панелі, не по дотичній;
    # розмітка (off_panel) — лише внутрішня лінія x=440, торці на панелі не дублюються
    panel = poly((0, 0), (500, 0), (500, 300), (480, 300), (0, 340))
    cut = M.bordino(panel, Point3d(510, 150, 0), 60, 0, 30, Z, tol)[0]
    top = 300 + 40 * 40 / 480.0
    assert cut.IsClosed and abs(cut.GetBoundingBox(True).Max.Y - top) < 1e-3, cut.GetBoundingBox(True)
    assert abs(area(cut) - (60 * 300 + 40 * 40 / 2 * 40 / 480.0)) < 1e-2, area(cut)  # + трикутник під скосом
    from ReinfCircle import off_panel
    mk = off_panel(cut, [panel], tol)
    assert len(mk) == 1 and abs(mk[0].GetLength() - top) < 1e-3, [c.GetLength() for c in mk]
    cut, seams = M.bordino(panel, Point3d(510, 150, 0), 60, 10, 30, Z, tol)[:2]  # SA: шов — теж лише лінія H
    assert len(seams) == 1 and abs(seams[0].GetLength() - top) < 1e-3, [c.GetLength() for c in seams]
    # JoinCorner: смуги на правому і верхньому ребрі перекриваються в куті → одна L-подібна деталь
    panel = poly((0, 0), (500, 0), (500, 300), (0, 300))
    a = M.bordino(panel, Point3d(510, 150, 0), 60, 0, 30, Z, tol)[0]
    b = M.bordino(panel, Point3d(250, 310, 0), 60, 0, 30, Z, tol)[0]
    j = JoinCorner.join(a, b, Point3d(490, 290, 0), tol)
    assert isinstance(j, list) and len(j) == 1 and j[0].IsClosed, j
    assert abs(area(j[0]) - (18000 + 30000 - 3600)) < 1e-2, area(j[0])
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
