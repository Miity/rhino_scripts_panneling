# -*- coding: utf-8 -*-
"""Sewing points: a point at the curve centre + points left/right of the centre with an equal step."""
import rhinoscriptsyntax as rs
import scriptcontext as sc


def sewing_lengths(total, step):
    """Lengths along the curve: centre, then centre ± k*step, while within the curve."""
    mid = total / 2.0
    out = [mid]
    k = 1
    while k * step <= mid + 1e-9:
        out += [mid - k * step, mid + k * step]
        k += 1
    return sorted(out)


def main():
    crvs = rs.GetObjects("Select curves for sewing points", rs.filter.curve, preselect=True)
    if not crvs:
        return
    step = rs.GetReal("Step between points (document units)", sc.sticky.get("sew_step", 20.0), 0.001)
    if not step:
        return
    sc.sticky["sew_step"] = step
    opt = rs.GetBoolean("Options", [("DeleteInput", "No", "Yes")], [sc.sticky.get("sew_del", True)])
    if opt is None:
        return
    delete = opt[0]
    sc.sticky["sew_del"] = delete

    rs.EnableRedraw(False)
    for cid in crvs:
        crv = rs.coercecurve(cid)
        layer = rs.ObjectLayer(cid)
        ids = []
        for s in sewing_lengths(crv.GetLength(), step):
            ok, t = crv.LengthParameter(s)
            if ok:
                pid = rs.AddPoint(crv.PointAt(t))
                rs.ObjectLayer(pid, layer)
                ids.append(pid)
        if delete:
            rs.DeleteObject(cid)
        else:
            ids.append(cid)
        # points (+ the curve, if kept) = one group
        if ids:
            rs.AddObjectsToGroup(ids, rs.AddGroup())
    rs.EnableRedraw(True)


if __name__ == "__main__":
    assert sewing_lengths(100, 20) == [10, 30, 50, 70, 90]
    main()
