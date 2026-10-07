# -*- coding: utf-8 -*-
"""Seam allowance — a separate part outside the panel.
Like ZipCover: select a panel (closed curve) and click near an edge (several in a row, Enter — done).
Edge — corner to corner (corner — a break larger than Angle); part — edge + offset by W outward,
ends along the extension of the neighbouring edges (geometry — ZipCover.flap). Part + label "SA <W>" in a group,
layer Parts::Seam. The panel is not changed.
Option Points=Yes: also seam points (logic of markup/sewing_points.py: centre ± k·Step) on a copy of the edge
in Parts::Seam — copy + points in the same group as the part.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Plane, Vector3d

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
sys.modules.pop("PatternTextStyles", None)  # Rhino keeps modules from the first run for the session
from PatternTextStyles import label_style, pick_style  # label style: option Style, default PAT 14 mm
from sewing_points import sewing_lengths  # the same markup/ in sys.path

STICKY = "Seam"
LAYER = "Parts::Seam"


def label_frame(crv, offset, normal):
    """Point in the middle of the strip and direction along the edge (text reads left to right)."""
    ok, t = crv.LengthParameter(crv.GetLength() / 2.0)
    t = t if ok else crv.Domain.Mid
    m = crv.PointAt(t)
    q = offset.PointAt(offset.ClosestPoint(m)[1])
    u = crv.TangentAt(t)
    if u.X < -1e-9 or (abs(u.X) < 1e-9 and u.Y < 0):
        u = -u
    return Plane((m + q) / 2.0, u, Vector3d.CrossProduct(normal, u))


def ask(gp):
    """Click near an edge with options W / Angle / Points / Step / Layout / Style. A point or None (Enter / Esc)."""
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 10.0), 0.001, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    pts = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_points", False), "No", "Yes")
    step = Rhino.Input.Custom.OptionDouble(sc.sticky.get("sew_step", 20.0), 0.001, 1e6)  # shared with sewing_points
    gp.AddOptionDouble("W", w)
    gp.AddOptionDouble("Angle", a)
    gp.AddOptionToggle("Points", pts)
    gp.AddOptionDouble("Step", step)
    lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", True), "No", "Yes")
    gp.AddOptionToggle("Layout", lay)
    i_style = gp.AddOption("Style")
    while True:
        r = gp.Get()
        sc.sticky[STICKY + "_layout"] = lay.CurrentValue
        sc.sticky[STICKY] = w.CurrentValue
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        sc.sticky[STICKY + "_points"] = pts.CurrentValue
        sc.sticky["sew_step"] = step.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_style:
                pick_style(sc.doc, STICKY)
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


def sewing_geometry(crv, step):
    """Copy of the edge (seam line) + seam points on it (as sewing_points) — geometry."""
    out = [crv.DuplicateCurve()]
    for s in sewing_lengths(crv.GetLength(), step):
        ok, t = crv.LengthParameter(s)
        if ok:
            out.append(Rhino.Geometry.Point(crv.PointAt(t)))
    return out


def add_sewing_points(doc, crv, step, attrs):
    """Copy of the edge (seam line) + seam points on it, both with attrs (layer Parts::Seam)."""
    return [doc.Objects.Add(g, attrs) for g in sewing_geometry(crv, step)]


HELP = u"""Options:
  W — seam allowance width: offset from the edge outward from the panel
  Angle — a break larger than this angle = panel corner (the edge is taken corner to corner)
  Points — Yes: also seam points on a copy of the edge
  Step — seam point spacing (from the edge centre both ways)
  Layout — Yes: only markup on the panel, full part 10000 up; No: full part in place
  Style — label text style (default PAT 14 mm)"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    from ZipCover import flap  # here, not at the top: ZipCover itself imports label_frame / label_style from Seam
    sys.modules.pop("ReinfCircle", None)  # Rhino caches modules per session
    from ReinfCircle import add_part, off_panel  # Layout: markup in place + part above
    doc = sc.doc
    oid = rs.GetObject(u"Select a panel (closed curve)", rs.filter.curve, preselect=True)
    if not oid:
        return
    panel = rs.coercecurve(oid)
    tol = doc.ModelAbsoluteTolerance
    ok, plane = panel.TryGetPlane(tol)
    normal = plane.ZAxis if ok else rs.ViewCPlane().ZAxis
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Seam", parent="Parts")
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(LAYER, -1)
    made = n_pts = 0
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near the edge for the seam allowance (Enter — done)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        w, angle = sc.sticky[STICKY], sc.sticky[STICKY + "_angle"]
        res = flap(panel, click, w, angle, normal, tol)
        if not isinstance(res, tuple):
            print(u"Skipped: %s" % res)
            continue
        crv, edge, off, square = res
        te = Rhino.Geometry.TextEntity.Create(u"SA %g" % w, label_frame(edge, off, normal),
                                              label_style(doc, STICKY), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        full = [crv]
        if sc.sticky[STICKY + "_points"]:
            pts = sewing_geometry(edge, sc.sticky["sew_step"])
            full += pts
            n_pts += len(pts) - 1
        add_part(doc, full, te, off_panel(crv, [panel], tol), attrs, sc.sticky[STICKY + "_layout"])
        made += 1
        if square:
            print(u"Warning: %d end(s) with a neighbour sharper than 30° — end is perpendicular" % square)
        doc.Views.Redraw()
    print(u"Seam allowance: %d parts → %s" % (made, LAYER))
    if n_pts:
        print(u"Seam points: %d on edge copies in %s" % (n_pts, LAYER))


if __name__ == "__main__":
    main()
