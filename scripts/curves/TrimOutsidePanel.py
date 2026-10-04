# -*- coding: utf-8 -*-
"""Обрізає 2D-криві по замкненому контуру панелі: все, що поза панеллю, видаляється.
Шматки, що лежать точно на контурі панелі, залишаються."""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

Outside = Rhino.Geometry.PointContainment.Outside


def trim_to_panel(crv, panel, plane, tol):
    """Повертає список шматків усередині панелі (або None, якщо крива вся всередині)."""
    params = []
    for e in Rhino.Geometry.Intersect.Intersection.CurveCurve(crv, panel, tol, tol) or []:
        params.append(e.ParameterA)
        if e.IsOverlap:
            params.append(e.OverlapA.T1)
    pieces = crv.Split(params) if params else None
    if not pieces:
        pieces = [crv]
    inside = [p for p in pieces
              if panel.Contains(p.PointAtNormalizedLength(0.5), plane, tol) != Outside]
    if len(inside) == len(pieces) and len(pieces) == 1:
        return None
    return inside


def main():
    ids = rs.GetObjects("Виберіть криві для обрізки", rs.filter.curve, preselect=True)
    if not ids:
        return
    panel_id = rs.GetObject("Виберіть панель (замкнений контур)", rs.filter.curve)
    if not panel_id:
        return
    panel = rs.coercecurve(panel_id)
    ok, plane = panel.TryGetPlane()
    if not (panel.IsClosed and ok):
        print("Панель має бути замкненою пласкою кривою")
        return
    tol = sc.doc.ModelAbsoluteTolerance

    rs.EnableRedraw(False)
    changed = 0
    for oid in ids:
        if oid == panel_id:
            continue
        inside = trim_to_panel(rs.coercecurve(oid), panel, plane, tol)
        if inside is None:
            continue
        attrs = sc.doc.Objects.FindId(oid).Attributes  # шар, колір, тип лінії
        for p in inside:
            sc.doc.Objects.AddCurve(p, attrs)
        sc.doc.Objects.Delete(oid, True)
        changed += 1
    rs.EnableRedraw(True)
    print("Обрізано / видалено кривих: {}".format(changed))


if __name__ == "__main__":
    main()
