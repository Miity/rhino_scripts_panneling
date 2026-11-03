# -*- coding: utf-8 -*-
"""Rinforzo (R): a reinforcement strip of width W along a panel edge, laid on the panel without folding.
Select a panel (closed curve) and click near an edge (several in a row, Enter — done).
Like ZipCover (ZipCover.flap, inward), but inward: edge corner to corner (corner — tangent break
larger than Angle) + offset by W (default 6 cm) into the panel, ends — along the neighbouring edges
(neighbour sharper than 30° — perpendicular end). Two strips at a corner: JoinCorner on the markup lines.
The panel is not changed. Part in place, layer Parts::Reinforcements, label "R<w>" (cm;
≈ W/10, at a quarter of the edge, along the inner line) in a group. No number, no length in the label.
If the strip holds a zip — a ZipStops number whose edge midpoint is on the strip: the panel edge itself or a zip line
inside it (the old edge after ZipCover) — the label stands right after the number ("Z20  R6": two texts, each in its
own group); a zip made later on the strip pulls the label to its number, flipping the number moves the label with it.
The full part on the canvas then also carries the zip: its stops (copies), the line stop to stop and the label "Z20 R6".
Option Layout (default Yes): on the panel — markup (only the inner line W, without panel edges),
full part — 10000 up (ReinfCircle.add_part); No — full part in place.
Option Seam (default Yes) — seam allowance on the full part: after the last click the view zooms to the new parts and
pattern/Seams.py runs on them (the strip contour is the sew line; click near the edges that need a seam, Width is asked there).
The contour carries UserText RF_W / RF_Angle / RF_Layout / RF_Panel: UpdateRinforzo rebuilds the strip from them.
B (bordino, folded over the edge) — Bordino.py; its label B<w> goes after R<w> (also without a zip).
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _m in ("ReinfCircle", "ZipCover", "ZipStops"):  # Rhino keeps modules from the first run for the session
    sys.modules.pop(_m, None)
from ZipStops import (EDGE, RINF_LINE, edge_of, holds, labels_after, mid_point, read_trims, stored_point, zip_span,
                      zip_text)
from ReinfCircle import LAYER, UP_KEY, add_part, up_option, layer, off_panel, label_style, pick_style  # layer, style
from ZipCover import cm, flap, label_frame  # edge corner to corner + offset, ends along the neighbours; label along the edge

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pattern"))
sys.modules.pop("Seams", None)
import Seams  # seam allowance of the full part: second step
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

STICKY = "Rinforzo"
CODE = "R"  # rinforzo


def label_place(edge, off, normal, gap):
    """(plane, vertical alignment) of the label: at a quarter of the edge, along the inner line (offset W),
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


