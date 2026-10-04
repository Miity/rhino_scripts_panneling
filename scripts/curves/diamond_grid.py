# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs

def create_diamond_grid():
    # 1. Prompt for surface
    srf = rs.GetObject("Select Untrimmed NURBS surface (Fabric)", rs.filter.surface)
    if not srf: return

    # 2. Prompt for diamond size
    size = rs.GetReal("Enter approximate diamond size (e.g. 10.0)", 10.0, 0.1)
    if not size: return

    # 3. Read the actual mathematical UV Domain of the NURBS surface
    u_domain = rs.SurfaceDomain(srf, 0)
    v_domain = rs.SurfaceDomain(srf, 1)

    # 4. Extract isocurves at the start of the domain to measure physical length
    u_crvs = rs.ExtractIsoCurve(srf, (u_domain[0], v_domain[0]), 0)
    v_crvs = rs.ExtractIsoCurve(srf, (u_domain[0], v_domain[0]), 1)

    u_len = rs.CurveLength(u_crvs[0]) if u_crvs else 100
    v_len = rs.CurveLength(v_crvs[0]) if v_crvs else 100

    # Clean up temporary analysis geometry
    if u_crvs: rs.DeleteObjects(u_crvs)
    if v_crvs: rs.DeleteObjects(v_crvs)

    # Calculate grid divisions based on target size
    u_count = max(2, int(u_len / size))
    v_count = max(2, int(v_len / size))

    rs.EnableRedraw(False)
    lines = []

    # Calculate the exact mathematical step size within the domains
    u_step = (u_domain[1] - u_domain[0]) / u_count
    v_step = (v_domain[1] - v_domain[0]) / v_count

    # 5. Iterate through the UV domain and generate geodesic paths
    for i in range(u_count):
        for j in range(v_count):
            # Calculate actual U and V parameters for the 4 corners
            u0 = u_domain[0] + (i * u_step)
            u1 = u_domain[0] + ((i + 1) * u_step)
            v0 = v_domain[0] + (j * v_step)
            v1 = v_domain[0] + ((j + 1) * v_step)

            # Evaluate the 3D points on the surface
            pt00 = rs.EvaluateSurface(srf, u0, v0)
            pt11 = rs.EvaluateSurface(srf, u1, v1)
            pt01 = rs.EvaluateSurface(srf, u0, v1)
            pt10 = rs.EvaluateSurface(srf, u1, v0)

            # Generate shortest paths (Geodesic curves) honoring surface curvature
            crv1 = rs.ShortPath(srf, pt00, pt11)
            crv2 = rs.ShortPath(srf, pt01, pt10)

            if crv1: lines.append(crv1)
            if crv2: lines.append(crv2)

    rs.EnableRedraw(True)
    if lines:
        rs.SelectObjects(lines)
    print("Grid generated: {} x {} divisions.".format(u_count, v_count))

if __name__ == "__main__":
    create_diamond_grid()