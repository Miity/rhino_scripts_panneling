# -*- coding: utf-8 -*-
"""Join any two open curves at a corner, edge to edge (like _Connect, but for corner-to-corner edges).
Typical case: two ZipCover / Seam markups on neighbouring panel edges leave a notch at the panel corner.
Select curves (window selection is fine: texts, points and closed curves are ignored), then click near the
corner (several corners in a row, Enter — done). The two curve ends nearest the click are taken (two curves,
or both ends of one curve). An edge runs corner to corner (corner — a break larger than Angle).
For each end the script either joins its last edge or drops it (the short end to the panel) and joins the next
one — whichever pair of edges meets nearest the click. The two edges are extended (straight, along the tangent)
or trimmed to their intersection, everything beyond it is removed, the curves are joined into one.
Two curves → the first keeps its object (layer, groups, UserText), the second is deleted and its group (label,
seam points) merges into the first's group. Both ends of one curve (frame around a panel) → it closes.
Parallel edges — skipped with a message.
"""
import math

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, CurveEnd, CurveExtensionStyle, Vector3d
from Rhino.Geometry.Intersect import Intersection

STICKY = "JoinCorner"


def edges(crv, angle, tol):
    """Edges corner to corner of an open curve, in curve order (corner — a break larger than angle)."""
    out = []
    for s in crv.DuplicateSegments() or [crv.DuplicateCurve()]:
        if s.GetLength() <= tol:
            continue
        if out and Vector3d.VectorAngle(out[-1][-1].TangentAtEnd, s.TangentAtStart) <= math.radians(angle):
            out[-1].append(s)
        else:
            out.append([s])
    return [Curve.JoinCurves(g, tol)[0] for g in out]


def plan(es, at_end, drop):
    """(index of the edge to join, its corner end is its end?) for the curve end at_end with drop edges dropped."""
    return (len(es) - 1 - drop, True) if at_end else (drop, False)


def extended(e, at_end, big):
    return e.Extend(CurveEnd.End if at_end else CurveEnd.Start, big, CurveExtensionStyle.Line)


def cut(e, at_end, x):
    """Edge from its far end to x (x on its straight extension or on the edge itself)."""
    ext = extended(e, at_end, e.GetLength() + x.DistanceTo(e.PointAtEnd if at_end else e.PointAtStart) * 2 + 1)
    t = ext.ClosestPoint(x)[1]
    return ext.Trim(ext.Domain.T0, t) if at_end else ext.Trim(t, ext.Domain.T1)


def join(ends, click, angle, tol):
    """ends — two (curve, at_end) (the same curve twice for a frame). Joined curve or an error string."""
    (ca, ea), (cb, eb) = ends
    same = ca is cb
    la, lb = edges(ca, angle, tol), (None if same else edges(cb, angle, tol))
    lb = la if same else lb
    big = 10 * (ca.GetLength() + cb.GetLength())
    best = None
    for da in (0, 1):
        for db in (0, 1):
            ia, fa = plan(la, ea, da)
            ib, fb = plan(lb, eb, db)
            if not (0 <= ia < len(la) and 0 <= ib < len(lb)):
                continue
            if same and (ia >= ib if not fa else ib >= ia):  # frame: start edge before end edge, not the same one
                continue
            xa, xb = extended(la[ia], fa, big), extended(lb[ib], fb, big)
            if xa is None or xb is None:
                continue
            ev = Intersection.CurveCurve(xa, xb, tol, tol)
            pts = [e.PointA for e in ev or []]
            if not pts:
                continue
            x = min(pts, key=click.DistanceTo)
            ends_now = (ca.PointAtEnd if ea else ca.PointAtStart, cb.PointAtEnd if eb else cb.PointAtStart)
            if all(p.DistanceTo(x) <= tol for p in ends_now) and da == db == 0:
                continue  # already joined there — nothing to do
            if best is None or x.DistanceTo(click) < best[0]:
                best = (x.DistanceTo(click), ia, fa, ib, fb, x)
    if best is None:
        return u"the edges near the click do not meet (parallel?)"
    _, ia, fa, ib, fb, x = best
    if same:  # frame: both ends of one curve → closed loop
        es = list(la)
        es[ia], es[ib] = cut(es[ia], fa, x), cut(es[ib], fb, x)
        keep = es[min(ia, ib):max(ia, ib) + 1]
    else:
        ka = la[:ia] + [cut(la[ia], fa, x)] if fa else [cut(la[ia], fa, x)] + la[ia + 1:]
        kb = lb[:ib] + [cut(lb[ib], fb, x)] if fb else [cut(lb[ib], fb, x)] + lb[ib + 1:]
        keep = ka + kb
    joined = Curve.JoinCurves(keep, tol)
    if len(joined) != 1:
        return u"the result did not join into one curve"
    out = joined[0]
    ok, pl = out.TryGetPolyline()  # a clean polyline if everything is straight (for PreparePanelCut)
    if ok:
        pl.DeleteShortSegments(tol)
        out = Rhino.Geometry.PolylineCurve(pl)
    return out


def nearest_ends(ids, click):
    """Two curve ends nearest the click: [(id, at_end)], ends of the same curve allowed."""
    cands = []
    for i in ids:
        c = rs.coercecurve(i)
        if c is None or c.IsClosed:
            continue
        cands += [(c.PointAtStart.DistanceTo(click), i, False), (c.PointAtEnd.DistanceTo(click), i, True)]
    cands.sort(key=lambda k: k[0])
    return [(i, e) for _, i, e in cands[:2]]


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
    ids = [i for i in ids if rs.IsCurve(i) and not rs.IsCurveClosed(i)]
    if not ids:
        print(u"No open curves in the selection")
        return
    made = 0
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near the corner to join (Enter — done)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        ends = nearest_ends(ids, click)
        if len(ends) < 2:
            print(u"Skipped: need two curve ends")
            continue
        (ia, ea), (ib, eb) = ends
        ca = rs.coercecurve(ia)
        cb = ca if ia == ib else rs.coercecurve(ib)
        res = join([(ca, ea), (cb, eb)], click, sc.sticky[STICKY + "_angle"], tol)
        if not isinstance(res, Curve):
            print(u"Skipped: %s" % res)
            continue
        doc.Objects.Replace(ia, res)
        if ib != ia:
            merge_groups(ia, ib)
            doc.Objects.Delete(ib, True)
            ids.remove(ib)
        if res.IsClosed:
            ids.remove(ia)  # closed now — no more ends to join
        made += 1
        doc.Views.Redraw()
    print(u"Join Corner: %d corners joined" % made)


if __name__ == "__main__":
    main()
