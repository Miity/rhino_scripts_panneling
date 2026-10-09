# -*- coding: utf-8 -*-
"""Pack strips into a compact rectangle on the roll: after Layout Stack / Strips, before nesting.
Select strips already lying along CPlane X (Layout Stack copies, fascia strips…; a window is fine). A strip = a group
of the selection, or a closed curve with the loose selected objects inside it (label, zip lines). Only strips with a
straight top and bottom along CPlane X are packed (within SLACK_MM — DXF panel edges are not quite straight; the ends may
be slanted: rectangles, trapezoids, arrows), by their box; the others — curved, tilted — are not moved, their labels are
listed in the command history. Strips are only moved, never turned (the grain stays). One block per strip width (within
SLACK_MM, rows as high as the widest): rows as long as the longest strip, each strip in the
first row it fits (longest first); if the rows do not fit into the roll Width, the rows get longer — the shortest
length at which they fit. Blocks go down from the click point (top-left corner), widest strips first; a block that does
not fit into the rest of the roll width starts a new column to the right. Gap — between strips, rows and blocks
(0 — touching). Enter instead of a click — in place, from the top-left corner of the selection. Sizes in the command
history (cm).
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Plane, Transform

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("LayoutParts", None)  # Rhino keeps modules from the first run for the session
from LayoutParts import closed, outer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
sys.modules.pop("PatternTextStyles", None)
from PatternTextStyles import cm  # sizes in cm

STICKY = "PackStrips"
SLACK_MM = 4.0  # top / bottom this close to a straight line = straight; widths this close = one block


def strips(doc, ids):
    """Strips of the selection: [[objects]] — a group (its selected members), or a closed curve with the loose selected
    objects whose middle is inside its box. Objects of no strip are not moved."""
    groups, loose = {}, []
    for i in ids:
        o = doc.Objects.FindId(i)
        g = rs.ObjectTopGroup(i)
        if g:
            groups.setdefault(g, []).append(o)
        elif closed(o.Geometry):
            groups[str(i)] = [o]
        else:
            loose.append(o)
    units = [u for u in groups.values() if any(closed(o.Geometry) for o in u)]
    for o in loose:
        c = o.Geometry.GetBoundingBox(True).Center
        u = next((u for u in units if outer(u).GetBoundingBox(True).Contains(c)), None)
        if u is not None:
            u.append(o)
    return units


def is_flat(u, plane, tol):
    """Top and bottom of the strip u are straight along plane X within tol (the ends may be slanted): straight pieces of
    its contour lie on its box's top and on its bottom line over at least half the box length each."""
    c = outer(u)
    xf = Transform.PlaneToPlane(plane, Plane.WorldXY)
    b = c.GetBoundingBox(xf)
    on = [0.0, 0.0]
    for s in c.DuplicateSegments() or [c]:
        p, q = xf * s.PointAtStart, xf * s.PointAtEnd
        for k, y in enumerate((b.Min.Y, b.Max.Y)):
            if s.IsLinear(tol) and abs(p.Y - y) <= tol and abs(q.Y - y) <= tol:
                on[k] += abs(q.X - p.X)
    return min(on) >= (b.Max.X - b.Min.X) / 2.0


def rows_of(lengths, L, gap, tol):
    """First fit decreasing: rows (lists of indices into lengths), each no longer than L."""
    rows = []  # [used length, [indices]]
    for i in sorted(range(len(lengths)), key=lambda i: -lengths[i]):
        r = next((r for r in rows if r[0] + gap + lengths[i] <= L + tol), None)
        if r is None:
            rows.append([lengths[i], [i]])
        else:
            r[0] += gap + lengths[i]
            r[1].append(i)
    return [r[1] for r in rows]


