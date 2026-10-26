# -*- coding: utf-8 -*-
"""Fewer points on selected polylines, corners kept. A vertex that turns the curve by more than Angle is a corner:
it stays exactly where it is (so the angles of the joints do not change). The runs between corners are thinned
within Tol (no point of the old curve farther than Tol from the new one); option Smooth — each run becomes a
smooth fitted curve instead (the corners stay sharp). Open curves keep their ends. Layer, groups and UserText stay
(the object is replaced in place); one Undo takes the whole run back. Curves that are not polylines are skipped
(CrvToPolyline first)."""
import math

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, Polyline, PolylineCurve, Vector3d

STICKY = "ReducePoints"

# Defaults of the command options (the last values typed in Rhino are remembered until it is closed)
TOL = 0.1       # largest distance between the old and the new curve, document units (mm)
ANGLE = 5.0     # a vertex turning more than this (degrees) is a corner and stays exactly
SMOOTH = False  # True: runs between corners become smooth fitted curves, False: polylines


def reduce(crv, tol, angle, smooth, join_tol=0.001):
    """New curve with fewer points, or None if crv is not a polyline."""
    ok, pl = crv.TryGetPolyline()
    if not ok:
        return None
    closed = crv.IsClosed
    pts = list(pl)[:-1] if closed else list(pl)
    n = len(pts)
    if n < 3:
        return None
    lim = math.radians(angle)
    anchors = [i for i in range(n) if (not closed and i in (0, n - 1)) or (0 < i < n - 1 or closed)
               and Vector3d.VectorAngle(pts[i] - pts[i - 1], pts[(i + 1) % n] - pts[i]) > lim]
    if closed and not anchors:
        anchors = [0]
    runs = []
    for k, a in enumerate(anchors):
        if closed:
            b = anchors[(k + 1) % len(anchors)]
            b += n if b <= a else 0
        elif k + 1 < len(anchors):
            b = anchors[k + 1]
        else:
            break
        runs.append([pts[j % n] for j in range(a, b + 1)])
    curves = []
    for run in runs:
        run_pl = Polyline(run)
        fit = PolylineCurve(run_pl).Fit(3, tol, lim) if smooth and len(run) > 3 else None
        if fit is not None and fit.PointAtStart.DistanceTo(run[0]) <= join_tol \
                and fit.PointAtEnd.DistanceTo(run[-1]) <= join_tol:
            curves.append(fit)
        else:
            run_pl.ReduceSegments(tol)
            curves.append(PolylineCurve(run_pl))
    if not smooth:
        out = list(curves[0].TryGetPolyline()[1])
        for c in curves[1:]:
            out += list(c.TryGetPolyline()[1])[1:]
        return PolylineCurve(out)
    joined = Curve.JoinCurves(curves, join_tol)
    return joined[0] if len(joined) == 1 else None


HELP = u"""Options:
  Tol — largest distance between the old and the new curve (document units)
  Angle — a vertex turning more than this angle is a corner and stays as it is
  Smooth — Yes: runs between corners become smooth fitted curves, No: polylines with fewer vertices"""  # printed at start


def main():
    print(HELP)
    doc = sc.doc
    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt(u"Select polylines to reduce")
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Curve
    go.EnablePreSelect(True, True)
    tol = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_tol", TOL), 0.0001, 1e6)
    angle = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", ANGLE), 0.1, 179.0)
    smooth = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_smooth", SMOOTH), "No", "Yes")
    go.AddOptionDouble("Tol", tol)
    go.AddOptionDouble("Angle", angle)
    go.AddOptionToggle("Smooth", smooth)
    while True:
        r = go.GetMultiple(1, 0)
        if r != Rhino.Input.GetResult.Option:
            break
    sc.sticky[STICKY + "_tol"], sc.sticky[STICKY + "_angle"] = tol.CurrentValue, angle.CurrentValue
    sc.sticky[STICKY + "_smooth"] = smooth.CurrentValue
    if r != Rhino.Input.GetResult.Object:
        return
    rec = doc.BeginUndoRecord(u"ReducePoints")
    done = before = after = 0
    try:
        for o in go.Objects():
            crv = o.Curve()
            new = reduce(crv, tol.CurrentValue, angle.CurrentValue, smooth.CurrentValue, doc.ModelAbsoluteTolerance) \
                if crv is not None else None
            if new is None:
                print(u"Skipped a curve (not a polyline, or fitting failed)")
                continue
            before += crv.TryGetPolyline()[1].Count
            after += new.TryGetPolyline()[1].Count if new.TryGetPolyline()[0] else new.SpanCount + 1
            doc.Objects.Replace(o.ObjectId, new)
            done += 1
    finally:
        doc.EndUndoRecord(rec)
    doc.Views.Redraw()
    print(u"Reduce Points: %d curves, points %d -> %d" % (done, before, after))


if __name__ == "__main__":
    main()
