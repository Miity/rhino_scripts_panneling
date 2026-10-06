# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino.Geometry as rg
import math

def smart_explode_ultimate():
    # 1. Ask for curves
    curve_ids = rs.GetObjects("Select curves for 'Smart split'", rs.filter.curve, preselect=True)
    if not curve_ids: return

    # 2. Ask for the angle
    angle_deg = rs.GetReal("Split threshold angle (degrees)", 45.0, 0.0, 180.0)
    if angle_deg is None: return
    
    # 3. NEW PARAMETER: length of noise segments
    noise_len = rs.GetReal("Ignore 'micro-steps' shorter than (file units)", 1.0, 0.0)
    if noise_len is None: return

    threshold_rad = math.radians(angle_deg)
    rs.EnableRedraw(False)
    curves_added = []
    
    for crv_id in curve_ids:
        crv = rs.coercecurve(crv_id)
        if not crv: continue
        
        segments = crv.DuplicateSegments()
        if not segments or len(segments) <= 1: continue
            
        # --- MICRO-NOISE FILTERING ---
        # Keep only segments longer than the given threshold
        valid_segments = []
        for seg in segments:
            if seg.GetLength() > noise_len:
                valid_segments.append(seg)
                
        # If nothing is left to analyse after cleaning — skip
        if len(valid_segments) <= 1: continue
            
        split_params = []
        start_index = 0 if crv.IsClosed else 1
        
        # Analyse only stable, long segments
        for i in range(start_index, len(valid_segments)):
            prev_seg = valid_segments[i - 1] 
            curr_seg = valid_segments[i]
            
            # Take vectors at the end of the previous and the start of the next VALID segment
            v1 = prev_seg.TangentAt(prev_seg.Domain.Max)
            v2 = curr_seg.TangentAt(curr_seg.Domain.Min)
            
            # Guard: if the vector is zero, use the overall segment direction
            if v1.IsZero: v1 = prev_seg.PointAtEnd - prev_seg.PointAtStart
            if v2.IsZero: v2 = curr_seg.PointAtEnd - curr_seg.PointAtStart
            
            if v1.IsZero or v2.IsZero: continue
                
            angle = rg.Vector3d.VectorAngle(v1, v2)
            
            # If the global angle exceeds the threshold
            if angle > (threshold_rad + 1e-5):
                # Find the split point
                rc, t = crv.ClosestPoint(curr_seg.PointAtStart)
                if rc:
                    # Guard for open curves against splitting at the ends
                    if not crv.IsClosed:
                        if abs(t - crv.Domain.Min) < 1e-5 or abs(t - crv.Domain.Max) < 1e-5:
                            continue
                    split_params.append(t)
        
        # Actual split
        if split_params:
            split_params = list(set(split_params))
            split_results = crv.Split(split_params)
            
            if split_results and len(split_results) > 0:
                attr = sc.doc.Objects.Find(crv_id).Attributes
                for sc_crv in split_results:
                    new_id = sc.doc.Objects.AddCurve(sc_crv, attr)
                    curves_added.append(new_id)
                rs.DeleteObject(crv_id)
                
    rs.EnableRedraw(True)
    if curves_added:
        rs.SelectObjects(curves_added)

if __name__ == "__main__":
    smart_explode_ultimate()