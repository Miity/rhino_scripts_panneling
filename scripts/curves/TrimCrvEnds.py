# -*- coding: utf-8 -*-
"""Trims the selected curves at both ends or one end (click near it) by the given distance (in document units)."""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc


def trim_ends(crv, dist, side="Both"):
    tol = sc.doc.ModelAbsoluteTolerance
    length = crv.GetLength()
    d0 = dist if side in ("Both", "Start") else 0.0
    d1 = dist if side in ("Both", "End") else 0.0
    if length - d0 - d1 <= tol:
        return None
    ok0, t0 = crv.LengthParameter(d0)
    ok1, t1 = crv.LengthParameter(length - d1)
    if not (ok0 and ok1):
        return None
    return crv.Trim(t0, t1)


def replace(oid, new):
    if new is None:
        return False
    sc.doc.Objects.Replace(oid, new)  # keeps layer and attributes
    return True


def main():
    dist = rs.GetReal("Trim distance", sc.sticky.get("trim_ends_dist", 50.0), 0.0)
    if dist is None:
        return
    sc.sticky["trim_ends_dist"] = dist
    # Rhino command line options must be Latin
    mode = rs.GetString("Where to trim (Both=both ends, One=one end, click near it)",
                        sc.sticky.get("trim_ends_mode", "Both"), ["Both", "One"])
    if mode not in ("Both", "One"):
        return
    sc.sticky["trim_ends_mode"] = mode

    skipped = 0
    if mode == "Both":
        ids = rs.GetObjects("Select curves to trim", rs.filter.curve, preselect=True)
        for oid in ids or []:
            if not replace(oid, trim_ends(rs.coercecurve(oid), dist)):
                skipped += 1
    else:
        # Click the curve closer to the end to trim; Enter/Esc — finish
        while True:
            pick = rs.GetCurveObject("Click the curve near the end to trim (Enter — finish)")
            if not pick:
                break
            oid, t = pick[0], pick[4]
            crv = rs.coercecurve(oid)
            to_start = crv.GetLength(Rhino.Geometry.Interval(crv.Domain.T0, t))
            side = "Start" if to_start < crv.GetLength() / 2 else "End"
            if not replace(oid, trim_ends(crv, dist, side)):
                skipped += 1
            sc.doc.Views.Redraw()
    if skipped:
        print("Skipped {} curves: too short to trim by {}".format(skipped, dist))


if __name__ == "__main__":
    main()
