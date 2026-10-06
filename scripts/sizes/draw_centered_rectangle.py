# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs

def draw_centered_rectangle_on_cplane():
    # Geometry parameters (in document units)
    width = 1340.0
    height = 6657.973
    
    # Get the active CPlane
    cplane = rs.ViewCPlane()
    
    # Ask the user for a point
    center_pt = rs.GetPoint("Pick the rectangle centre", in_plane=True)
    if not center_pt: 
        return
    
    # Move the coordinate system (CPlane) to the picked point
    base_plane = rs.MovePlane(cplane, center_pt)
    
    # Compute the offset vector for the rectangle corner
    shift_vec = base_plane.XAxis * (-width / 2.0) + base_plane.YAxis * (-height / 2.0)
    corner_pt = rs.PointAdd(base_plane.Origin, shift_vec)
    
    # Plane for building the rectangle
    rect_plane = rs.MovePlane(base_plane, corner_pt)
    
    # Generate geometry (NURBS curve)
    rectangle_id = rs.AddRectangle(rect_plane, width, height)
    
    if rectangle_id:
        rs.SelectObject(rectangle_id)
        print("Rectangle generated.")

if __name__ == "__main__":
    draw_centered_rectangle_on_cplane()