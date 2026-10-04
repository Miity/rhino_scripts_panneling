# -*- coding: utf-8 -*-
"""Sewing points: точка в центрі кривої + точки від центру вліво/вправо з однаковим кроком."""
import rhinoscriptsyntax as rs
import scriptcontext as sc


def sewing_lengths(total, step):
    """Довжини вздовж кривої: центр, потім центр ± k*step, поки в межах кривої."""
    mid = total / 2.0
    out = [mid]
    k = 1
    while k * step <= mid + 1e-9:
        out += [mid - k * step, mid + k * step]
        k += 1
    return sorted(out)


def main():
    crvs = rs.GetObjects("Виберіть криві для sewing points", rs.filter.curve, preselect=True)
    if not crvs:
        return
    step = rs.GetReal("Крок між точками (одиниці документа)", sc.sticky.get("sew_step", 20.0), 0.001)
    if not step:
        return
    sc.sticky["sew_step"] = step

    rs.EnableRedraw(False)
    for cid in crvs:
        crv = rs.coercecurve(cid)
        layer = rs.ObjectLayer(cid)
        ids = [cid]
        for s in sewing_lengths(crv.GetLength(), step):
            ok, t = crv.LengthParameter(s)
            if ok:
                pid = rs.AddPoint(crv.PointAt(t))
                rs.ObjectLayer(pid, layer)
                ids.append(pid)
        # одна крива + її точки = одна група
        rs.AddObjectsToGroup(ids, rs.AddGroup())
    rs.EnableRedraw(True)


if __name__ == "__main__":
    assert sewing_lengths(100, 20) == [10, 30, 50, 70, 90]
    main()
