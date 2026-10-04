import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import System

"""BoundingBoxWithSize for Rhino 8
- Uses the current CPlane of the active viewport
- Python 3 compatible
- Safer redraw handling
- Creates bounding box / planar outline plus XYZ text dots
"""


def get_display_mode_by_name(mode_name):
    for mode in Rhino.Display.DisplayModeDescription.GetDisplayModes():
        if not mode.PipelineLocked and mode.LocalName == mode_name:
            return mode
    return None


def set_display_mode_all_viewports(obj_ids, mode_name="Ghosted"):
    if isinstance(obj_ids, System.Guid):
        obj_ids = [obj_ids]

    mode = get_display_mode_by_name(mode_name)
    if not mode:
        return

    view_ids = [view.ActiveViewportID for view in sc.doc.Views]
    for view_id in view_ids:
        for obj_id in obj_ids:
            obj_ref = sc.doc.Objects.Find(obj_id)
            if not obj_ref:
                continue
            attr = obj_ref.Attributes.Duplicate()
            attr.SetDisplayModeOverride(mode, view_id)
            sc.doc.Objects.ModifyAttributes(obj_id, attr, False)


def midpoint(pt_a, pt_b):
    return Rhino.Geometry.Point3d(
        (pt_a.X + pt_b.X) / 2.0,
        (pt_a.Y + pt_b.Y) / 2.0,
        (pt_a.Z + pt_b.Z) / 2.0,
    )


def main():
    msg = "Pick objects for bounding box"
    err_msg = "Bounding box creation failed."

    objs = rs.GetObjects(msg, preselect=True)
    if not objs:
        return

    view = sc.doc.Views.ActiveView
    if not view:
        print("No active view found.")
        return

    plane = view.ActiveViewport.ConstructionPlane()
    bb = rs.BoundingBox(objs, plane)
    if not bb:
        print(err_msg)
        return

    prec = sc.doc.DistanceDisplayPrecision
    tol = sc.doc.ModelAbsoluteTolerance
    unit_name = sc.doc.GetUnitSystemName(True, False, True, True)

    x_len = bb[1].DistanceTo(bb[0])
    y_len = bb[3].DistanceTo(bb[0])
    z_len = bb[4].DistanceTo(bb[0])

    has_x = x_len >= tol
    has_y = y_len >= tol
    has_z = z_len >= tol

    if int(has_x) + int(has_y) + int(has_z) < 2:
        print(err_msg)
        return

    is_volume = has_x and has_y and has_z
    if not has_x:
        area_or_volume = y_len * z_len
    elif not has_y:
        area_or_volume = x_len * z_len
    elif not has_z:
        area_or_volume = x_len * y_len
    else:
        area_or_volume = x_len * y_len * z_len

    x_mid = midpoint(bb[0], bb[1])
    y_mid = midpoint(bb[0], bb[3])
    z_mid = midpoint(bb[0], bb[4])

    x_text = "X {}".format(round(x_len, prec)) if has_x else ""
    y_text = "Y {}".format(round(y_len, prec)) if has_y else ""
    z_text = "Z {}".format(round(z_len, prec)) if has_z else ""

    created = []
    rs.EnableRedraw(False)
    try:
        if is_volume:
            box_id = rs.AddBox(bb)
            if box_id:
                created.append(box_id)
                rs.SurfaceIsocurveDensity(box_id, -1)
                set_display_mode_all_viewports(box_id, "Ghosted")
        else:
            if not has_x:
                poly_id = rs.AddPolyline([bb[0], bb[3], bb[7], bb[4], bb[0]])
            elif not has_y:
                poly_id = rs.AddPolyline([bb[0], bb[1], bb[5], bb[4], bb[0]])
            else:
                poly_id = rs.AddPolyline([bb[0], bb[1], bb[2], bb[3], bb[0]])
            if poly_id:
                created.append(poly_id)

        if has_x:
            dot_id = rs.AddTextDot(x_text, x_mid)
            if dot_id:
                created.append(dot_id)
        if has_y:
            dot_id = rs.AddTextDot(y_text, y_mid)
            if dot_id:
                created.append(dot_id)
        if has_z:
            dot_id = rs.AddTextDot(z_text, z_mid)
            if dot_id:
                created.append(dot_id)

        if created:
            group_name = rs.AddGroup()
            if group_name:
                rs.AddObjectsToGroup(created, group_name)
            rs.ObjectColor(created, System.Drawing.Color.Black)
    finally:
        rs.EnableRedraw(True)
        sc.doc.Views.Redraw()

    desc = "volume" if is_volume else "area"
    unit_prefix = "cubic " if is_volume else "sq. "
    av_text = " || {}: {} {}{}".format(desc, round(area_or_volume, prec), unit_prefix, unit_name)

    if x_text:
        x_text = " | " + x_text
    if y_text:
        y_text = " | " + y_text
    if z_text:
        z_text = " | " + z_text

    print("Bounding box size:{}{}{}{}".format(x_text, y_text, z_text, av_text))


if __name__ == "__main__":
    main()
