# -*- coding: utf-8 -*-
"""Write each closed planar curve's CPlane-aligned size inside it.

Run in Rhino's Python editor (Rhino 6/7 IronPython 2.7 or Rhino 8 CPython 3).
The dimensions are in document units. The current CPlane defines left/top and
the X/Y directions. A chosen document annotation style (remembered, default PAT 14 mm)
controls text font and height. Tall, narrow curves get a counterclockwise 90-degree fallback in the
lower-left corner when the horizontal label does not fit. No bounding-box
geometry is added.
"""

import os
import sys

import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
sys.modules.pop("PatternTextStyles", None)  # Rhino keeps modules from the first run for the session
import PatternTextStyles  # PAT styles, default label style PAT 14 mm


LAYER_NAME = "INK"
STICKY = "LabelClosedCurveSizes"


def local_xy(point, plane):
    delta = point - plane.Origin
    return delta * plane.XAxis, delta * plane.YAxis


def xy_bounds(points, plane):
    coordinates = [local_xy(point, plane) for point in points]
    return (min(p[0] for p in coordinates), min(p[1] for p in coordinates),
            max(p[0] for p in coordinates), max(p[1] for p in coordinates))


def drawing_plane(curve, cplane, tolerance):
    """Use the curve's plane with axes as close as possible to the active CPlane."""
    success, raw_plane = curve.TryGetPlane(tolerance)
    if not success:
        return None
    normal = raw_plane.Normal
    if normal * cplane.ZAxis < 0:
        normal.Reverse()
    x_axis = cplane.XAxis - normal * (cplane.XAxis * normal)
    if not x_axis.Unitize():
        y_axis = cplane.YAxis - normal * (cplane.YAxis * normal)
        if not y_axis.Unitize():
            return None
        x_axis = rg.Vector3d.CrossProduct(y_axis, normal)
    y_axis = rg.Vector3d.CrossProduct(normal, x_axis)
    return rg.Plane(raw_plane.Origin, x_axis, y_axis)


def number_string(value, precision):
    result = ("{0:.%df}" % precision).format(value)
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    if result == "0" and value > 0:
        result = "{0:.8g}".format(value)
    return result


def rectangle_fits(curve, plane, left, bottom, right, top, tolerance):
    corners = [plane.PointAt(left, bottom), plane.PointAt(right, bottom),
               plane.PointAt(right, top), plane.PointAt(left, top)]
    for corner in corners:
        if curve.Contains(corner, plane, tolerance) != rg.PointContainment.Inside:
            return False
    outline = rg.PolylineCurve(corners + [corners[0]])
    events = rg.Intersect.Intersection.CurveCurve(curve, outline,
                                                  tolerance, tolerance)
    return events is None or events.Count == 0


def candidate_positions(left, bottom, right, top, text_width, text_height,
                        margin, prefer_bottom=False):
    left_limit = left + margin
    right_limit = right - margin - text_width
    upper_limit = top - margin
    lower_limit = bottom + margin + text_height
    if right_limit < left_limit or lower_limit > upper_limit:
        return []
    positions = []
    for row in range(9):
        for column in range(9):
            x = left_limit + (right_limit - left_limit) * column / 8.0
            if prefer_bottom:
                y = lower_limit + (upper_limit - lower_limit) * row / 8.0
            else:
                y = upper_limit - (upper_limit - lower_limit) * row / 8.0
            positions.append((row + column, column, row, x, y))
    positions.sort()
    return [(item[3], item[4]) for item in positions]


def choose_style():
    """Select an annotation style (remembered, default PAT 14 mm). None — cancelled."""
    current = PatternTextStyles.label_style(sc.doc, STICKY).Name  # also creates the PAT styles
    selected = rs.ListBox(rs.DimStyleNames(sort=True) or [], u"Select the text style for size labels",
                          u"Label style", current)
    if selected:
        sc.sticky[STICKY + ".style"] = selected
    return sc.doc.DimStyles.FindName(selected) if selected else None


