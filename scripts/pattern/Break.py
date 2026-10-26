# -*- coding: utf-8 -*-
"""Break — break points on panel contours, after PatternSmith (Pattern Editor > Design > Edit Tools > Break).
A break point splits a panel edge (corner to corner) into two edges, as a corner does: Seams gives each its own
seam width and corner style, Notches counts From / Mid / Repeat… on each, Convert Notches takes the nearest one.
Select panels (closed curves = sew lines), then click on a contour (snaps work; several in a row, Enter — done):
a break point there — the point of the contour nearest the click; a click on a break point (within Pick) — removes it.
Layer Pattern::Breaks, UserText Break, in the panel's groups (moves with it); the scripts find the points on the
panel by geometry — no ids. A panel that already has a seam: its widths are read off the cut line again
(the edges are numbered anew), the corner styles go back to Extend — set them again in Seams if needed.
A 3D surface / polysurface can be selected instead (or with them): the click snaps to the nearest edge of the
surface (an edge shared by two faces too), the break point goes on it (no groups) — Squish To carries it onto the flat
panel, where it is an ordinary break point. Ripresa works on a flat panel curve only.
Type=Ripresa: a click near a contour segment marks it as a ripresa — the straight segment inside an edge that a seam
takes in when sewn (a dart): a mark point at its middle (UserText Break = Ripresa, same layer) + a notch point at
each end (Pattern::Notches), one group with the panel's groups; a click on a marked segment — removes all three.
The ripresa is not a break: Notches and Match Notches take the edge through it and measure it sewn (its length out),
Seams does not see it.
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
from Seams import (BREAK, BREAKS, KEY, MATCH_MM, NOTCH, PARENT, RIPRESA, break_objects, close_panel, layer_attrs,
                   mid, segment)
sys.path.insert(0, os.path.dirname(HERE))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

STICKY = "Break"
PICK_MM = 3.0  # a click this close to a break point removes it
TYPES = ["Break", "Ripresa"]
NOTCHES = "Notches"  # notch points at the ripresa ends: same layer as Notches.py, Pattern::Notches


def near_mm(doc, tol):
    return max(MATCH_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem), 10 * tol)


def contours(oid):
    """The contour curves of a selected object: the closed panel curve itself, or every edge of a 3D surface."""
    crv = rs.coercecurve(oid)
    if crv:
        return [crv]
    brep = rs.coercebrep(oid)
    return [e.EdgeCurve for e in brep.Edges] if brep else []


def nearest(crvs, p):
    """The point of the curves nearest p."""
    return min((c.PointAt(c.ClosestPoint(p)[1]) for c in crvs), key=p.DistanceTo)


def toggle(doc, panel, click, pick, steps, tol):
    """Click on the contour of panel (object; a 3D surface — its edges): removes the break point within pick of the
    click, else adds one at the contour point nearest the click. "added" / "removed" or why skipped."""
    flat = rs.coercecurve(panel.Id) is not None
    if flat:
        lp = close_panel(panel.Geometry)
        if lp is None:
            return u"panel is not closed"
        crvs = [lp]
    else:
        crvs = contours(panel.Id)
    near = near_mm(doc, tol)
    q = nearest(crvs, click)
    on = [o for o in break_objects(doc) if o.Attributes.GetUserString(BREAK) != RIPRESA and nearest(crvs, o.Geometry.Location).DistanceTo(
        o.Geometry.Location) <= near and o.Geometry.Location.DistanceTo(click) <= pick]
    if on:
        steps.delete(min(on, key=lambda o: o.Geometry.Location.DistanceTo(click)).Id)
        return u"removed"
    attrs = layer_attrs(doc, BREAKS, PARENT)
    attrs.SetUserString(BREAK, "1")
    for g in (panel.Attributes.GetGroupList() or []) if flat else []:  # moves / selects together with the panel
        attrs.AddToGroup(g)
    doc.Objects.Add(Point(q), attrs)
    return u"added"


def ripresa(doc, panel, click, steps, tol):
    """Click near a contour segment of panel (object): marks it as a ripresa (mark at its middle + notch points at
    its ends), or removes them if it is marked already. "added" / "removed" or why skipped."""
    lp = close_panel(panel.Geometry)
    if lp is None:
        return u"panel is not closed"
    seg = segment(lp, click)
    if seg is None:
        return u"no straight segment there (one smooth curve)"
    near, m = near_mm(doc, tol), mid(seg)
    ends = (seg.PointAtStart, seg.PointAtEnd)
    marks = [o for o in break_objects(doc) if o.Attributes.GetUserString(BREAK) == RIPRESA
             and o.Geometry.Location.DistanceTo(m) <= near]
    s = Rhino.DocObjects.ObjectEnumeratorSettings()
    s.HiddenObjects = s.LockedObjects = True
    notches = [o for o in doc.Objects.GetObjectList(s) if o.Attributes.GetUserString(NOTCH) == "Point"
               and isinstance(o.Geometry, Point) and any(o.Geometry.Location.DistanceTo(p) <= near for p in ends)]
    if marks:
        for o in marks + notches:
            steps.delete(o.Id)
        return u"removed"
    groups = list(panel.Attributes.GetGroupList() or []) + [doc.Groups.Add()]  # moves with the panel, one per ripresa
    attrs = layer_attrs(doc, BREAKS, PARENT)
    attrs.SetUserString(BREAK, RIPRESA)
    for g in groups:
        attrs.AddToGroup(g)
    doc.Objects.Add(Point(m), attrs)
    attrs = layer_attrs(doc, NOTCHES, PARENT)
    attrs.SetUserString(NOTCH, "Point")
    for g in groups:
        attrs.AddToGroup(g)
    for p in ends:
        if not any(o.Geometry.Location.DistanceTo(p) <= near for o in notches):  # one already there is kept
            doc.Objects.Add(Point(p), attrs)
    return u"added"


def ask(gp, doc):
    """Click with options Undo / Type / Pick. A point, UNDO or None (Enter / Esc)."""
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    pick = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_pick", PICK_MM * mm), 0.0, 1e6)
    while True:
        kind = sc.sticky.get(STICKY + "_type", 0)
        gp.ClearCommandOptions()
        gp.SetCommandPrompt(u"Click on a panel contour or a 3D surface edge — a break point there; on a break point — remove it (Enter — done)"
                            if TYPES[kind] == "Break" else
                            u"Click near the ripresa segment — mark it; on a marked one — remove it (Enter — done)")
        i_undo = gp.AddOption("Undo")
        i_type = gp.AddOptionList("Type", TYPES, kind)
        if TYPES[kind] == "Break":
            gp.AddOptionDouble("Pick", pick)
        r = gp.Get()
        sc.sticky[STICKY + "_pick"] = pick.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_undo:
                return UNDO
            if gp.OptionIndex() == i_type:
                sc.sticky[STICKY + "_type"] = gp.Option().CurrentListOptionIndex
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options:
  Type — Break: break points (on a panel curve or on the edges of a 3D surface — Squish To carries them to the flat panel); Ripresa (flat panel curve only): a click near a segment marks it as a ripresa (taken in when sewn) —
    notch points at its ends, Notches / Match Notches measure the edge without it; a click on a marked one removes it
  Pick — a click this close to a break point removes it (default 3 mm; Point snap — exactly on it)
  Undo — take back the last click (again — the click before it)"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select panels (closed curves = sew lines) or 3D surfaces", rs.filter.curve | rs.filter.surface | rs.filter.polysurface,
                        preselect=True)
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
        cs = [(i, contours(i)) for i in ids]
        oid = min((ic for ic in cs if ic[1]), key=lambda ic: nearest(ic[1], click).DistanceTo(click))[0]
        panel = doc.Objects.FindId(oid)
        if TYPES[sc.sticky.get(STICKY + "_type", 0)] == "Ripresa":
            if rs.coercecurve(oid) is None:
                res, what = u"ripresa works on a flat panel curve, not on a 3D surface", u"Ripresa"
            else:
                res, what = ripresa(doc, panel, click, steps, tol), u"Ripresa"
        else:
            res, what = toggle(doc, panel, click, sc.sticky[STICKY + "_pick"], steps, tol), u"Break point"
        print(u"%s %s" % (what, res) if res in (u"added", u"removed") else u"Skipped: %s" % res)
        doc.Views.Redraw()


if __name__ == "__main__":
    main()
