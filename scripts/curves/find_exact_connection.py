# -*- coding: utf-8 -*-
"""
Senior Computational Designer Tool
Calculates the exact contact point on a curve from a selected point with a locked length.
Works directly in Rhino Document.
"""

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

def find_exact_connection():
    # 1. Get the document tolerance (System Absolute Tolerance)
    tolerance = sc.doc.ModelAbsoluteTolerance
    
    # 2. Pick the target curve
    curve_id = rs.GetCurveObject("Select the target curve for the second connection", preselect=False)
    if not curve_id: 
        print("Error: no curve selected.")
        return
    curve_geom = rs.coercecurve(curve_id[0])
    
    # 3. Pick the first fixed point (P1)
    point_id = rs.GetObject("Select the first connection point (P1)", filter=1, preselect=False)
    if not point_id:
        # If no point is selected in the document, let the user just click it
        p1 = rs.GetPoint("No point selected. Click point P1 in space")
    else:
        p1 = rs.PointCoordinates(point_id)
        
    if not p1:
        print("Error: point P1 not defined.")
        return
        
    # 4. Enter the line length (L)
    length = rs.GetReal("Enter the exact line length (L) in document units", minimum=0.001)
    if not length:
        print("Error: invalid length.")
        return

    # 5. Math via RhinoCommon
    p1_3d = Rhino.Geometry.Point3d(p1[0], p1[1], p1[2])
    sphere = Rhino.Geometry.Sphere(p1_3d, length)
    sphere_brep = sphere.ToBrep()
    
    if not sphere_brep:
        print("Error building the limiting sphere.")
        return
        
    # Intersection of the NURBS curve and the Brep sphere
    rc, _, intersection_points = Rhino.Geometry.Intersect.Intersection.CurveBrep(
        curve_geom, 
        sphere_brep, 
        tolerance
    )
    
    # 6. Generate geometry in the document
    if rc and intersection_points:
        sc.doc.Objects.UnselectAll()
        
        # Disable screen redraw to speed up building
        rs.EnableRedraw(False)
        
        created_lines = []
        for pt in intersection_points:
            # Add the intersection point to the Rhino doc
            pt_id = sc.doc.Objects.AddPoint(pt)
            # Build the fixed-length line
            line_geom = Rhino.Geometry.Line(p1_3d, pt)
            line_id = sc.doc.Objects.AddLine(line_geom)
            
            created_lines.append(line_id)
            # Highlight the created objects
            rs.SelectObject(line_id)
            rs.SelectObject(pt_id)
            
        rs.EnableRedraw(True)
        print("Success! Connection options found: {}. Created lines selected.".format(len(created_lines)))
    else:
        print("Geometry analysis error: the curve is outside the reach radius {} units from point P1.".format(length))

if __name__ == "__main__":
    find_exact_connection()