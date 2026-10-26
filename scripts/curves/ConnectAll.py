# -*- coding: utf-8 -*-
"""Connect all corners of the selected open curves at once (like _Connect, one corner after another).
Curve ends are paired with the nearest ends of other curves (or the other end of the same curve) closer than Gap,
the closest pair first; each pair is joined like JoinCorner (edges extended / trimmed to their intersection,
corner to corner). A curve that closes is done; ends with no partner within Gap stay and are printed.
The first selected curve of a chain keeps its object (layer, groups, UserText), the others are deleted and their
groups merge into it. One Undo takes the whole run back."""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parts"))
sys.modules.pop("JoinCorner", None)  # live Rhino keeps old module versions
import JoinCorner as JC

STICKY = "ConnectAll"


def connect(curves, gap, angle, tol):
    """curves — open Curves. Returns (items, free): items — [curve, [indices into curves]] per result (closed or
    not), free — [(item number, at_end)] of the ends that found no partner."""
    items = [[c, [i]] for i, c in enumerate(curves)]
    while True:
        cands = []
        for a, (ca, _) in enumerate(items):
            for b in range(a, len(items)):
                cb = items[b][0]
                for ea, eb in ((False, True),) if a == b else ((x, y) for x in (False, True) for y in (False, True)):
                    d = (ca.PointAtEnd if ea else ca.PointAtStart).DistanceTo(cb.PointAtEnd if eb else cb.PointAtStart)
                    if d <= gap and not ca.IsClosed and not cb.IsClosed:
                        cands.append((d, a, ea, b, eb))
        for d, a, ea, b, eb in sorted(cands):
            ca, cb = items[a][0], items[b][0]
            if d <= tol:  # already touching: just join
                if a == b:
                    res = ca.DuplicateCurve()
                    res.SetEndPoint(res.PointAtStart)
                else:
                    joined = Curve.JoinCurves([ca, cb], tol)
                    res = joined[0] if len(joined) == 1 else None
            else:
                mid = (ca.PointAtEnd if ea else ca.PointAtStart) + (cb.PointAtEnd if eb else cb.PointAtStart)
                res = JC.join([(ca, ea), (ca if a == b else cb, eb)], mid / 2, angle, tol)
            if isinstance(res, Curve):
                break
        else:
            break  # nothing left to join
        merged = [res, items[a][1] + ([] if a == b else items[b][1])]
        items = [it for k, it in enumerate(items) if k not in (a, b)] + [merged]
    free = [(k, e) for k, (c, _) in enumerate(items) if not c.IsClosed for e in (False, True)]
    return items, free


HELP = u"""Options:
  Gap — ends closer than this are connected (document units)
  Angle — a break larger than this angle = corner (an edge runs corner to corner)"""  # printed at start


def main():
    print(HELP)
    doc = sc.doc
    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt(u"Select open curves to connect")
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Curve
    go.EnablePreSelect(True, True)
    gap = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_gap", 2.0), 0.0, 1e9)
    angle = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    go.AddOptionDouble("Gap", gap)
    go.AddOptionDouble("Angle", angle)
    while True:
        r = go.GetMultiple(1, 0)
        if r == Rhino.Input.GetResult.Option:
            continue
        break
    sc.sticky[STICKY + "_gap"], sc.sticky[STICKY + "_angle"] = gap.CurrentValue, angle.CurrentValue
    if r != Rhino.Input.GetResult.Object:
        return
    ids = [o.ObjectId for o in go.Objects() if o.Curve() is not None and not o.Curve().IsClosed]
    if len(ids) < 1:
        print(u"No open curves in the selection")
        return
    tol = doc.ModelAbsoluteTolerance
    curves = [rs.coercecurve(i).DuplicateCurve() for i in ids]
    items, free = connect(curves, gap.CurrentValue, angle.CurrentValue, tol)

    rec = doc.BeginUndoRecord(u"ConnectAll")
    try:
        out = []
        for crv, idx in items:
            keep = ids[min(idx)]
            if crv is curves[idx[0]]:
                out.append(keep)  # untouched
                continue
            doc.Objects.Replace(keep, crv)
            for i in idx:
                if ids[i] != keep:
                    JC.merge_groups(keep, ids[i])
                    doc.Objects.Delete(ids[i], True)
            out.append(keep)
    finally:
        doc.EndUndoRecord(rec)
    rs.UnselectAllObjects()
    rs.SelectObjects(out)
    doc.Views.Redraw()
    closed = sum(1 for c, _ in items if c.IsClosed)
    print(u"Connect All: %d curves -> %d (%d closed)" % (len(ids), len(items), closed))
    for k, e in free:
        c = items[k][0]
        p = c.PointAtEnd if e else c.PointAtStart
        print(u"  free end at %.3f, %.3f (no partner within Gap)" % (p.X, p.Y))


if __name__ == "__main__":
    main()
