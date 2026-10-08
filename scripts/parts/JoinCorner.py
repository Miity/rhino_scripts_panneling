# -*- coding: utf-8 -*-
"""Join any two open curves at a corner, edge to edge (like _Connect, but for corner-to-corner edges).
Typical case: two ZipCover / Seam markups on neighbouring panel edges leave a notch at the panel corner.
Select curves (window selection is fine: texts and points are ignored), then click near the
corner (several corners in a row, Enter — done). The two curve ends nearest the click are taken (two curves,
or both ends of one curve). An edge runs corner to corner (corner — a break larger than Angle).
For each end the script either joins its last edge or drops the short end to the panel (its last segment, or
the whole last edge) and joins the edge before it — whichever pair of edges meets nearest the click. The two edges are extended (straight, along the tangent)
or trimmed to their intersection, everything beyond it is removed, the curves are joined into one.
Two curves → the first keeps its object (layer, groups, UserText), the second is deleted and its group (label,
seam points) merges into the first's group. Both ends of one curve (frame around a panel) → it closes.
If after a join the two far ends also touch (markups end exactly on the panel corner), that corner is joined too.
A closed curve (e.g. a frame already closed with a notch at a corner) works too: the inward break (notch,
turn larger than Angle) nearest the click is taken as the two ends; smooth bends and outward corners are never notches.
Parallel edges — skipped with a message.
"""
import math

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, CurveEnd, CurveExtensionStyle, Vector3d
from Rhino.Geometry.Intersect import Intersection

STICKY = "JoinCorner"


def segments(crv, tol):
    return [s for s in crv.DuplicateSegments() or [crv.DuplicateCurve()] if s.GetLength() > tol]


def tail(segs, at_end, angle):
    """Number of segments in the edge at that end of segs (corner to corner: breaks up to angle stay in the edge)."""
    order = list(reversed(segs)) if at_end else segs
    n = 1
    while n < len(order):
        a, b = (order[n], order[n - 1]) if at_end else (order[n - 1], order[n])
        if Vector3d.VectorAngle(a.TangentAtEnd, b.TangentAtStart) > math.radians(angle):
            break
        n += 1
    return n


def drops(segs, at_end, angle):
    """How many segments may be dropped at that end: none, the last segment, the whole last edge.
    Segment matters when the short end bends less than angle into a curved edge (it is not an edge of its own)."""
    return sorted(set(k for k in (0, 1, tail(segs, at_end, angle)) if k < len(segs)))


def flip(cs):
    """Curves in reverse order, each reversed."""
    out = []
    for c in reversed(cs):
        c = c.DuplicateCurve()
        c.Reverse()
        out.append(c)
    return out


def extended(e, at_end, big):
    return e.Extend(CurveEnd.End if at_end else CurveEnd.Start, big, CurveExtensionStyle.Line)


def cut(e, at_end, x):
    """Edge from its far end to x (x on its straight extension or on the edge itself)."""
    ext = extended(e, at_end, e.GetLength() + x.DistanceTo(e.PointAtEnd if at_end else e.PointAtStart) * 2 + 1)
    t = ext.ClosestPoint(x)[1]
    return ext.Trim(ext.Domain.T0, t) if at_end else ext.Trim(t, ext.Domain.T1)


def join(ends, click, angle, tol):
    """ends — two (curve, at_end) (the same curve twice for a frame). Joined curve or an error string.
    For each end: drop 0 / 1 segment / the last edge, then the edge at the new end (corner to corner) is extended
    or trimmed to meet the other one; the pair meeting nearest the click wins."""
    (ca, ea), (cb, eb) = ends
    same = ca is cb
    sa = segments(ca, tol)
    sb = sa if same else segments(cb, tol)
    big = 10 * (ca.GetLength() + cb.GetLength())
    now = (ca.PointAtEnd if ea else ca.PointAtStart, cb.PointAtEnd if eb else cb.PointAtStart)
    best = None
    for da in drops(sa, ea, angle):
        for db in drops(sb, eb, angle):
            ra = sa[:len(sa) - da] if ea else sa[da:]
            if same:  # frame: both ends cut from one list (ea is the start or the end, eb the other)
                lo, hi = (db, len(sa) - da) if ea else (da, len(sa) - db)
                ra = rb = sa[lo:hi]
                if len(ra) < 2:
                    continue
            else:
                rb = sb[:len(sb) - db] if eb else sb[db:]
            na, nb = tail(ra, ea, angle), tail(rb, eb, angle)
            if same and na + nb > len(ra):
                continue  # the two edges would overlap
            ga = ra[len(ra) - na:] if ea else ra[:na]
            gb = rb[len(rb) - nb:] if eb else rb[:nb]
            ta, tb = Curve.JoinCurves(ga, tol)[0], Curve.JoinCurves(gb, tol)[0]
            xa, xb = extended(ta, ea, big), extended(tb, eb, big)
            if xa is None or xb is None:
                continue
            pts = [ev.PointA for ev in Intersection.CurveCurve(xa, xb, tol, tol) or []]
            if not pts:
                continue
            x = min(pts, key=click.DistanceTo)
            if da == db == 0 and all(p.DistanceTo(x) <= tol for p in now):
                continue  # already joined there — nothing to do
            if best is None or x.DistanceTo(click) < best[0]:
                best = (x.DistanceTo(click), ra, rb, na, nb, ta, tb, x)
    if best is None:
        return u"the edges near the click do not meet (parallel?)"
    _, ra, rb, na, nb, ta, tb, x = best
    ka = cut(ta, ea, x)
    kb = cut(tb, eb, x)
    if same:  # rest of the frame between the two edges + both cut edges → closed
        mid = ra[nb:len(ra) - na] if ea else ra[na:len(ra) - nb]
        joined = Curve.JoinCurves([ka, kb] + mid, tol)
        if len(joined) != 1:
            return u"the result did not join into one curve"
        out = joined[0]
    else:  # A ending at x, then B from x — in this order (JoinCurves would also join where the far ends touch)
        pa = ra[:len(ra) - na] + [ka] if ea else flip([ka] + ra[na:])
        pb = [kb] + rb[nb:] if not eb else flip(rb[:len(rb) - nb] + [kb])
        out = Rhino.Geometry.PolyCurve()
        for c in pa + pb:
            out.AppendSegment(c)
        out.RemoveNesting()
        if out.PointAtStart.DistanceTo(out.PointAtEnd) <= tol:  # far ends touch at another corner (markups end
            return join([(out, False), (out, True)], out.PointAtStart, angle, tol)  # on the panel) → join it too
    ok, pl = out.TryGetPolyline()  # a clean polyline if everything is straight (for PreparePanelCut)
    if ok:
        pl.DeleteShortSegments(tol)
        out = Rhino.Geometry.PolylineCurve(pl)
    return out


