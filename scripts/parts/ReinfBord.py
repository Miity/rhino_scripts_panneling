# -*- coding: utf-8 -*-
"""Reinforced border: a reinforcement strip of height H along a panel edge, inside the panel.
Select a panel (closed curve) and click near an edge (several in a row, Enter — done).
Like ZipCover (ZipCover.flap, inward), but inward: edge corner to corner (corner — tangent break
larger than Angle) + offset by H (default 6 cm; sometimes 10) into the panel, ends — along the neighbouring edges
(neighbour sharper than 30° — perpendicular end). Two strips at a corner are joined by JoinCorner.
Option SA — seam allowance on the inner edge (default 0): cut at H + SA, seam line at H, in the group.
The panel is not changed. Part in place, layer Parts::Reinforcements, label "RB<n>  H=…" (≈ H/10, at a quarter of the edge, along the inner line) in a group;
RB numbering continues between runs.
Option Layout (default Yes): on the panel — markup (only the inner line H, without panel edges), full part —
10000 up (ReinfCircle.add_part); No — full part in place.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _m in ("ReinfCircle", "Seam", "ZipCover"):  # Rhino keeps modules from the first run for the session
    sys.modules.pop(_m, None)
from ReinfCircle import LAYER, add_part, layer, next_number, off_panel, text_style  # layer, numbering, PAT style ≈ H/10
from Seam import label_frame  # label direction along the edge (reads left to right)
from ZipCover import flap  # edge corner to corner + offset, ends along the neighbouring edges

STICKY = "ReinfBord"
PREFIX = "RB"  # Reinforced Border


def border(panel, click, h, sa, angle, normal, tol):
    """(cut, [seam lines], edge, offset by H, number of perpendicular ends) or an error string."""
    res = flap(panel, click, h + sa, angle, normal, tol, inward=True)
    if not isinstance(res, tuple) or sa <= 0:
        return res if not isinstance(res, tuple) else (res[0], [], res[1], res[2], res[3])
    cut, edge, _, square = res
    strip = flap(panel, click, h, angle, normal, tol, inward=True)
    if not isinstance(strip, tuple):
        return strip
    crv, _, off, _ = strip
    # seam — edge of the H strip not lying on the edge and the neighbouring sides (i.e. not on the cut)
    seams = [g for g in crv.DuplicateSegments() or []
             if any(cut.PointAt(cut.ClosestPoint(g.PointAtNormalizedLength(t))[1])
                    .DistanceTo(g.PointAtNormalizedLength(t)) > tol for t in (0.25, 0.5, 0.75))]
    return cut, list(Curve.JoinCurves(seams, tol)) if seams else [], edge, off, square


def label_place(edge, off, normal, gap):
    """(plane, vertical alignment) of the label: at a quarter of the edge, along the inner line (offset H),
    on the strip side at distance gap — the middle of the edge already has ZipCover / ZipStops labels."""
    half = edge.Trim(edge.Domain.T0, edge.LengthParameter(edge.GetLength() / 2.0)[1]) or edge
    plane = label_frame(half, off, normal)
    ok, t = half.LengthParameter(half.GetLength() / 2.0)
    m = half.PointAt(t if ok else half.Domain.Mid)
    q = off.PointAt(off.ClosestPoint(m)[1])
    toward = m - q  # from the inner line to the edge, i.e. into the strip
    toward.Unitize()
    plane.Origin = q + toward * gap
    up = plane.YAxis * toward > 0
    return plane, (Rhino.DocObjects.TextVerticalAlignment.Bottom if up else Rhino.DocObjects.TextVerticalAlignment.Top)


def ask(gp):
    """Click near an edge with options H / SA / Angle / Layout. A point or None (Enter / Esc)."""
    unit = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    h = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 60.0 * unit), 0.001, 1e6)
    sa = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_sa", 0.0), 0.0, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get("ZipCover_angle", 30.0), 1.0, 179.0)  # shared with ZipCover
    gp.AddOptionDouble("H", h)
    gp.AddOptionDouble("SA", sa)
    gp.AddOptionDouble("Angle", a)
    lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", True), "No", "Yes")
    gp.AddOptionToggle("Layout", lay)
    while True:
        r = gp.Get()
        sc.sticky[STICKY + "_layout"] = lay.CurrentValue
        sc.sticky[STICKY] = h.CurrentValue
        sc.sticky[STICKY + "_sa"] = sa.CurrentValue
        sc.sticky["ZipCover_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options:
  H — strip height from the edge into the panel
  SA — seam allowance on the inner edge of the strip (0 — none)
  Angle — a break larger than this angle = panel corner (the edge is taken corner to corner)
  Layout — Yes: only markup on the panel, full part 10000 up; No: full part in place"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    oid = rs.GetObject(u"Select a panel (closed curve)", rs.filter.curve, preselect=True)
    if not oid:
        return
    panel = rs.coercecurve(oid)
    tol = doc.ModelAbsoluteTolerance
    ok, plane = panel.TryGetPlane(tol)
    normal = plane.ZAxis if ok else rs.ViewCPlane().ZAxis
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer(), -1)
    n = next_number(LAYER, PREFIX)
    made = 0
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near the edge for the reinforced border (Enter — done)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        h, sa = sc.sticky[STICKY], sc.sticky[STICKY + "_sa"]
        res = border(panel, click, h, sa, sc.sticky["ZipCover_angle"], normal, tol)
        if not isinstance(res, tuple):
            print(u"Skipped: %s" % res)
            continue
        cut, seams, edge, off, square = res
        label = u"%s%d  H=%g" % (PREFIX, n, h)
        style = text_style(doc, h)
        plane, valign = label_place(edge, off, normal, style.TextHeight * 0.5)
        te = Rhino.Geometry.TextEntity.Create(label, plane, style, False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = valign
        add_part(doc, [cut] + seams, te, seams or off_panel(cut, [panel], tol), attrs,
                 sc.sticky[STICKY + "_layout"])  # seam = line H on the panel
        doc.Views.Redraw()
        print(label)
        if square:
            print(u"Warning: %d end(s) with a neighbour sharper than 30° — end is perpendicular" % square)
        n += 1
        made += 1
    print(u"Reinforced border: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
