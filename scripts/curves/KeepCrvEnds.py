# -*- coding: utf-8 -*-
"""Вирізає середину кривих: лишає по заданій довжині на початку і в кінці.
Два шматки кожної кривої зберігають шар/атрибути, групи оригіналу, згруповані між собою й виділені."""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc


def keep_ends(crv, dist):
    """Повертає [початковий, кінцевий] шматки або None, якщо крива закоротка."""
    length = crv.GetLength()
    if length - 2 * dist <= sc.doc.ModelAbsoluteTolerance:
        return None
    ok0, t0 = crv.LengthParameter(dist)
    ok1, t1 = crv.LengthParameter(length - dist)
    if not (ok0 and ok1):
        return None
    d = crv.Domain
    pieces = [crv.Trim(d.T0, t0), crv.Trim(t1, d.T1)]
    return pieces if all(pieces) else None


def main():
    ids = rs.GetObjects("Виберіть криві", rs.filter.curve, preselect=True)
    if not ids:
        return
    mm5 = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem) * 5
    dist = rs.GetReal("Довжина, яка лишається на кожному кінці", sc.sticky.get("keep_ends_dist", mm5), 0.0)
    if not dist:
        return
    sc.sticky["keep_ends_dist"] = dist

    rs.EnableRedraw(False)
    result, skipped = [], 0
    for oid in ids:
        pieces = keep_ends(rs.coercecurve(oid), dist)
        if pieces is None:
            skipped += 1
            result.append(oid)  # лишається як є, але теж виділена
            continue
        attrs = sc.doc.Objects.FindId(oid).Attributes  # шар, колір, тип лінії, групи
        new = [sc.doc.Objects.AddCurve(p, attrs) for p in pieces]
        rs.AddObjectsToGroup(new, rs.AddGroup())
        sc.doc.Objects.Delete(oid, True)
        result.extend(new)
    rs.UnselectAllObjects()
    rs.SelectObjects(result)
    rs.EnableRedraw(True)
    if skipped:
        print("Пропущено {} кривих: коротші за 2 x {}".format(skipped, dist))


if __name__ == "__main__":
    main()
