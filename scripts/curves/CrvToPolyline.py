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
            # 1. Remember the layer of the original curve
            original_layer = rs.ObjectLayer(obj)
            
            # 2. Convert to a polyline
            polyline = rs.ConvertCurveToPolyline(obj, angle_tolerance=5, tolerance=tolerance)
            
            if polyline:
                # 3. Assign the original's layer to the new polyline
                rs.ObjectLayer(polyline, original_layer)
                
                # 4. Delete the original
                rs.DeleteObject(obj)
    
    rs.EnableRedraw(True)
    print("Conversion finished. Layers kept.")

if __name__ == "__main__":
    convert_to_polyline_keep_layer()