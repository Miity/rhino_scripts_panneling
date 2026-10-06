# -*- coding: utf-8 -*-
"""
smooth_corners.py

Rounds (fillets with an arc) the corners of selected polylines where the deviation angle
from a straight line is larger than the given threshold. The other corners stay sharp.

Angle convention: 0 deg = segments continue each other (straight),
180 deg = full reversal. So a "sharp corner" = a LARGE value.

Rhino 6/7/8. Compatible with IronPython 2.7 and CPython 3.
Run: _EditPythonScript / _ScriptEditor -> Run.
"""

import math

try:
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    import Rhino
except ImportError:                 # run outside Rhino -> only the self-check is available
    rs = sc = Rhino = None

TOL = 1e-9
FILL = 0.999   # share of a segment that two neighbouring tangents may consume


# ---------- geometry without Rhino dependency (so it can be tested) ----------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _len(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _unit(v):
    n = _len(v)
    return None if n < TOL else (v[0] / n, v[1] / n, v[2] / n)


def turn_angle(p_prev, p, p_next):
    """Deviation angle from a straight line in degrees. 0 = straight, 180 = reversal."""
    a = _unit(_sub(p, p_prev))
    b = _unit(_sub(p_next, p))
    if a is None or b is None:
        return 0.0
    c = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
    return math.degrees(math.acos(c))


def _clamp(pts, closed, t):
    """Shrinks tangent lengths so that two neighbours do not overlap on a segment.

    One pass: each corner gets a proportional share of the segment length.
    Since the shares of the two ends of a segment sum to L*FILL, overlap
    is impossible after one pass — no iterations needed.
    """
    n = len(pts)
    segs = [(i, (i + 1) % n) for i in range(n if closed else n - 1)]
    capped = list(t)
    # ponytail: slightly conservative (a corner trimmed on one side does not return
    # the slack to the neighbour on the other). Exact redistribution — only if visible by eye.
    for i, j in segs:
        s = t[i] + t[j]
        if s <= TOL:
            continue
        L = _len(_sub(pts[j], pts[i]))
        if s > L * FILL:
            capped[i] = min(capped[i], L * FILL * t[i] / s)
            capped[j] = min(capped[j], L * FILL * t[j] / s)
    return capped


def tangent_lengths(pts, closed, radius, min_angle):
    """For each vertex — distance from the vertex to the arc tangent point (0 = do not bend)."""
    n = len(pts)
    t = [0.0] * n
    for i in (range(n) if closed else range(1, n - 1)):
        ang = turn_angle(pts[i - 1], pts[i], pts[(i + 1) % n])
        if ang < min_angle or ang > 179.9:      # 180 -> degenerate arc, skip
            continue
        t[i] = radius * math.tan(math.radians(ang) / 2.0)
    return _clamp(pts, closed, t)


def _dedupe(pts):
    out = []
    for p in pts:
        if not out or _len(_sub(p, out[-1])) > TOL:
            out.append(p)
    while len(out) > 1 and _len(_sub(out[0], out[-1])) < TOL:
        out.pop()
    return out


# ---------- building the curve (needs Rhino) ----------

def build_curve(pts, closed, t):
    n = len(pts)
    P = [Rhino.Geometry.Point3d(p[0], p[1], p[2]) for p in pts]
    A, B, tan_in = [], [], []
    for i in range(n):
        if t[i] <= TOL:
            A.append(P[i]); B.append(P[i]); tan_in.append(None)
            continue
        u_in = P[i] - P[i - 1]; u_in.Unitize()
        u_out = P[(i + 1) % n] - P[i]; u_out.Unitize()
        A.append(P[i] - u_in * t[i])
        B.append(P[i] + u_out * t[i])
        tan_in.append(u_in)

    pc = Rhino.Geometry.PolyCurve()
    for i in range(n):
        if tan_in[i] is not None:
            arc = Rhino.Geometry.Arc(A[i], tan_in[i], B[i])
            if arc.IsValid and arc.Length > TOL:
                pc.Append(arc)
            else:                                # safeguard: do not leave a gap
                pc.Append(Rhino.Geometry.Line(A[i], P[i]))
                pc.Append(Rhino.Geometry.Line(P[i], B[i]))
        if not closed and i == n - 1:
            break
        j = (i + 1) % n
        if B[i].DistanceTo(A[j]) > TOL:
            pc.Append(Rhino.Geometry.Line(B[i], A[j]))
    return pc


def main():
    ids = rs.GetObjects("Select polylines", rs.filter.curve, preselect=True, select=False)
    if not ids:
        return
    min_angle = rs.GetReal("Min. deviation angle from straight, deg (0=straight, 180=reversal)", 20.0, 0.0, 179.0)
    if min_angle is None:
        return
    radius = rs.GetReal("Fillet radius", 5.0, TOL)
    if radius is None:
        return

    done = 0
    skipped = []
    for gid in ids:
        crv = rs.coercecurve(gid)
        ok, pl = crv.TryGetPolyline() if crv else (False, None)
        if not ok or pl is None or pl.Count < 3:
            skipped.append("not a polyline")
            continue
        pts = _dedupe([(p.X, p.Y, p.Z) for p in pl])
        if len(pts) < 3:
            skipped.append("too few vertices")
            continue
        t = tangent_lengths(pts, crv.IsClosed, radius, min_angle)
        if max(t) <= TOL:
            skipped.append("no corners > threshold")
            continue
        new_crv = build_curve(pts, crv.IsClosed, t)
        if new_crv and new_crv.IsValid and sc.doc.Objects.Replace(gid, new_crv):
            done += 1
        else:
            skipped.append("could not replace")

    sc.doc.Views.Redraw()
    print("Curves rounded: {0}, skipped: {1}".format(done, len(skipped)))
    for s in set(skipped):
        print("  reason: {0} x{1}".format(s, skipped.count(s)))


# ---------- self-check (works in plain Python, without Rhino) ----------

def _self_check():
    sq = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]

    t = tangent_lengths(sq, True, 3.0, 20.0)          # 90 deg -> t = r * tan45 = r
    assert all(abs(x - 3.0) < 1e-9 for x in t), t

    t = tangent_lengths(sq, True, 3.0, 91.0)          # threshold above the angle -> untouched
    assert max(t) == 0.0, t

    t = tangent_lengths(sq, True, 100.0, 20.0)        # shrink to the segment length
    assert all(x <= 10 * FILL / 2 + 1e-9 for x in t), t

    almost = [(0, 0, 0), (10, 0, 0), (20, 0.01, 0), (20, 10, 0), (0, 10, 0)]
    t = tangent_lengths(almost, True, 1.0, 5.0)       # ~0.06 deg -> below the threshold
    assert t[1] == 0.0, t

    t = tangent_lengths(sq, False, 3.0, 20.0)         # open: ends are not bent
    assert t[0] == 0.0 and t[-1] == 0.0, t

    print("self-check ok")


if __name__ == "__main__":
    if rs is None:
        _self_check()
    else:
        main()
