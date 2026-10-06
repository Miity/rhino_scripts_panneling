# -*- coding: utf-8 -*-
"""Flat bounding box in the CPlane + two centre lines.
After building, select the lines to keep; the rest are deleted."""
import rhinoscriptsyntax as rs


def main():
    ids = rs.GetObjects("Select objects for the bounding box", preselect=True)
    if not ids:
        return
    plane = rs.ViewCPlane()
    box = rs.BoundingBox(ids, plane)
    if not box:
        return
    p0, p1, p2, p3 = box[:4]  # bottom rectangle in the CPlane
    mid = lambda a, b: (a + b) / 2

    rs.EnableRedraw(False)
    lines = [rs.AddLine(p0, p1), rs.AddLine(p1, p2), rs.AddLine(p2, p3), rs.AddLine(p3, p0),
             rs.AddLine(mid(p0, p1), mid(p3, p2)),   # centre line across X
             rs.AddLine(mid(p1, p2), mid(p0, p3))]   # centre line across Y
    lines = [l for l in lines if l]  # degenerate (zero-length) lines are not created
    rs.UnselectAllObjects()
    rs.EnableRedraw(True)

    allowed = set(lines)
    keep = rs.GetObjects("Select the lines to keep (Enter — confirm)", rs.filter.curve,
                         custom_filter=lambda obj, geo, idx: obj.Id in allowed)
    keep = set(keep or [])  # nothing selected / Esc — all are deleted
    rs.DeleteObjects([l for l in lines if l not in keep])
    rs.SelectObjects(list(keep))


if __name__ == "__main__":
    main()
