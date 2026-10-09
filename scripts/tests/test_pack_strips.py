# -*- coding: utf-8 -*-
"""Check of PackStrips in Rhino 8 (headless document): strips 35 and 60 high (groups with a label, one with a zip line,
one loose rectangle with a loose label) → one block per width, rows no longer than the longest strip, labels and lines
moved with their strip, nothing overlaps, a text outside the strips stays; a narrow roll with Gap → rows get longer,
the block fits the roll width, the next block goes to a new column, Gap between all strips.
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_pack_strips.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_pack_strips.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Plane, Point3d, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("LayoutParts", "PackStrips", "PatternTextStyles"):
        sys.modules.pop(m, None)
    import PackStrips as P

    doc = Rhino.RhinoDoc.CreateHeadless(None)
    sc.doc = doc
    tol = 1e-6
    y = 5000.0
    owner = {}  # text / line id → its strip contour id

    def strip(length, h, group=True, line=False):
        global y
        y -= h + 37.0
        r = rs.AddRectangle(Plane(Point3d(13.0, y, 0), Vector3d.ZAxis), length, h)
        t = rs.AddText("B3.5" if h < 50 else "Z1 R6", Plane(Point3d(13.0 + length / 2.0, y + h / 2.0, 0), Vector3d.ZAxis),
                       10)
        extra = [rs.AddLine((13.0, y, 0), (13.0 + length, y, 0))] if line else []
        if group:
            rs.AddObjectsToGroup([r, t] + extra, rs.AddGroup())
        for i in [t] + extra:
            owner[str(i)] = r
        return r

    rects = [strip(l, 35.0) for l in (1825, 1780, 1620, 1615, 1330, 990, 980, 385, 380, 330, 330)]
    rects += [strip(l, 60.0, line=True) for l in (1400, 900, 500)]
    rects.append(strip(700, 35.0, group=False))  # loose rectangle + loose label inside
    stray = rs.AddText("NOTE", Plane(Point3d(-3000, -3000, 0), Vector3d.ZAxis), 10)
    every = [o.Id for o in doc.Objects]
    where = rs.coercegeometry(stray).GetBoundingBox(True).Center

    units = P.strips(doc, every)
    assert len(units) == len(rects), len(units)
    assert sorted(len(u) for u in units) == [2] * 12 + [3] * 3, sorted(len(u) for u in units)  # stray text in none

    def check(width, gap, x0, y0):
        boxes = dict((str(r), rs.coercecurve(r).GetBoundingBox(True)) for r in rects)
        for a in boxes:
            for b in boxes:
                if a < b:
                    p, q = boxes[a], boxes[b]
                    sep = max(q.Min.X - p.Max.X, p.Min.X - q.Max.X, q.Min.Y - p.Max.Y, p.Min.Y - q.Max.Y)
                    assert sep >= gap - tol, (sep, gap)  # no overlap, Gap between all strips
        for b in boxes.values():
            assert b.Min.X >= x0 - tol and b.Max.Y <= y0 + tol and b.Min.Y >= y0 - width - tol, (b.Min, b.Max)
        for i, r in owner.items():  # labels and lines moved with their strip
            c = rs.coercegeometry(i).GetBoundingBox(True).Center
            assert boxes[str(r)].Contains(c), (i, c)
        return boxes

    def block(boxes, h):
        bb = [b for b in boxes.values() if abs(b.Max.Y - b.Min.Y - h) < tol]
        return min(b.Min.X for b in bb), max(b.Max.X for b in bb), min(b.Min.Y for b in bb), max(b.Max.Y for b in bb)

    rep = P.pack(doc, units, Plane.WorldXY, Point3d(0, 0, 0), 1500.0, 0.0)
    assert [(h, n) for h, n, r, l, t in rep] == [(60.0, 3), (35.0, 12)], rep  # widest strips first
    assert rep[0][2] == 2 and abs(rep[0][3] - 1400) < tol, rep  # 1400 | 900 500
    assert abs(rep[1][3] - 1825) < tol, rep  # rows no longer than the longest strip
    boxes = check(1500.0, 0.0, 0.0, 0.0)
    x0, x1, y0, y1 = block(boxes, 35.0)
    assert abs(x0) < tol and abs(y1 + 120.0) < tol and abs(y1 - y0 - rep[1][4]) < tol, (x0, y1, y0)  # under the 60 block
    assert rs.coercegeometry(stray).GetBoundingBox(True).Center.DistanceTo(where) < tol  # not a strip: not moved

    rep = P.pack(doc, P.strips(doc, every), Plane.WorldXY, Point3d(100, 50, 0), 200.0, 10.0)
    assert rep[0][2] == 3 and rep[0][4] <= 200.0 + tol, rep  # 60: 900 + 10 + 500 > 1400 → three rows, just fit
    assert rep[1][2] <= 4 and rep[1][4] <= 200.0 + tol and rep[1][3] > 1825, rep  # 35: four rows at most, longer rows
    boxes = check(200.0, 10.0, 100.0, 50.0)
    x0, x1, y0, y1 = block(boxes, 35.0)
    assert abs(x0 - (100 + 1400 + 10)) < tol and abs(y1 - 50) < tol, (x0, y1)  # next column, Gap after the 60 block
    out.write("OK\n%r\n" % (rep,))
except Exception:
    out.write(traceback.format_exc())
out.close()
