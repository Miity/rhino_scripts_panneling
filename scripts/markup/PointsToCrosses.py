# -*- coding: utf-8 -*-
# Converts all selected points into crosses or circles (centre marks), or into lines to the panel edge.
# Accepts: point objects, point clouds, text dots (TextDot), circles (their centre — seam marks drawn as circles).
# Each position is replaced by a cross (two lines, grouped), a circle, or (Edge) a line from the mark to the nearest
# point of the selected outer panel contours — across the seam allowance, ending exactly on the edge, so the seamstress
# sees the mark on the edge when the fabrics are laid over each other.
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


def edge_end(pt, contours, tol):
    """Closest point (perpendicular to the edge) of the nearest closed contour with the mark inside, or None.
    The seam line through the mark is not "inside" — skipped; a mark already on the cut line — None.
    ponytail: nearest containing contour wins — an inner closed piece holding the mark (pocket, strip) with a side
    closer than the cut edge would get the line; select only the outer contours if that happens."""
    ends = []
    for c in contours:
        ok, plane = c.TryGetPlane(tol)
        if c.IsClosed and ok and c.Contains(pt, plane, tol) == Rhino.Geometry.PointContainment.Inside:
            ends.append(c.PointAt(c.ClosestPoint(pt)[1]))
    return min(ends, key=lambda q: q.DistanceTo(pt)) if ends else None


HELP = u"""Shape: Cross / Circle — mark of the given half size / radius; Edge — line from the mark to the nearest
  selected closed panel contour around it (perpendicular, ends on the edge); the seam line through the mark and the
  marks themselves are ignored, so a window over the panel works; a mark already on the edge is skipped
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

    shape = rs.GetString("Mark shape", "Cross", ["Cross", "Circle", "Edge"])
    if shape not in ("Cross", "Circle", "Edge"):
        return
    if shape == "Edge":
        ids = rs.GetObjects("Select the outer panel contours (cut line, closed)", rs.filter.curve)
        if not ids:
            return
        contours = [rs.coercecurve(i) for i in ids if not is_mark_circle(i)]
        tol = sc.doc.ModelAbsoluteTolerance
    else:
        arm = rs.GetReal("Half size (for a circle — radius), document units", 1.0, 0.001)
        if arm is None:
            return
    delete_originals = rs.GetBoolean(
        "Delete originals?", [("Originals", "Keep", "Delete")], [True])
    if delete_originals is None:
        return
    delete_originals = delete_originals[0]

    made = 0
    lengths = []
    originals = set()
    created = []
    prev_layer = rs.CurrentLayer()
    rs.EnableRedraw(False)
    try:
        for c, layer, src in items:
            if layer and rs.IsLayer(layer):
                rs.CurrentLayer(layer)
            if shape == "Edge":
                end = edge_end(c, contours, tol)
                if end is None:
                    continue  # no contour around the mark (already on the edge): no line, the original stays
                new = [rs.AddLine(c, end)]
                lengths.append(end.DistanceTo(c))
            elif shape == "Circle":
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
    if lengths:
        print("Lines %.1f–%.1f long." % (min(lengths), max(lengths)))
    if shape == "Edge" and made < len(items):
        print("Skipped %d marks: already on the edge or no selected closed contour around them." % (len(items) - made))


if __name__ == "__main__":
    points_to_crosses()
