# -*- coding: utf-8 -*-
"""Rinforzo (R): a reinforcement strip of width W along a panel edge, laid on the panel without folding.
Select a panel (closed curve) and click near an edge (several in a row, Enter — done).
Like ZipCover (ZipCover.flap, inward), but inward: edge corner to corner (corner — tangent break
larger than Angle) + offset by W (default 6 cm) into the panel, ends — along the neighbouring edges
(neighbour sharper than 30° — perpendicular end). Two strips at a corner: JoinCorner on the markup lines.
Option Plus — the strip is cut longer than the edge by Plus (default 10 cm: Plus / 2 past each end, straight on),
trimmed after sewing.
The panel is not changed. Part in place, layer Parts::Reinforcements, label "R<w>" (cm;
≈ W/10, at a quarter of the edge, along the inner line) in a group. No number, no length in the label.
If the strip holds a zip — a ZipStops number whose edge midpoint is on the strip: the panel edge itself or a zip line
inside it (the old edge after ZipCover) — the label stands right after the number ("Z20  R6": two texts, each in its
own group); a zip made later on the strip pulls the label to its number, flipping the number moves the label with it.
The full part on the canvas then also carries the zip: its stops (copies) and the label "Z20 R6".
Option Layout (default Yes): on the panel — markup (only the inner line W, without panel edges and without Plus),
full part — 10000 up (ReinfCircle.add_part); No — full part in place.
B / BR (bordino, folded over the edge) are other parts, not this script.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _m in ("ReinfCircle", "ZipCover", "ZipStops"):  # Rhino keeps modules from the first run for the session
    sys.modules.pop(_m, None)
from ZipStops import RINF_LINE, beside, zip_text
from ReinfCircle import LAYER, UP_KEY, add_part, up_option, layer, off_panel, label_style, pick_style  # layer, style
from ZipCover import cm, flap, label_frame  # edge corner to corner + offset, ends along the neighbours; label along the edge

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


def ask(gp):
    """Click near an edge with options W / Plus / Angle / Layout / Style / Undo. A point, UNDO or None (Enter / Esc)."""
    unit = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 60.0 * unit), 0.001, 1e6)
    plus = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_plus", 100.0 * unit), 0.0, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get("ZipCover_angle", 30.0), 1.0, 179.0)  # shared with ZipCover
    gp.AddOptionDouble("W", w)
    gp.AddOptionDouble("Plus", plus)
    gp.AddOptionDouble("Angle", a)
    lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", True), "No", "Yes")
    gp.AddOptionToggle("Layout", lay)
    up = up_option(gp)
    i_style = gp.AddOption("Style")
    i_undo = gp.AddOption("Undo")
    while True:
        r = gp.Get()
        sc.sticky[STICKY + "_layout"] = lay.CurrentValue
        sc.sticky[UP_KEY] = up.CurrentValue
        sc.sticky[STICKY] = w.CurrentValue
        sc.sticky[STICKY + "_plus"] = plus.CurrentValue
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
  Plus — the strip is longer than the edge by this much (half past each end), trimmed after sewing
  Angle — a break larger than this angle = panel corner (the edge is taken corner to corner)
  Layout — Yes: only markup on the panel, full part `Up` up; No: full part in place
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
    made = 0
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
        w, plus, angle = sc.sticky[STICKY], sc.sticky[STICKY + "_plus"], sc.sticky["ZipCover_angle"]
        res = flap(panel, click, w, angle, normal, tol, inward=True)  # on the panel: markup
        full = flap(panel, click, w, angle, normal, tol, inward=True, plus=plus)  # for cutting: longer by Plus
        bad = next((r for r in (res, full) if not isinstance(r, tuple)), None)
        if bad:
            print(u"Skipped: %s" % bad)
            continue
        cut, edge, off, square = res
        label = u"%s%s" % (CODE, cm(w))
        style = label_style(doc, STICKY)
        plane, valign = label_place(edge, off, normal, style.TextHeight * 0.5)
        layout = sc.sticky[STICKY + "_layout"]
        zid = zip_text(cut, tol) if layout else None  # zip number on the strip (edge or zip line): R goes right after it
        te = Rhino.Geometry.TextEntity.Create(label, plane, style, False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = valign
        zip_marks = []  # the zip's stops on this edge go to the part on the canvas too (copies of the number's group)
        if zid:
            zip_marks = [rs.coercecurve(m) for g in rs.ObjectGroups(zid) or [] for m in rs.ObjectsByGroup(g) or []
                         if rs.IsCurve(m)]
        full_ids, markup = add_part(doc, [full[0]] + zip_marks, te, off_panel(cut, [panel], tol), attrs, layout)
        if layout:  # a zip made later on this strip puts the label after its number (ZipStops.finish_zip)
            rs.SetUserText(markup[-1], RINF_LINE, str(oid))
        if zid:
            beside(doc, zid, markup[-1], steps)
            rs.TextObjectText(full_ids[-1], rs.GetUserText(zid, "Zip") + u" " + label)  # canvas part: "Z20 R6"
        doc.Views.Redraw()
        print(u"%s  l=%s" % (label, cm(edge.GetLength() + plus)))  # length only in the command history
        if square:
            print(u"Warning: %d end(s) with a neighbour sharper than 30° — end is perpendicular" % square)
        made += 1
    print(u"Rinforzo: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
