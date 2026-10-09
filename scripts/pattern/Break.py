# -*- coding: utf-8 -*-
"""Break — break points on panel contours, after PatternSmith (Pattern Editor > Design > Edit Tools > Break).
A break point splits a panel edge (corner to corner) into two edges, as a corner does: Seams gives each its own
seam width and corner style, Notches counts From / Mid / Repeat… on each, Convert Notches takes the nearest one.
Select panels (closed curves = sew lines), then click on a contour (snaps work; several in a row, Enter — done):
a break point there — the point of the contour nearest the click; a click on a break point (within Pick) — removes it.
Layer Pattern::Breaks, UserText Break, in the panel's groups (moves with it); the scripts find the points on the
panel by geometry — no ids. A panel that already has a seam: its widths are read off the cut line again
(the edges are numbered anew), the corner styles go back to Extend — set them again in Seams if needed.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Point

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.modules.pop("Seams", None)  # Rhino keeps modules from the first run for the session
from Seams import BREAK, BREAKS, KEY, MATCH_MM, NOTCH, PARENT, break_objects, close_panel, layer_attrs
sys.path.insert(0, os.path.dirname(HERE))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

STICKY = "Break"
PICK_MM = 3.0  # a click this close to a break point removes it


def toggle(doc, panel, click, pick, steps, tol):
    """Click on the contour of panel (object): removes the break point within pick of the click, else adds one at
    the contour point nearest the click. "added" / "removed" or why skipped."""
    lp = close_panel(panel.Geometry)
    if lp is None:
        return u"panel is not closed"
    near = max(MATCH_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem), 10 * tol)
    q = lp.PointAt(lp.ClosestPoint(click)[1])
    on = [o for o in break_objects(doc) if lp.PointAt(lp.ClosestPoint(o.Geometry.Location)[1]).DistanceTo(
        o.Geometry.Location) <= near and o.Geometry.Location.DistanceTo(click) <= pick]
    if on:
        steps.delete(min(on, key=lambda o: o.Geometry.Location.DistanceTo(click)).Id)
        return u"removed"
    attrs = layer_attrs(doc, BREAKS, PARENT)
    attrs.SetUserString(BREAK, "1")
    for g in panel.Attributes.GetGroupList() or []:  # moves / selects together with the panel
        attrs.AddToGroup(g)
    doc.Objects.Add(Point(q), attrs)
    return u"added"


def ask(gp, doc):
    """Click with options Undo / Pick. A point, UNDO or None (Enter / Esc)."""
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    pick = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_pick", PICK_MM * mm), 0.0, 1e6)
    gp.SetCommandPrompt(u"Click on a panel contour — a break point there; on a break point — remove it (Enter — done)")
    i_undo = gp.AddOption("Undo")
    gp.AddOptionDouble("Pick", pick)
    while True:
        r = gp.Get()
        sc.sticky[STICKY + "_pick"] = pick.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_undo:
                return UNDO
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options:
  Pick — a click this close to a break point removes it (default 3 mm; Point snap — exactly on it)
  Undo — take back the last click (again — the click before it)"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select panels (closed curves = sew lines)", rs.filter.curve, preselect=True)
    ids = [i for i in ids or [] if not rs.GetUserText(i, KEY) and not rs.GetUserText(i, NOTCH)]  # cut lines, notches
    if not ids:
        return
    tol = doc.ModelAbsoluteTolerance
    steps = Steps(doc)
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.AcceptNothing(True)
        click = ask(gp, doc)
        if click is None:
            break
        if click == UNDO:
            steps.undo()
            continue
        steps.start()
        crvs = [(i, rs.coercecurve(i)) for i in ids]
        oid = min((ic for ic in crvs if ic[1]), key=lambda ic: ic[1].PointAt(ic[1].ClosestPoint(click)[1]).DistanceTo(click))[0]
        res = toggle(doc, doc.Objects.FindId(oid), click, sc.sticky[STICKY + "_pick"], steps, tol)
        print(u"Break point %s" % res if res in (u"added", u"removed") else u"Skipped: %s" % res)
        doc.Views.Redraw()


if __name__ == "__main__":
    main()
