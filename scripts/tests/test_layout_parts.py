# -*- coding: utf-8 -*-
"""Check of LayoutParts.layout (canvas) in Rhino 8 (headless document):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_layout_parts.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_layout_parts.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Plane, Point3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    sys.modules.pop("LayoutParts", None)
    import LayoutParts as M

    def T(text, x, y, h):
        return rs.AddText(text, Plane(Point3d(x, y, 0), Rhino.Geometry.Vector3d.ZAxis), h)

    doc = Rhino.RhinoDoc.CreateHeadless(None)
    sc.doc = doc
    rs.AddLayer("Parts")
    rs.AddLayer("Panels", parent="Parts")
    rs.AddLayer("Zip", parent="Parts")
    rs.CurrentLayer("Parts::Panels")
    # panel 0..100 x 0..100: contour + hole + label + TextDot, one group
    panel = rs.AddRectangle(Plane.WorldXY, 100, 100)
    hole = rs.AddCircle((50, 50, 0), 5)
    lbl = T("P4", 80, 80, 5)
    dot = rs.AddTextDot("P4", (-5, 105, 0))
    rs.AddObjectsToGroup([panel, hole, lbl, dot], rs.AddGroup())
    # markup on the panel (separate objects): seam points, a cross, a circle, labels, zip line on the edge, stop
    pts = [rs.AddPoint((x, 0, 0)) for x in (30, 50, 70)]
    cross = [rs.AddLine((20, 20, 0), (22, 20, 0)), rs.AddLine((21, 19, 0), (21, 21, 0))]
    rs.AddObjectsToGroup(cross, rs.AddGroup())
    circ = rs.AddCircle((40, 40, 0), 1)
    rs.CurrentLayer("Parts::Zip")
    zipl = rs.AddLine((100, 0, 0), (100, 100, 0))          # on the right edge → tick into the panel
    inner = rs.AddLine((10, 60, 0), (90, 60, 0))           # inside → tick across
    stop = rs.AddLine((95, 10, 0), (105, 10, 0))           # short → no tick
    ztxt = T("Z15", 90, 50, 5)
    long_txt = T("CZ 20", 50, 90, 5)         # no code → not copied
    # detail far above: closed contour + open seam line + label "RC3  r=4"
    rs.CurrentLayer("Parts::Panels")
    det = rs.AddRectangle(Plane(Point3d(0, 1000, 0), Rhino.Geometry.Vector3d.ZAxis), 40, 20)
    seam = rs.AddLine((0, 1005, 0), (40, 1005, 0))
    dlbl = T("RC3  r=4", 10, 1010, 3)
    rs.AddObjectsToGroup([det, seam, dlbl], rs.AddGroup())

    sel = [panel, dot, circ, zipl, inner, stop, ztxt, long_txt, det] + pts + cross
    new, skipped = M.layout(doc, sel, 10.0, Plane.WorldXY, Point3d(0, 2000, 0), 20.0)
    assert skipped == 0, skipped
    objs = [doc.Objects.FindId(i) for i in new]
    texts = sorted(o.Geometry.PlainText for o in objs if isinstance(o.Geometry, Rhino.Geometry.TextEntity))
    assert texts == ["P4", "RC3", "Z15"], texts
    assert not [o for o in objs if isinstance(o.Geometry, Rhino.Geometry.TextDot)]
    assert len([o for o in objs if isinstance(o.Geometry, Rhino.Geometry.Point)]) == 3
    lines = [o.Geometry for o in objs if isinstance(o.Geometry, Rhino.Geometry.Curve) and o.Geometry.IsLinear()
             and not o.Geometry.IsClosed]
    # 2 cross lines + 2 ticks (edge, inner); no zip line itself, no stop, no seam line
    assert len(lines) == 4, len(lines)
    ticks = [c for c in lines if abs(c.GetLength() - 20) < 1e-6]
    assert len(ticks) == 2, [c.GetLength() for c in lines]
    closed = [o.Geometry for o in objs if isinstance(o.Geometry, Rhino.Geometry.Curve) and o.Geometry.IsClosed]
    assert len(closed) == 4, len(closed)  # panel, hole, circle mark, detail
    # panel copy at the click, detail to the right after the gap
    pc = [o for o in objs if str(o.Attributes.GetUserString(M.KEY)) == str(panel)][0]
    bb = pc.Geometry.GetBoundingBox(True)
    assert abs(bb.Min.X) < 1e-6 and abs(bb.Min.Y - 2000) < 1e-6, bb.Min
    # edge tick: from x=100 inward to x=80 (panel copy is at y 2000..2100)
    et = [c for c in ticks if abs(c.PointAtStart.Y - c.PointAtEnd.Y) < 1e-6 and abs(c.PointAtStart.Y - 2050) < 1e-6][0]
    assert sorted([et.PointAtStart.X, et.PointAtEnd.X]) == [80, 100], (et.PointAtStart, et.PointAtEnd)
    it = [c for c in ticks if c is not et][0]
    assert sorted([it.PointAtStart.Y, it.PointAtEnd.Y]) == [2050, 2070], (it.PointAtStart, it.PointAtEnd)
    dc = [o for o in objs if str(o.Attributes.GetUserString(M.KEY)) == str(det)][0]
    assert dc.Geometry.GetBoundingBox(True).Min.X >= 110 - 1e-6  # after the panel (+ its labels) and the gap
    assert all(doc.Layers[o.Attributes.LayerIndex].FullPath.endswith("::Layout") for o in objs)
    assert rs.ObjectLayer(panel) == "Parts::Panels" and rs.IsObject(zipl)  # originals untouched
    # repeated run: skipped
    again, skipped = M.layout(doc, sel, 10.0, Plane.WorldXY)
    assert not again and skipped == 2, (again, skipped)
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
