# -*- coding: utf-8 -*-
# Converts all selected points into crosses or circles (centre marks).
# Accepts: point objects, point clouds, text dots (TextDot), circles (their centre — seam marks drawn as circles).
# Each position is replaced by a cross (two lines, grouped) or a circle, in the original's layer and groups.
# Compatibility: IronPython 2.7 / CPython 3 (Rhino 8).
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

MARK_MM = 10.0  # circles up to this radius are marks; bigger ones (panel holes) are not touched


def is_mark_circle(obj):
    r = MARK_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    return rs.IsCurve(obj) and rs.IsCircle(obj) and rs.CircleRadius(obj) <= r


def collect_positions(objs):
    """Returns a list of (coordinate, layer, original_id) from different object types."""
    items = []
    for obj in objs:
        if rs.IsPoint(obj):
            items.append((rs.PointCoordinates(obj), rs.ObjectLayer(obj), obj))
        elif rs.IsPointCloud(obj):
            layer = rs.ObjectLayer(obj)
            for pt in rs.PointCloudPoints(obj):
                items.append((pt, layer, obj))
        elif rs.IsTextDot(obj):
            items.append((rs.TextDotPoint(obj), rs.ObjectLayer(obj), obj))
        elif is_mark_circle(obj):
            items.append((rs.CircleCenterPoint(obj), rs.ObjectLayer(obj), obj))
    return items


HELP = u"""Shape: Cross / Circle — mark of the given half size / radius
Originals: Keep / Delete — the selected points / circles"""  # printed at start


def points_to_crosses():
    print(HELP)
    objs = rs.SelectedObjects()
    if not objs:
        objs = rs.GetObjects("Select points / circles", preselect=True)
    if not objs:
        print("Nothing selected.")
        return

    items = collect_positions(objs)
    if not items:
        rs.MessageBox("The selection has no points / point clouds / text dots / circles.\n"
                      "Objects selected: %d" % len(objs))
        return

    shape = rs.GetString("Mark shape", "Cross", ["Cross", "Circle"])
    if shape not in ("Cross", "Circle"):
        return
    arm = rs.GetReal("Half size (for a circle — radius), document units", 1.0, 0.001)
    if arm is None:
        return
    delete_originals = rs.GetBoolean(
        "Delete originals?", [("Originals", "Keep", "Delete")], [True])
    if delete_originals is None:
        return
    delete_originals = delete_originals[0]

    made = 0
    originals = set()
    created = []
    prev_layer = rs.CurrentLayer()
    rs.EnableRedraw(False)
    try:
        for c, layer, src in items:
            if layer and rs.IsLayer(layer):
                rs.CurrentLayer(layer)
            if shape == "Circle":
                new = [rs.AddCircle(c, arm)]
            else:
                new = [rs.AddLine([c[0] - arm, c[1], c[2]], [c[0] + arm, c[1], c[2]]),
                       rs.AddLine([c[0], c[1] - arm, c[2]], [c[0], c[1] + arm, c[2]])]
                rs.AddObjectsToGroup(new, rs.AddGroup())
            if layer and rs.IsLayer(layer):
                rs.ObjectLayer(new, layer)  # original's layer
            for g in rs.ObjectGroups(src) or []:  # stay in the original's groups
                rs.AddObjectsToGroup(new, g)
            created.extend(new)
            originals.add(src)
            made += 1
        if delete_originals:
            rs.DeleteObjects(list(originals))
        rs.UnselectAllObjects()
        rs.SelectObjects(created)
    finally:
        rs.CurrentLayer(prev_layer)
        rs.EnableRedraw(True)
    print("Done: %d marks (%s)." % (made, shape))


if __name__ == "__main__":
    points_to_crosses()
