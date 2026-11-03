# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs

def convert_to_polyline_keep_layer():
    # Get the selected objects
    selected_objs = rs.SelectedObjects()
    
    if not selected_objs:
        print("Please select curves before running.")
        return

    # Tolerance settings
    tolerance = 0.1

    rs.EnableRedraw(False)
    
    for obj in selected_objs:
        if rs.IsCurve(obj):
            # Replaced in place: layer, groups and attributes stay
            rs.ConvertCurveToPolyline(obj, angle_tolerance=5, tolerance=tolerance, delete_input=True)

    rs.EnableRedraw(True)
    print("Conversion finished. Layers and groups kept.")

if __name__ == "__main__":
    convert_to_polyline_keep_layer()