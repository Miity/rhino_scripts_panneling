# -*- coding: utf-8 -*-
"""Перевірка TubePockets.pocket у Rhino 8 (потрібен RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <цей файл>
Результат пишеться в test_tube_pockets.txt поруч."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_tube_pockets.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, LineCurve, Point3d, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("CopriZip", "Seam", "OffsetRigid", "TubePockets"):  # живий Rhino тримає старі версії модулів
        sys.modules.pop(m, None)
    import TubePockets as M

    Z, tol = Vector3d.ZAxis, 0.001
    line = LineCurve(Point3d(0, 0, 0), Point3d(1000, 0, 0))
    # W 600 по центру, H 100 вгору, Trim 50, SA 10 вниз: трапеція (600+500)/2·100 + 600·10
    outline, seg, mark, folds, simple = M.pocket(line, Point3d(300, 40, 0), 600, 100, 50, 10, True, Z, tol)
    assert outline.IsClosed
    assert abs(AreaMassProperties.Compute(outline).Area - 61000) < 1e-3
    assert abs(seg.PointAtStart.X - 200) < 1e-6 and abs(seg.PointAtEnd.X - 800) < 1e-6
    assert abs(mark.PointAtStart.X - 500) < 1e-6 and abs(mark.PointAtStart.Y + 10) < 1e-6
    assert abs(mark.PointAtEnd.Y - 10) < 1e-6  # H/10 у карман
    bb = outline.GetBoundingBox(True)
    assert abs(bb.Min.Y + 10) < 1e-6 and abs(bb.Max.Y - 100) < 1e-6
    # W 0 — уся лінія; клік знизу → карман вниз, без SA
    outline, seg, mark, folds, simple = M.pocket(line, Point3d(300, -40, 0), 0, 100, 50, 0, False, Z, tol)
    assert abs(AreaMassProperties.Compute(outline).Area - 95000) < 1e-3 and mark is None
    assert outline.GetBoundingBox(True).Min.Y < -99
    # Trim завеликий → причина рядком
    assert not isinstance(M.pocket(line, Point3d(0, 40, 0), 80, 100, 50, 10, False, Z, tol), tuple)
    # панель 1000×500: клік біля верхнього ребра → карман униз (всередину), SA вгору; обидва напрямки обходу
    from Rhino.Geometry import Polyline, PolylineCurve
    pts = [Point3d(0, 0, 0), Point3d(1000, 0, 0), Point3d(1000, 500, 0), Point3d(0, 500, 0), Point3d(0, 0, 0)]
    for order in (pts, pts[::-1]):
        panel = PolylineCurve(Polyline(order))
        edge = M.pick_edge(panel, Point3d(400, 520, 0), 30, tol)[3]
        assert abs(edge.GetLength() - 1000) < 1e-6 and abs(edge.PointAtStart.Y - 500) < 1e-6
        outline, seg, mark, folds, simple = M.pocket(edge, M.inward(panel, edge, Z), 600, 100, 50, 10, True, Z, tol)
        bb = outline.GetBoundingBox(True)
        assert abs(bb.Min.Y - 400) < 1e-6 and abs(bb.Max.Y - 510) < 1e-6, bb
        assert abs(AreaMassProperties.Compute(outline).Area - 61000) < 1e-3
    # UpdateTubePockets.read_pocket: карман у документі → параметри; без UserText — з геометрії
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    sys.modules.pop("UpdateTubePockets", None)
    import UpdateTubePockets as U
    line = LineCurve(Point3d(0, 0, 0), Point3d(1000, 0, 0))
    toward = Point3d(300, 40, 0)
    res = M.pocket(line, toward, 600, 100, 50, 10, True, Z, tol) + (toward,)
    before = set(rs.AllObjects() or [])
    M.add_pocket(sc.doc, res, 100, 50, 10, True, 7, sc.doc.CreateDefaultAttributes(), Z, tol)
    ids = [o for o in rs.AllObjects() if o not in before]
    try:
        for legacy in (False, True):
            if legacy:
                for o in ids:
                    for k in U.KEYS:
                        rs.SetUserText(o, "TP_" + k, None)
            p = U.read_pocket(ids, tol)
            assert p["n"] == 7 and p["H"] == 100 and abs(p["Trim"] - 50) < 1e-6 and abs(p["SA"] - 10) < 1e-6, p
            assert p["Notch"] == 1 and abs(p["seg"].GetLength() - 600) < 1e-6
            r = M.pocket(p["seg"], p["toward"], 0, 100, 30, 10, True, Z, tol)  # Trim 50 → 30
            assert abs(AreaMassProperties.Compute(r[0]).Area - 63000) < 1e-3
    finally:
        rs.DeleteObjects(ids)
    # Hem: лінії підгину в підшарі <шар>::Fold, у групі; Update бере шар контуру і Hem з UserText
    res = M.pocket(line, toward, 600, 100, 0, 10, False, Z, tol, False, 20) + (toward,)
    attrs = sc.doc.CreateDefaultAttributes()
    before = set(rs.AllObjects() or [])
    M.add_pocket(sc.doc, res, 100, 0, 10, False, 8, attrs, Z, tol, False, 20)
    ids = [o for o in rs.AllObjects() if o not in before]
    base = sc.doc.Layers[attrs.LayerIndex].FullPath
    try:
        folds = [o for o in ids if rs.ObjectLayer(o) == base + "::Fold"]
        assert len(folds) == 2 and all(rs.ObjectGroups(o) == rs.ObjectGroups(ids[0]) for o in ids)
        p = U.read_pocket(list(reversed(ids)), tol)
        assert p["Hem"] == 20 and p["attrs"].LayerIndex == attrs.LayerIndex, p
    finally:
        rs.DeleteObjects(ids)
        rs.DeleteLayer(base + "::Fold")
    # розмітка на місці + повна деталь на up: простий контур = трапеція 55000 без SA; Update бачить пару
    up = Vector3d(0, 10000, 0)
    res = M.pocket(line, toward, 600, 100, 50, 10, True, Z, tol, False, 20)
    assert abs(AreaMassProperties.Compute(res[4]).Area - 55000) < 1e-3
    before = set(rs.AllObjects() or [])
    M.add_pocket(sc.doc, res + (toward,), 100, 50, 10, True, 9, attrs, Z, tol, False, 20, up)
    ids = [o for o in rs.AllObjects() if o not in before]
    try:
        markup = [o for o in ids if rs.GetUserText(o, "TP_Markup")]
        full = [o for o in ids if o not in markup]
        assert len(markup) == 2 and rs.ObjectGroups(markup[0]) == rs.ObjectGroups(markup[1])
        assert all(rs.BoundingBox(o)[0].Y < 1000 for o in markup)
        assert all(rs.BoundingBox(o)[0].Y > 9000 for o in full) and len(full) == 6  # контур, 2 підгини, шов, мітка, текст
        assert set(U.tagged(markup[0], "9", False)) == set(o for o in full if rs.ObjectLayer(o) == rs.ObjectLayer(markup[0]))
        p = U.read_pocket(rs.ObjectsByGroup(rs.ObjectGroups(full[0])[0]), tol)
        assert p["up"] == up and set(p["markup"]) == set(markup) and p["n"] == 9, p
        seg = p["seg"].DuplicateCurve()
        seg.Translate(-up)
        assert abs(seg.PointAtStart.Y) < 1e-6  # лінія шва повертається на місце розмітки
    finally:
        rs.DeleteObjects(ids)
        if rs.IsLayer(base + "::Fold"):
            rs.DeleteLayer(base + "::Fold")
    # Rigid: дуга R1000 (45°..135°), карман до центру H 100: жорсткий — та сама довжина, центр зсунутий рівно на H;
    # стандартний — дуга R900 (коротша в 0.9)
    from Rhino.Geometry import Arc, ArcCurve
    import math
    arc = ArcCurve(Arc(Point3d(707.1068, 707.1068, 0), Point3d(0, 1000, 0), Point3d(-707.1068, 707.1068, 0)))
    rig = M.pocket_side(arc, Point3d(0, 0, 0), 100, Z, tol, True)
    std = M.pocket_side(arc, Point3d(0, 0, 0), 100, Z, tol, False)
    assert abs(rig.GetLength() - arc.GetLength()) < 1e-3
    assert abs(rig.PointAt(rig.Domain.Mid).Y - 900) < 1e-3, rig.PointAt(rig.Domain.Mid)
    assert abs(std.GetLength() - 0.9 * arc.GetLength()) < 1e-2
    res = M.pocket(arc, Point3d(0, 0, 0), 0, 100, 50, 10, True, Z, tol, True)
    assert isinstance(res, tuple) and res[0].IsClosed, res
    # Hem 20: прямокутний карман (Trim 0) 600×100 + SA 10 → торці назовні на 20: 640×110, дві лінії підгину x=200 / 800
    outline, seg, mark, folds, simple = M.pocket(line, Point3d(300, 40, 0), 600, 100, 0, 10, False, Z, tol, False, 20)
    assert abs(AreaMassProperties.Compute(outline).Area - 70400) < 1e-3
    assert len(folds) == 2 and sorted(round(f.PointAtStart.X) for f in folds) == [200, 800]
    assert abs(folds[0].GetLength() - 110) < 1e-6
    # з Trim 50 (косий торець): низ SA подовжується до x=180, верх — далі від краю; контур замкнений
    outline, seg, mark, folds, simple = M.pocket(line, Point3d(300, 40, 0), 600, 100, 50, 10, False, Z, tol, False, 20)
    bb = outline.GetBoundingBox(True)
    assert outline.IsClosed and abs(bb.Min.X - 180) < 1e-6 and abs(bb.Max.X - 820) < 1e-6, bb
    assert AreaMassProperties.Compute(outline).Area > 61000 + 2 * 20 * 110
    # Hem на дузі з Rigid
    res = M.pocket(arc, Point3d(0, 0, 0), 0, 100, 50, 10, True, Z, tol, True, 20)
    assert isinstance(res, tuple) and res[0].IsClosed and len(res[3]) == 2, res
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
