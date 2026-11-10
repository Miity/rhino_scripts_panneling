# -*- coding: utf-8 -*-
"""Split the selected curves at corners sharper than Angle (the turn between neighbouring segments; 0 = straight).
Micro steps shorter than Noise are ignored: the turn is measured between the longer segments around them.
The pieces keep the layer, attributes and groups of the curve and are selected.

Also a module: ``angle`` / ``turn_angle`` / ``corners`` (which vertices of a polyline are corners) are used by
curves/smooth_corners.py and curves/ReducePoints.py. This part works without Rhino."""
import math
import os
import sys

try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.modules.pop("TrimOutsidePanel", None)  # live Rhino keeps old module versions
    import TrimOutsidePanel  # replace: the pieces in place of the curve
except ImportError:  # outside Rhino only the corner maths is available
    Rhino = rs = sc = TrimOutsidePanel = None

STICKY = "SplitCrvByAngle"
ANGLE = 45.0   # degrees: a sharper turn is a corner
NOISE_MM = 1.0  # segments shorter than this are micro steps


def angle(u, v):
    """Angle between two directions (x, y, z) in degrees; 0 if one of them has no length."""
    lu = math.sqrt(u[0] * u[0] + u[1] * u[1] + u[2] * u[2])
    lv = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if lu < 1e-12 or lv < 1e-12:
        return 0.0
    c = (u[0] * v[0] + u[1] * v[1] + u[2] * v[2]) / (lu * lv)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def turn_angle(p_prev, p, p_next):
    """Turn at p in degrees: 0 = straight on, 180 = back."""
    return angle((p[0] - p_prev[0], p[1] - p_prev[1], p[2] - p_prev[2]),
                 (p_next[0] - p[0], p_next[1] - p[1], p_next[2] - p[2]))


def corners(pts, closed, min_angle):
    """[(index, turn in degrees)] of the vertices turning more than min_angle. pts — (x, y, z) without the
    repeated last point of a closed polyline; the ends of an open one are never corners."""
    n = len(pts)
    out = []
    for i in (range(n) if closed else range(1, n - 1)):
        turn = turn_angle(pts[i - 1], pts[i], pts[(i + 1) % n])
        if turn > min_angle:
            out.append((i, turn))
    return out


def split_params(crv, min_angle, noise):
    """Curve parameters of the corners sharper than min_angle (degrees)."""
    segs = [s for s in crv.DuplicateSegments() or [] if s.GetLength() > noise]
    if len(segs) < 2:
        return []
    lo, hi = crv.Domain.T0, crv.Domain.T1
    out = []
    for i in range(0 if crv.IsClosed else 1, len(segs)):
        prev, cur = segs[i - 1], segs[i]
        v1, v2 = prev.TangentAt(prev.Domain.Max), cur.TangentAt(cur.Domain.Min)
        if v1.IsZero:
            v1 = prev.PointAtEnd - prev.PointAtStart
        if v2.IsZero:
            v2 = cur.PointAtEnd - cur.PointAtStart
        if angle((v1.X, v1.Y, v1.Z), (v2.X, v2.Y, v2.Z)) <= min_angle + 1e-3:
            continue
        ok, t = crv.ClosestPoint(cur.PointAtStart)
        if ok and (crv.IsClosed or (abs(t - lo) > 1e-5 and abs(t - hi) > 1e-5)):
            out.append(t)
    return sorted(set(out))


def main():
    ids = rs.GetObjects("Select curves to split at corners", rs.filter.curve, preselect=True)
    if not ids:
        return
    min_angle = rs.GetReal("Split at corners sharper than (degrees)", sc.sticky.get(STICKY + "_angle", ANGLE), 0.0, 180.0)
    if min_angle is None:
        return
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    noise = rs.GetReal("Ignore micro steps shorter than (document units)", sc.sticky.get(STICKY + "_noise", NOISE_MM * mm), 0.0)
    if noise is None:
        return
    sc.sticky[STICKY + "_angle"], sc.sticky[STICKY + "_noise"] = min_angle, noise

    rs.EnableRedraw(False)
    added, split = [], 0
    for oid in ids:
        crv = rs.coercecurve(oid)
        params = split_params(crv, min_angle, noise) if crv is not None else []
        pieces = crv.Split(params) if params else None
        if pieces and len(pieces) > 1:
            added.extend(TrimOutsidePanel.replace(oid, list(pieces), sc.doc.ModelAbsoluteTolerance, join=False))
            split += 1
    rs.EnableRedraw(True)
    if added:
        rs.UnselectAllObjects()
        rs.SelectObjects(added)
    print("Curves split: {0} of {1}, pieces: {2}".format(split, len(ids), len(added)))


def _self_check():
    sq = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
    assert [i for i, _ in corners(sq, True, 45.0)] == [0, 1, 2, 3]
    assert all(abs(t - 90.0) < 1e-9 for _, t in corners(sq, True, 45.0))
    assert [i for i, _ in corners(sq, False, 45.0)] == [1, 2]  # open: the ends are not corners
    assert corners(sq, True, 91.0) == []
    assert turn_angle((0, 0, 0), (1, 0, 0), (2, 0, 0)) == 0.0 and abs(turn_angle((0, 0, 0), (1, 0, 0), (0, 0, 0)) - 180.0) < 1e-6
    assert angle((0, 0, 0), (1, 0, 0)) == 0.0
    print("self-check ok")


if __name__ == "__main__":
    if rs is None:
        _self_check()
    else:
        main()
