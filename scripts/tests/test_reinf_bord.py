# -*- coding: utf-8 -*-
"""Check of ReinfBord.border in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_reinf_bord.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_reinf_bord.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "Seam", "ZipCover", "ReinfBord", "JoinCorner"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import ReinfBord as M
    import JoinCorner

    Z, tol = Vector3d.ZAxis, 0.001
    def poly(*xy):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in xy + (xy[0],)]))
    area = lambda c: AreaMassProperties.Compute(c).Area
    # rectangle 500×300, right edge, H 60 → strip 60×300 inside
    panel = poly((0, 0), (500, 0), (500, 300), (0, 300))
    cut, seams, edge, off, sq = M.border(panel, Point3d(510, 150, 0), 60, 0, 30, Z, tol)
    bb = cut.GetBoundingBox(True)
    assert cut.IsClosed and abs(area(cut) - 18000) < 1e-2 and not seams, area(cut)
    assert abs(bb.Min.X - 440) < 1e-3 and abs(bb.Max.X - 500) < 1e-3, bb
    # same side, clockwise panel (other direction) — also inward
    panel_cw = poly((0, 0), (0, 300), (500, 300), (500, 0))
    cut = M.border(panel_cw, Point3d(510, 150, 0), 60, 0, 30, Z, tol)[0]
    assert abs(area(cut) - 18000) < 1e-2
    # SA 10: cut 70×300, seam — line x=440 of length 300
    cut, seams, _, _, _ = M.border(panel, Point3d(510, 150, 0), 60, 10, 30, Z, tol)
    assert abs(area(cut) - 21000) < 1e-2 and len(seams) == 1 and abs(seams[0].GetLength() - 300) < 1e-3
    assert abs(seams[0].PointAtStart.X - 440) < 1e-3
    # bevel (as in the photo): top horizontal, right edge slanted → strip trimmed by top and bottom, inside the panel
    panel = poly((0, 0), (400, 0), (500, 300), (0, 300))
    cut = M.border(panel, Point3d(460, 150, 0), 60, 0, 30, Z, tol)[0]
    bb = cut.GetBoundingBox(True)
    assert cut.IsClosed and bb.Min.Y > -1e-3 and bb.Max.Y < 300 + 1e-3 and bb.Max.X < 500 + 1e-3, bb
    L = (100 ** 2 + 300 ** 2) ** 0.5
    assert abs(area(cut) - 60 * L) < 1, area(cut)  # parallelogram between horizontals
    # label: at a quarter of the edge, on the strip side near the inner line (x=440), text grows towards the edge
    rect = poly((0, 0), (500, 0), (500, 300), (0, 300))
    cut, _, edge, off, _ = M.border(rect, Point3d(510, 150, 0), 60, 0, 30, Z, tol)
    pl, va = M.label_place(edge, off, Z, 3)
    assert abs(pl.Origin.X - 443) < 1e-3 and abs(pl.Origin.Y - 75) < 1e-3, pl.Origin
    import Rhino
    TV = Rhino.DocObjects.TextVerticalAlignment
    assert (va == TV.Bottom) == (pl.YAxis.X > 0), (va, pl.YAxis)
    # neighbouring edge — a polyline (break 4.8° < Angle, 20 from the corner): the end follows the panel, not the tangent;
    # markup (off_panel) — only the inner line x=440, ends on the panel are not duplicated
    panel = poly((0, 0), (500, 0), (500, 300), (480, 300), (0, 340))
    cut = M.border(panel, Point3d(510, 150, 0), 60, 0, 30, Z, tol)[0]
    top = 300 + 40 * 40 / 480.0
    assert cut.IsClosed and abs(cut.GetBoundingBox(True).Max.Y - top) < 1e-3, cut.GetBoundingBox(True)
    assert abs(area(cut) - (60 * 300 + 40 * 40 / 2 * 40 / 480.0)) < 1e-2, area(cut)  # + triangle under the bevel
    from ReinfCircle import off_panel
    mk = off_panel(cut, [panel], tol)
    assert len(mk) == 1 and abs(mk[0].GetLength() - top) < 1e-3, [c.GetLength() for c in mk]
    cut, seams = M.border(panel, Point3d(510, 150, 0), 60, 10, 30, Z, tol)[:2]  # SA: seam — also only line H
    assert len(seams) == 1 and abs(seams[0].GetLength() - top) < 1e-3, [c.GetLength() for c in seams]
    # JoinCorner: strips on the right and top edges overlap at the corner → one L-shaped part
    panel = poly((0, 0), (500, 0), (500, 300), (0, 300))
    a = M.border(panel, Point3d(510, 150, 0), 60, 0, 30, Z, tol)[0]
    b = M.border(panel, Point3d(250, 310, 0), 60, 0, 30, Z, tol)[0]
    j = JoinCorner.join(a, b, Point3d(490, 290, 0), tol)
    assert isinstance(j, list) and len(j) == 1 and j[0].IsClosed, j
    assert abs(area(j[0]) - (18000 + 30000 - 3600)) < 1e-2, area(j[0])
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
