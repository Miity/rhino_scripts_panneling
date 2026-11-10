# -*- coding: utf-8 -*-
"""Trims the selected curves at both ends or one end (click near it) by the given distance (in document units).
One end: click after click, option Undo takes back the last trim."""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)  # live Rhino keeps old module versions
from click_undo import UNDO, Steps  # option Undo: take back the last click

DIST_MM = 50.0  # default trim distance


def cut_params(crv, d0, d1):
    """Curve parameters at length d0 from the start and d1 from the end; None if the curve is too short.
    Also used by curves/KeepCrvEnds.py."""
    length = crv.GetLength()
    if length - d0 - d1 <= sc.doc.ModelAbsoluteTolerance:
        return None
    ok0, t0 = crv.LengthParameter(d0)
    ok1, t1 = crv.LengthParameter(length - d1)
    return (t0, t1) if ok0 and ok1 else None


def trim_ends(crv, dist, side="Both"):
    ts = cut_params(crv, dist if side in ("Both", "Start") else 0.0, dist if side in ("Both", "End") else 0.0)
    return crv.Trim(ts[0], ts[1]) if ts else None


def replace(oid, new):
    if new is None:
        return False
    sc.doc.Objects.Replace(oid, new)  # keeps layer and attributes
    return True


def click_end():
    """One click on a curve near the end to trim. Returns (id, curve parameter), UNDO or None (Enter / Esc)."""
    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt("Click the curve near the end to trim (Enter - finish)")
    go.AddOption("Undo")  # first: keeps the letter U
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Curve
    go.EnablePreSelect(False, True)
    go.AcceptNothing(True)
    res = go.Get()
    if res == Rhino.Input.GetResult.Option:
        return UNDO
    if res != Rhino.Input.GetResult.Object:
        return None
    ref = go.Object(0)
    rs.UnselectAllObjects()
    return ref.ObjectId, ref.CurveParameter()[1]


HELP = u"""Options (mode One, at the click):
  U — Undo: take back the last trim"""  # printed at start — visible under the option fields



def main():
    print(HELP)
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    dist = rs.GetReal("Trim distance", sc.sticky.get("trim_ends_dist", DIST_MM * mm), 0.0)
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
        steps = Steps()
        while True:
            pick = click_end()
            if pick is None:
                break
            if pick == UNDO:
                steps.undo()
                continue
            oid, t = pick
            crv = rs.coercecurve(oid)
            to_start = crv.GetLength(Rhino.Geometry.Interval(crv.Domain.T0, t))
            side = "Start" if to_start < crv.GetLength() / 2 else "End"
            steps.start()
            steps.change(oid)
            if not replace(oid, trim_ends(crv, dist, side)):
                skipped += 1
            sc.doc.Views.Redraw()
    if skipped:
        print("Skipped {0} curves: too short to trim by {1}".format(skipped, dist))


if __name__ == "__main__":
    main()
