# -*- coding: utf-8 -*-
# Selects all closed curves whose area is below the threshold
# (small contours the plotter/cutter physically cannot cut).
import rhinoscriptsyntax as rs
import scriptcontext as sc


def select_small_closed_curves():
    # Threshold in sq. document units. 25 mm^2 ~ a hole 5.6 mm in diameter.
    min_area = rs.GetReal("Minimum area the plotter can cut (sq. units)", 25.0, 0.0)
    if min_area is None:
        return

    # Work on the selection, or if nothing is selected — on all curves in the document.
    objs = rs.SelectedObjects() or rs.ObjectsByType(4, select=False)
    if not objs:
        print("No curves found in the document.")
        return

    rs.EnableRedraw(False)
    rs.UnselectAllObjects()

    small = []
    for obj in objs:
        if not rs.IsCurveClosed(obj):
            continue
        # Planar curves: CurveArea returns None for non-planar ones — they are skipped.
        if not rs.IsCurvePlanar(obj, sc.doc.ModelAbsoluteTolerance):
            continue
        area = rs.CurveArea(obj)
        if area and area[0] < min_area:
            small.append(obj)

    rs.SelectObjects(small)
    rs.EnableRedraw(True)
    print("Selected {} closed curves with area < {}.".format(len(small), min_area))


if __name__ == "__main__":
    select_small_closed_curves()
