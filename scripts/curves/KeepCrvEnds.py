# -*- coding: utf-8 -*-
"""Cuts out the middle of curves: keeps the given length at the start and at the end.
Both pieces of each curve keep the original's layer/attributes and groups, are grouped together and selected."""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc


def keep_ends(crv, dist):
    """Returns [start, end] pieces or None if the curve is too short."""
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
    ids = rs.GetObjects("Select curves", rs.filter.curve, preselect=True)
    if not ids:
        return
    mm5 = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem) * 5
    dist = rs.GetReal("Length kept at each end", sc.sticky.get("keep_ends_dist", mm5), 0.0)
    if not dist:
        return
    sc.sticky["keep_ends_dist"] = dist

    rs.EnableRedraw(False)
    result, skipped = [], 0
    for oid in ids:
        pieces = keep_ends(rs.coercecurve(oid), dist)
        if pieces is None:
            skipped += 1
            result.append(oid)  # stays as is, but selected too
            continue
        attrs = sc.doc.Objects.FindId(oid).Attributes  # layer, colour, linetype, groups
        new = [sc.doc.Objects.AddCurve(p, attrs) for p in pieces]
        rs.AddObjectsToGroup(new, rs.AddGroup())
        sc.doc.Objects.Delete(oid, True)
        result.extend(new)
    rs.UnselectAllObjects()
    rs.SelectObjects(result)
    rs.EnableRedraw(True)
    if skipped:
        print("Skipped {} curves: shorter than 2 x {}".format(skipped, dist))


if __name__ == "__main__":
    main()
