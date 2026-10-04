# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs

def assign_custom_linetype():
    """
    Assigns the linetype '400,2' to user-selected curves.
    Ensures the linetype exists and overrides layer inheritance.
    """
    target_linetype = "400,2"

    # Verify if the linetype exists in the current Rhino document
    if not rs.IsLinetype(target_linetype):
        rs.MessageBox("Linetype '{}' does not exist in this document. Please define it in Options > Linetypes first.".format(target_linetype), 48, "Missing Definition")
        return

    # Prompt user to select curves
    # Filter set to 4 (Curves) to avoid assigning linetypes to surfaces/meshes where it won't render
    object_ids = rs.GetObjects("Select curves to apply linetype '400,2'", rs.filter.curve)
    
    if not object_ids:
        return

    # Disable redraw during the loop for performance on heavy files
    rs.EnableRedraw(False)
    
    modified_count = 0
    for obj_id in object_ids:
        # Assign the specific linetype
        rs.ObjectLinetype(obj_id, target_linetype)
        
        # Force the object to read linetype from itself, not its layer (1 = By Object)
        rs.ObjectLinetypeSource(obj_id, 1) 
        modified_count += 1
        
    # Re-enable viewport redrawing
    rs.EnableRedraw(True)
    
    print("Successfully updated {} curves to linetype '{}'.".format(modified_count, target_linetype))

if __name__ == "__main__":
    assign_custom_linetype()