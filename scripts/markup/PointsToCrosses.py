# -*- coding: utf-8 -*-
# Converts all selected points into crosses or circles (centre marks).
# Accepts: point objects, point clouds, text dots (TextDot), circles (their centre — seam marks drawn as circles).
# Each position is replaced by a cross (two lines, grouped) or a circle, in the original's layer and groups.
# Compatibility: IronPython 2.7 / CPython 3 (Rhino 8).
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

MARK_MM = 10.0  # circles up to this radius are marks; bigger ones (panel holes) are not touched
SIZE_MM = 1.0  # default half size of a cross / radius of a circle


def is_mark_circle(obj):
    r = MARK_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    return rs.IsCurve(obj) and rs.IsCircle(obj) and rs.CircleRadius(obj) <= r


def collect_positions(objs):
    """Returns a list of (coordinate, original_id) from different object types."""
    items = []
    for obj in objs:
        if rs.IsPoint(obj):
            items.append((rs.PointCoordinates(obj), obj))
        elif rs.IsPointCloud(obj):
            for pt in rs.PointCloudPoints(obj):
                items.append((pt, obj))
        elif rs.IsTextDot(obj):
            items.append((rs.TextDotPoint(obj), obj))
        elif is_mark_circle(obj):
            items.append((rs.CircleCenterPoint(obj), obj))
    return items


def mark_attributes(src):
    """Attributes of a new mark: the original's layer and groups only (its UserText, e.g. Notch, is not copied)."""
    old = sc.doc.Objects.FindId(src).Attributes
    attrs = Rhino.DocObjects.ObjectAttributes()
    attrs.LayerIndex = old.LayerIndex
    for g in old.GetGroupList() or []:
        attrs.AddToGroup(g)
    return attrs


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
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    arm = rs.GetReal("Half size (for a circle — radius), document units", SIZE_MM * mm, 0.001 * mm)
    if arm is None:
        return
    delete_originals = rs.GetBoolean(
        "Delete originals?", [("Originals", "Keep", "Delete")], [True])
    if delete_originals is None:
        return
    delete_originals = delete_originals[0]

    view = sc.doc.Views.ActiveView
    plane = view.ActiveViewport.ConstructionPlane() if view else Rhino.Geometry.Plane.WorldXY  # a circle lies in the CPlane
    originals = set()
    created = []
    rs.EnableRedraw(False)
    try:
        for c, src in items:
            c = Rhino.Geometry.Point3d(c[0], c[1], c[2])
            attrs = mark_attributes(src)
            if shape == "Circle":
                plane.Origin = c
                created.append(sc.doc.Objects.AddCircle(Rhino.Geometry.Circle(plane, arm), attrs))
            else:
                attrs.AddToGroup(sc.doc.Groups.Add())  # the two lines of a cross — one group
                x, y = Rhino.Geometry.Vector3d(arm, 0, 0), Rhino.Geometry.Vector3d(0, arm, 0)
                created.append(sc.doc.Objects.AddLine(c - x, c + x, attrs))
                created.append(sc.doc.Objects.AddLine(c - y, c + y, attrs))
            originals.add(src)
        if delete_originals:
            rs.DeleteObjects(list(originals))
        rs.UnselectAllObjects()
        rs.SelectObjects(created)
    finally:
        rs.EnableRedraw(True)
    made = len(items)
    print("Done: %d marks (%s)." % (made, shape))


if __name__ == "__main__":
    points_to_crosses()