def make(doc, oid, panel, click, w, angle, layout, normal, tol, attrs, steps):
    """One strip at the edge nearest to click: markup on the panel + full part. (full part ids, label) or None."""
    res = flap(panel, click, w, angle, normal, tol, inward=True)  # on the panel: markup
    if not isinstance(res, tuple):
        print(u"Skipped: %s" % res)
        return None
    cut, edge, off, square = res
    label = u"%s%s" % (CODE, cm(w))
    style = label_style(doc, STICKY)
    plane, valign = label_place(edge, off, normal, style.TextHeight * 0.5)
    zid = zip_text(lambda p, o: holds(cut, p, tol)) if layout else None  # zip number on the strip (edge or zip line): R goes right after it
    te = Rhino.Geometry.TextEntity.Create(label, plane, style, False, 0, 0)
    te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
    te.TextVerticalAlignment = valign
    zip_marks = []  # the zip goes to the part on the canvas too: its stops (copies of the number's group) + the line
    if zid:
        zip_marks = [rs.coercecurve(m) for g in rs.ObjectGroups(zid) or [] for m in rs.ObjectsByGroup(g) or []
                     if rs.IsCurve(m)]
        zedge = edge_of(zid, tol)[0]
        if zedge is not None:
            zip_marks.append(zip_span(zedge, read_trims(zid)))  # stop to stop
    full_ids, markup = add_part(doc, [cut] + zip_marks, te, off_panel(cut, [panel], tol), attrs, layout)
    if layout:  # a zip made later on this strip puts the label after its number (ZipStops.finish_zip)
        rs.SetUserText(markup[-1], RINF_LINE, str(oid))
    if zid:
        labels_after(doc, zid, stored_point(zid, EDGE), tol, steps)  # Z<n> R<w> (B<w> after it, if any)
        rs.TextObjectText(full_ids[-1], rs.GetUserText(zid, "Zip") + u" " + label)  # canvas part: "Z20 R6"
    elif layout:
        labels_after(doc, None, mid_point(edge), tol, steps, oid)  # no zip: B<w> / Pt<w> of this edge after R<w>
    doc.Views.Redraw()
    print(u"%s  l=%s" % (label, cm(edge.GetLength())))  # length only in the command history
    if square:
        print(u"Warning: %d end(s) with a neighbour sharper than 30° — end is perpendicular" % square)
    contour = full_ids[0]  # data for UpdateRinforzo: the strip is rebuilt from the panel and this click
    for key, value in (("W", w), ("Angle", angle), ("Layout", int(layout)), ("Panel", oid)):
        rs.SetUserText(contour, "RF_" + key, str(value))
    return full_ids, label


def ask(gp):
    """Click near an edge with options W / Angle / Layout / Seam / Style / Undo. A point, UNDO or None (Enter / Esc)."""
    unit = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 60.0 * unit), 0.001, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get("ZipCover_angle", 30.0), 1.0, 179.0)  # shared with ZipCover
    i_undo = gp.AddOption("Undo")
    gp.AddOptionDouble("W", w)
    gp.AddOptionDouble("Angle", a)
    lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", True), "No", "Yes")
    gp.AddOptionToggle("Layout", lay)
    seam = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_seam", True), "No", "Yes")
    gp.AddOptionToggle("Seam", seam)
    up = up_option(gp)
    i_style = gp.AddOption("Style")
    while True:
        r = gp.Get()
        sc.sticky[STICKY + "_layout"] = lay.CurrentValue
        sc.sticky[STICKY + "_seam"] = seam.CurrentValue
        sc.sticky[UP_KEY] = up.CurrentValue
        sc.sticky[STICKY] = w.CurrentValue
        sc.sticky["ZipCover_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_undo:
                return UNDO
            if gp.OptionIndex() == i_style:
                pick_style(sc.doc, STICKY)
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options:
  W — strip width from the edge into the panel (R<w> in the label, cm)
  Angle — a break larger than this angle = panel corner (the edge is taken corner to corner)
  Layout — Yes: only markup on the panel, full part `Up` up; No: full part in place
  Seam — Yes: after the last click the seam allowance step (Seams.py) runs on the new full parts
  Up — how far up (along CPlane Y) the full part goes with Layout=Yes; shared by all part scripts
  Style — label text style (default PAT 14 mm)
  Undo — take back the last click (again — the click before it)"""  # printed at start — visible under the option fields


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
    made, parts = 0, []
    steps = Steps(doc)
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near the edge for the reinforcement strip (Enter — done)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        if click == UNDO:
            if steps.undo():
                made -= 1
            continue
        steps.start()
        got = make(doc, oid, panel, click, sc.sticky[STICKY], sc.sticky["ZipCover_angle"],
                   sc.sticky[STICKY + "_layout"], normal, tol, attrs, steps)
        if got is None:
            continue
        parts.append(got[0][0])  # the contour of the full part
        made += 1
    if parts and sc.sticky.get(STICKY + "_seam", True):  # second step: seam allowance — the view goes to the new parts, Seams.py asks where
        rs.ZoomBoundingBox(rs.BoundingBox(parts))
        Seams.main(parts)
    print(u"Rinforzo: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