def notch(crv, click, angle, tol):
    """Closed curve: (distance, seam parameter) of the inward break (notch, turn larger than angle) nearest the click,
    or None. Cutting the curve there makes the corner a frame corner (both ends of one curve)."""
    ok, plane = crv.TryGetPlane(tol)
    if not ok:
        return None
    sign = 1 if crv.ClosedCurveOrientation(plane.ZAxis) == Rhino.Geometry.CurveOrientation.CounterClockwise else -1
    segs = segments(crv, tol)
    best = None
    for i in range(len(segs)):
        a, b = segs[i - 1].TangentAtEnd, segs[i].TangentAtStart
        if Vector3d.VectorAngle(a, b) <= math.radians(angle) or Vector3d.CrossProduct(a, b) * plane.ZAxis * sign >= 0:
            continue  # smooth, or turns the way the curve goes round (outward corner)
        p = segs[i].PointAtStart
        if best is None or p.DistanceTo(click) < best[0]:
            best = (p.DistanceTo(click), crv.ClosestPoint(p)[1])
    return best


def nearest_ends(ids, click, angle, tol):
    """What to join at the click: two curve ends [(id, at_end, seam)] (two curves or both ends of one), seam=None;
    or a notch of a closed curve — the same id twice with the seam parameter to cut it at."""
    cands, notches = [], []
    for i in ids:
        c = rs.coercecurve(i)
        if c is None:
            continue
        if c.IsClosed:
            n = notch(c, click, angle, tol)
            if n:
                notches.append((n[0], i, n[1]))
            continue
        cands += [(c.PointAtStart.DistanceTo(click), i, False), (c.PointAtEnd.DistanceTo(click), i, True)]
    cands.sort(key=lambda k: k[0])
    if notches:
        d, i, t = min(notches, key=lambda k: k[0])
        if len(cands) < 2 or d < cands[1][0]:  # a notch nearer than the open ends → join inside the closed curve
            return [(i, False, t), (i, True, t)]
    return [(i, e, None) for _, i, e in cands[:2]]


def merge_groups(keep_id, drop_id):
    """Members of drop_id's groups go into keep_id's group (created if keep_id has none)."""
    groups = rs.ObjectGroups(drop_id) or []
    if not groups:
        return
    target = (rs.ObjectGroups(keep_id) or [None])[0]
    if target is None:
        target = rs.AddGroup()
        rs.AddObjectToGroup(keep_id, target)
    for g in groups:
        members = [m for m in rs.ObjectsByGroup(g) if m != drop_id]
        if members:
            rs.AddObjectsToGroup(members, target)


def ask(gp):
    """Click near the corner with option Angle. A point or None (Enter / Esc)."""
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    gp.AddOptionDouble("Angle", a)
    while True:
        r = gp.Get()
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options:
  Angle — a break larger than this angle = corner (an edge runs corner to corner)"""  # printed at start


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select curves to join at corners", preselect=True)
    if not ids:
        return
    tol = doc.ModelAbsoluteTolerance
    ids = [i for i in ids if rs.IsCurve(i)]
    if not ids:
        print(u"No curves in the selection")
        return
    made = 0
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near the corner to join (Enter — done)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        angle = sc.sticky[STICKY + "_angle"]
        ends = nearest_ends(ids, click, angle, tol)
        if len(ends) < 2:
            print(u"Skipped: need two curve ends or a notch of a closed curve")
            continue
        (ia, ea, seam), (ib, eb, _) = ends
        ca = rs.coercecurve(ia).DuplicateCurve()
        if seam is not None:
            ca.ChangeClosedCurveSeam(seam)  # notch → both ends of one curve there
        cb = ca if ia == ib else rs.coercecurve(ib)
        res = join([(ca, ea), (cb, eb)], click, angle, tol)
        if not isinstance(res, Curve):
            print(u"Skipped: %s" % res)
            continue
        doc.Objects.Replace(ia, res)
        if ib != ia:
            merge_groups(ia, ib)
            doc.Objects.Delete(ib, True)
            ids.remove(ib)
        made += 1
        doc.Views.Redraw()
    print(u"Join Corner: %d corners joined" % made)


if __name__ == "__main__":
    main()