def add_label(curve_id, cplane, tolerance, precision, style):
    curve = rs.coercecurve(curve_id)
    if curve is None or not curve.IsClosed:
        return False, u"is not a closed curve"
    plane = drawing_plane(curve, cplane, tolerance)
    if plane is None:
        return False, u"the curve is not planar"

    curve_box = rs.BoundingBox(curve_id, plane)
    if not curve_box:
        return False, u"could not measure the curve"
    left, bottom, right, top = xy_bounds(curve_box, plane)
    width, height = right - left, top - bottom
    small_side = min(width, height)
    if small_side <= 2.0 * tolerance:
        return False, u"the curve is too small"

    label = u"{0} x {1}".format(number_string(width, precision),
                               number_string(height, precision))
    margin = max(2.0 * tolerance, small_side * 0.04)
    text_planes = [(plane, False)]
    if height > width + tolerance:
        # Counterclockwise: the first letter starts at the lower left and
        # the remaining letters run up the long side of a narrow piece.
        rotated_plane = rg.Plane(plane.Origin, plane.YAxis, -plane.XAxis)
        text_planes.append((rotated_plane, True))

    for text_plane, prefer_bottom in text_planes:
        entity = rg.TextEntity.Create(label, text_plane, style, False, 0.0, 0.0)
        if entity is None:
            return False, u"could not create the text"
        entity.DimensionStyleId = style.Id
        entity.ClearPropertyOverrides()
        text_id = sc.doc.Objects.AddText(entity)
        if text_id == System.Guid.Empty:
            return False, u"could not add the text to the document"
        placed = False
        try:
            text_box = rs.BoundingBox(text_id, plane)
            if not text_box:
                return False, u"could not measure the text"
            text_left, text_bottom, text_right, text_top = xy_bounds(text_box, plane)
            text_width = text_right - text_left
            text_depth = text_top - text_bottom
            positions = candidate_positions(left, bottom, right, top,
                                            text_width, text_depth, margin,
                                            prefer_bottom)
            for x, y in positions:
                if not rectangle_fits(curve, plane, x, y - text_depth,
                                      x + text_width, y, tolerance):
                    continue
                displacement = plane.XAxis * (x - text_left)
                displacement += plane.YAxis * (y - text_top)
                if not rs.MoveObject(text_id, displacement):
                    return False, u"could not move the text"
                rs.ObjectLayer(text_id, LAYER_NAME)
                if rs.ObjectLayer(text_id) != LAYER_NAME:
                    return False, u"could not assign layer INK"
                placed = True
                return True, label
        finally:
            # Failed candidates leave no temporary text in the document.
            if not placed and rs.IsObject(text_id):
                rs.DeleteObject(text_id)
    return False, u"the label in the selected style does not fit inside"


def main():
    ids = rs.GetObjects(u"Select closed planar contours for size labels",
                        rs.filter.curve, preselect=True, select=False)
    if not ids:
        return
    view = sc.doc.Views.ActiveView
    if view is None:
        print(u"No active Rhino view.")
        return
    cplane = view.ActiveViewport.ConstructionPlane()
    tolerance = sc.doc.ModelAbsoluteTolerance
    precision = max(0, int(sc.doc.DistanceDisplayPrecision))
    style = choose_style()
    if style is None:
        return
    if not rs.IsLayer(LAYER_NAME):
        rs.AddLayer(LAYER_NAME)

    completed = 0
    skipped = []
    rs.EnableRedraw(False)
    try:
        for index, curve_id in enumerate(ids, 1):
            try:
                success, message = add_label(curve_id, cplane, tolerance,
                                             precision, style)
            except Exception as error:
                success, message = False, u"{0}".format(error)
            if success:
                completed += 1
            else:
                skipped.append(u"{0}: {1}".format(index, message))
    finally:
        rs.EnableRedraw(True)
        sc.doc.Views.Redraw()
    print(u"Labels on layer INK: {0} of {1}.".format(completed, len(ids)))
    for item in skipped:
        print(u"Skipped contour {0}".format(item))


if __name__ == "__main__":
    main()
