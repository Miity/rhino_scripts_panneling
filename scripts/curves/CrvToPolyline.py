# -*- coding: utf-8 -*-
"""Selected curves → polylines, replaced in place (layer, groups, attributes kept); polylines and lines are left as they are.

Also a module: ``polyline_copy`` is used by cut/PreparePanelCut.py."""
import math

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

TOL_MM, ANGLE_DEG = 0.1, 5  # the polyline stays within TOL_MM of the curve, turns at most ANGLE_DEG per segment


def polyline_copy(curve):
    """The curve itself if it is a polyline / line, else its polyline copy (None if it cannot be made)."""
    if curve is None or curve.TryGetPolyline()[0]:
        return curve
    tol = TOL_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    return curve.ToPolyline(0, 0, math.radians(ANGLE_DEG), 0, 0, tol, 0, 0, True)


def main():
    ids = rs.SelectedObjects()
    if not ids:
        print("Please select curves before running.")
        return
    rs.EnableRedraw(False)
    changed = 0
    for object_id in ids:
        curve = rs.coercecurve(object_id)
        copy = polyline_copy(curve)
        if copy is not None and copy is not curve and sc.doc.Objects.Replace(object_id, copy):
            changed += 1
    rs.EnableRedraw(True)
    print("Curves turned into polylines: {0} (layers and groups kept).".format(changed))


if __name__ == "__main__":
    main()
