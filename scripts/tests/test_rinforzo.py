# -*- coding: utf-8 -*-
"""Check of Rinforzo (ZipCover.flap inward, Plus, label place) in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_rinforzo.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_rinforzo.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ZipCover", "Rinforzo"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import Rinforzo as M

    Z, tol = Vector3d.ZAxis, 0.001
    def poly(*xy):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in xy + (xy[0],)]))
    area = lambda c: AreaMassProperties.Compute(c).Area
    strip = lambda panel, click, plus=0.0: M.flap(panel, click, 60, 30, Z, tol, inward=True, plus=plus)
    # rectangle 500×300, right edge, W 60 → strip 60×300 inside
    panel = poly((0, 0), (500, 0), (500, 300), (0, 300))
    cut = strip(panel, Point3d(510, 150, 0))[0]
    bb = cut.GetBoundingBox(True)
    assert cut.IsClosed and abs(area(cut) - 18000) < 1e-2, area(cut)
    assert abs(bb.Min.X - 440) < 1e-3 and abs(bb.Max.X - 500) < 1e-3, bb
    # Plus 100 → 50 past each end: 60×400, y −50…350
    cut = strip(panel, Point3d(510, 150, 0), 100)[0]
    bb = cut.GetBoundingBox(True)
    assert cut.IsClosed and abs(area(cut) - 24000) < 1e-2, area(cut)
    assert abs(bb.Min.Y + 50) < 1e-3 and abs(bb.Max.Y - 350) < 1e-3, bb
    # same side, clockwise panel (other direction) — also inward
    panel_cw = poly((0, 0), (0, 300), (500, 300), (500, 0))
    cut = strip(panel_cw, Point3d(510, 150, 0))[0]
    assert abs(area(cut) - 18000) < 1e-2
    # bevel: top horizontal, right edge slanted → strip trimmed by top and bottom, inside the panel
    panel = poly((0, 0), (400, 0), (500, 300), (0, 300))
    cut = strip(panel, Point3d(460, 150, 0))[0]
    bb = cut.GetBoundingBox(True)
    assert cut.IsClosed and bb.Min.Y > -1e-3 and bb.Max.Y < 300 + 1e-3 and bb.Max.X < 500 + 1e-3, bb
    L = (100 ** 2 + 300 ** 2) ** 0.5
    assert abs(area(cut) - 60 * L) < 1, area(cut)  # parallelogram between horizontals
    cut = strip(panel, Point3d(460, 150, 0), 100)[0]  # Plus: same parallelogram, longer by 100 along the edge
    assert cut.IsClosed and abs(area(cut) - 60 * (L + 100)) < 1, area(cut)
    # label: at a quarter of the edge, on the strip side near the inner line (x=440), text grows towards the edge
    rect = poly((0, 0), (500, 0), (500, 300), (0, 300))
    cut, edge, off, _ = strip(rect, Point3d(510, 150, 0))
    pl, va = M.label_place(edge, off, Z, 3)
    assert abs(pl.Origin.X - 443) < 1e-3 and abs(pl.Origin.Y - 75) < 1e-3, pl.Origin
    import Rhino
    TV = Rhino.DocObjects.TextVerticalAlignment
    assert (va == TV.Bottom) == (pl.YAxis.X > 0), (va, pl.YAxis)
    # neighbouring edge — a polyline (break 4.8° < Angle, 20 from the corner): the end follows the panel, not the tangent;
    # markup (off_panel) — only the inner line x=440, ends on the panel are not duplicated
    panel = poly((0, 0), (500, 0), (500, 300), (480, 300), (0, 340))
    cut = strip(panel, Point3d(510, 150, 0))[0]
    top = 300 + 40 * 40 / 480.0
    assert cut.IsClosed and abs(cut.GetBoundingBox(True).Max.Y - top) < 1e-3, cut.GetBoundingBox(True)
    assert abs(area(cut) - (60 * 300 + 40 * 40 / 2 * 40 / 480.0)) < 1e-2, area(cut)  # + triangle under the bevel
    mk = M.off_panel(cut, [panel], tol)
    assert len(mk) == 1 and abs(mk[0].GetLength() - top) < 1e-3, [c.GetLength() for c in mk]
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