def block(lengths, h, width, gap, tol):
    """Rows of one block: the shortest row length, not below the longest strip, at which the rows fit into width.
    ponytail: first fit decreasing + bisection on the length — near the best for tens of strips, not proven optimal."""
    n = max(1, int((width + gap + tol) // (h + gap)))  # rows across the roll
    lo, hi = max(lengths), sum(lengths) + gap * (len(lengths) - 1)
    if len(rows_of(lengths, lo, gap, tol)) <= n:
        return rows_of(lengths, lo, gap, tol)
    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        if len(rows_of(lengths, mid, gap, tol)) <= n:
            hi = mid
        else:
            lo = mid
    return rows_of(lengths, hi, gap, tol)


def pack(doc, units, plane, start, width, gap):
    """Moves the strips (units) into blocks down from start (top-left corner).
    Returns [(strip width, strips, rows, block length, block height)]."""
    tol = doc.ModelAbsoluteTolerance
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    to_plane = Transform.PlaneToPlane(plane, Plane.WorldXY)  # boxes in CPlane coordinates
    boxes = [outer(u).GetBoundingBox(to_plane) for u in units]
    size = [(b.Max.X - b.Min.X, b.Max.Y - b.Min.Y) for b in boxes]
    blocks = []  # [height, [strip indices]], widest strips first
    for i in sorted(range(len(units)), key=lambda i: -size[i][1]):
        if blocks and blocks[-1][0] - size[i][1] <= SLACK_MM * mm:  # ponytail: one row height (the widest) per block
            blocks[-1][1].append(i)
        else:
            blocks.append([size[i][1], [i]])
    ok, x0, y0 = plane.ClosestParameter(start)
    x, y, col = x0, y0, 0.0  # col — the longest block of the current column
    report = []
    for h, idx in blocks:
        rows = [[idx[j] for j in r] for r in block([size[i][0] for i in idx], h, width, gap, tol)]
        tall = len(rows) * (h + gap) - gap
        if y < y0 - tol and y0 - y + tall > width + tol:  # does not fit under the previous block: next column
            x, y, col = x + col + gap, y0, 0.0
        long = 0.0
        for r, row in enumerate(rows):
            cx = x
            for i in row:
                b = boxes[i]
                rs.MoveObjects([o.Id for o in units[i]],
                               plane.XAxis * (cx - b.Min.X) + plane.YAxis * (y - r * (h + gap) - b.Max.Y))
                cx += size[i][0] + gap
            long = max(long, cx - gap - x)
        col = max(col, long)
        y -= tall + gap
        report.append((h, len(idx), len(rows), long, tall))
    return report


HELP = u"""Options:
  Width — roll width: the layout goes down from the click no more than this; rows get longer if needed
  Gap — space between the strips, the rows and the blocks (0 — touching)
  Enter instead of a click — pack in place, from the top-left corner of the selection"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select the strips (lying along CPlane X; window allowed)", preselect=True)
    if not ids:
        return
    plane = rs.ViewCPlane()
    tol = doc.ModelAbsoluteTolerance
    slack = SLACK_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    units, odd = [], []
    for u in strips(doc, ids):
        (units if is_flat(u, plane, slack) else odd).append(u)
    if odd:
        names = [o.Geometry.PlainText for u in odd for o in u if isinstance(o.Geometry, Rhino.Geometry.TextEntity)]
        print(u"Top / bottom not straight, not moved: %d (%s)" % (len(odd), u", ".join(names) or u"no labels"))
    if not units:
        print(u"No strips with a straight top and bottom in the selection")
        return
    unit = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Point to pack from (top-left corner; Enter — in place)")
    gp.AcceptNothing(True)
    width = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_width", 1500.0 * unit), 0.001, 1e7)
    gap = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_gap", 0.0), 0.0, 1e6)
    gp.AddOptionDouble("Width", width)
    gp.AddOptionDouble("Gap", gap)
    while gp.Get() == Rhino.Input.GetResult.Option:
        pass
    sc.sticky[STICKY + "_width"] = width.CurrentValue
    sc.sticky[STICKY + "_gap"] = gap.CurrentValue
    if gp.CommandResult() != Rhino.Commands.Result.Success:
        return
    if gp.Result() == Rhino.Input.GetResult.Point:
        start = gp.Point()
    else:  # in place: the top-left corner of the selected strips
        to_plane = Transform.PlaneToPlane(plane, Plane.WorldXY)
        bbs = [outer(u).GetBoundingBox(to_plane) for u in units]
        start = plane.PointAt(min(b.Min.X for b in bbs), max(b.Max.Y for b in bbs))
    rs.EnableRedraw(False)
    try:
        report = pack(doc, units, plane, start, width.CurrentValue, gap.CurrentValue)
    finally:
        rs.EnableRedraw(True)
    for h, n, rows, long, tall in report:
        print(u"Strips %s cm: %d in %d rows, block %s × %s cm" % (cm(h), n, rows, cm(long), cm(tall)))
        if tall > width.CurrentValue + tol:
            print(u"Warning: a strip is wider than the roll — the block is taller than Width")


if __name__ == "__main__":
    main()
