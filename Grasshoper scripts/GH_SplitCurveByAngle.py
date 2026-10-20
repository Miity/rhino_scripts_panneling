import Rhino.Geometry as rg
import math

# ==============================================================================
# Rhino / Grasshopper Python Component
# Description: Splits a curve only at kinks where the angle between 
#              segments is strictly greater than a specified threshold.
#
# Inputs:
#     C : Curve to split (Set Type Hint to: Curve)
#     A : Angle threshold in degrees (Set Type Hint to: float)
#
# Outputs:
#     a : List of split curve segments
# ==============================================================================

def split_curve_by_angle(crv, angle_threshold_deg):
    if not crv: return []
    
    # Convert angle threshold to radians for RhinoCommon internal math
    threshold_rad = math.radians(angle_threshold_deg)
    
    # Extract segments based on curve type
    if isinstance(crv, rg.PolyCurve):
        segments = [crv.SegmentCurve(i) for i in range(crv.SegmentCount)]
    else:
        # For standard curves, duplicate segments breaks them at G0 continuity
        segments = crv.DuplicateSegments()
        
    if not segments: return [crv]

    split_params = []
    
    # Iterate through segment junctions
    for i in range(len(segments)):
        # Python's negative index beautifully handles closed curves (loops to the end)
        prev_seg = segments[i - 1] 
        curr_seg = segments[i]
        
        # Get tangent vectors at the junction
        v1 = prev_seg.TangentAt(prev_seg.Domain.Max)
        v2 = curr_seg.TangentAt(curr_seg.Domain.Min)
        
        # Calculate angle between tangent vectors
        angle = rg.Vector3d.VectorAngle(v1, v2)
        
        # Check condition (> 45 degrees)
        if angle > threshold_rad:
            # Find the parameter 't' on the original curve to execute the split
            rc, t = crv.ClosestPoint(curr_seg.PointAtStart)
            if rc:
                split_params.append(t)
                
    # Split the original curve at collected parameters
    if split_params:
        split_curves = crv.Split(split_params)
        return list(split_curves) if split_curves else [crv]
    else:
        return [crv]

# GH Component entry point execution
if 'C' in globals() and 'A' in globals():
    if C is not None:
        if A is None:
            A = 45.0 # Default fallback
        a = split_curve_by_angle(C, A)
    else:
        a = []
