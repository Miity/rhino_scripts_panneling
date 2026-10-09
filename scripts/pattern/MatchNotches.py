# -*- coding: utf-8 -*-
"""Match Notches — the notches of one edge onto the edge sewn to it (CLO 3D / PatternSmith: notches meet when sewing).
Select panels (closed curves = sew lines), then two clicks per seam: near edge A at the corner where the seam starts,
then near edge B at the corner sewn to that one (several seams in a row, Enter — done). Edges run corner to corner
(a break larger than Angle; an edge also ends at a break point, Break.py).
Every notch point of A (Notches) gets a point on B at the same distance from the clicked corner: layer Pattern::Notches,
UserText Notch = Point, one group per seam + panel B's groups. A notch already on B there (within 1 mm) is kept,
one past the end of B is skipped (counted). A has no notches but B has — copied from B to A.
The lengths of both edges and their difference are printed (what the seamstress has to ease in).
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Interval, Point

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.modules.pop("Seams", None)  # Rhino keeps modules from the first run for the session
from Seams import KEY, MATCH_MM, NOTCH, PARENT, breaks_on, edges, layer_attrs, loop, up_normal
sys.path.insert(0, os.path.dirname(HERE))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last seam

STICKY = "MatchNotches"
LAYER = "Notches"  # same layer as Notches.py: Pattern::Notches


def mm(doc):
    return Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)


def near(doc, tol):
    return max(MATCH_MM * mm(doc), 10 * tol)


def pick(doc, ids, click, tol):
    """(panel id, its edge nearest the click, running from the corner nearest the click) or None — panel not closed."""
    def dist(c):
        return c.PointAt(c.ClosestPoint(click)[1]).DistanceTo(click)
    oid, crv = min(((i, rs.coercecurve(i)) for i in ids), key=lambda ic: dist(ic[1]) if ic[1] else 1e300)
    lp = loop(crv, up_normal(crv, doc, tol)) if crv else None
    if lp is None:
        return None
    es = edges(lp, sc.sticky.get(STICKY + "_angle", 30.0), tol, breaks_on(doc, lp, near(doc, tol)))
    e = min(es, key=dist).DuplicateCurve()
    if e.PointAtEnd.DistanceTo(click) < e.PointAtStart.DistanceTo(click):
        e.Reverse()
    return oid, e


def on_edge(doc, e, nr):
    """Lengths from the start of edge e of the notch points lying on it."""
    s = Rhino.DocObjects.ObjectEnumeratorSettings()
    s.HiddenObjects = s.LockedObjects = True
    out = []
    for o in doc.Objects.GetObjectList(s):
        if o.Attributes.GetUserString(NOTCH) != "Point" or not isinstance(o.Geometry, Point):
            continue
        p = o.Geometry.Location
        t = e.ClosestPoint(p)[1]
        if e.PointAt(t).DistanceTo(p) <= nr:
            out.append(e.GetLength(Interval(e.Domain.T0, t)))
    return sorted(out)


def match(doc, a, b, tol):
    """Notch points of edge a copied onto edge b at the same lengths from their start (a, b — from pick);
    a without notches and b with them — b onto a. (made, past the end, length from, length to)."""
    nr = near(doc, tol)
    sa, sb = on_edge(doc, a[1], nr), on_edge(doc, b[1], nr)
    if not sa and sb:
        a, b, sa, sb = b, a, sb, sa
    e, lb = b[1], b[1].GetLength()
    attrs = layer_attrs(doc, LAYER, PARENT)
    attrs.SetUserString(NOTCH, "Point")
    made = past = 0
    for s in sa:
        if s > lb + nr:
            past += 1
        elif not any(abs(s - x) <= nr for x in sb):
            if not made:  # panel B's groups + one per seam, only when something is placed
                for g in list(doc.Objects.FindId(b[0]).Attributes.GetGroupList() or []) + [doc.Groups.Add()]:
                    attrs.AddToGroup(g)
            ok, t = e.LengthParameter(min(s, lb))
            doc.Objects.Add(Point(e.PointAt(t if ok else e.Domain.T1)), attrs)
            made += 1
    return made, past, a[1].GetLength(), lb


def ask(prompt):
    """Click with options Undo / Angle. A point, UNDO or None (Enter / Esc)."""
    gp = Rhino.Input.Custom.GetPoint()
    gp.AcceptNothing(True)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    while True:
        gp.ClearCommandOptions()
        gp.SetCommandPrompt(prompt)
        i_undo = gp.AddOption("Undo")
        gp.AddOptionDouble("Angle", a)
        r = gp.Get()
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_undo:
                return UNDO
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Per seam two clicks: edge A near the corner where the seam starts, edge B near the corner sewn to it.
  The notch points of A go onto B at the same distances from the clicked corner (A without notches — from B to A);
  the lengths of both edges and the difference are printed
  Angle — a break larger than this angle = corner (edges are taken corner to corner)
  Undo — on edge A: take back the last seam (again — the one before it); on edge B: pick edge A again"""  # printed at start


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select panels (closed curves = sew lines)", rs.filter.curve, preselect=True)
    ids = [i for i in ids or [] if not rs.GetUserText(i, KEY) and not rs.GetUserText(i, NOTCH)]  # cut lines, notches
    if not ids:
        return
    tol = doc.ModelAbsoluteTolerance
    steps = Steps(doc)
    made = []  # notches per seam (Undo takes the last off)
    while True:
        ca = ask(u"Edge A: click near it at the corner where the seam starts (Enter — done)")
        if ca is None:
            break
        if ca == UNDO:
            if steps.undo() and made:
                made.pop()
            continue
        cb = ask(u"Edge B: click near it at the corner sewn to that one")
        if cb is None:
            break
        if cb == UNDO:
            continue
        a, b = pick(doc, ids, ca, tol), pick(doc, ids, cb, tol)
        if not a or not b:
            print(u"Skipped: panel is not closed")
            continue
        steps.start()
        n, past, la, lb = match(doc, a, b, tol)
        if n:
            made.append(n)
        k = mm(doc)
        print(u"Notches: %d placed%s; edges %.1f → %.1f mm, difference %+.1f mm" % (
            n, u", %d past the end" % past if past else u"", la / k, lb / k, (lb - la) / k))
        doc.Views.Redraw()
    print(u"Match Notches: %d points → Pattern::%s (Convert Notches — into pen / knife notches)" % (sum(made), LAYER))


if __name__ == "__main__":
    main()
