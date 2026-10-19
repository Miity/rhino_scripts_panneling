# -*- coding: utf-8 -*-
"""Match Notches — checks the lengths of two edges sewn together; nothing is placed or changed (notches — Notches.py).
Select panels (closed curves = sew lines), then two clicks per seam: near edge A, then near edge B sewn to it
(several seams in a row, Enter — done). Edges run corner to corner (a break larger than Angle; an edge also ends
at a break point, Break.py).
The lengths of both edges and their difference are printed (what the seamstress has to ease in).
A ripresa (Break.py, Type Ripresa) is not a corner: the edge runs through it and its length is taken sewn — without
the ripresa.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.modules.pop("Seams", None)  # Rhino keeps modules from the first run for the session
from Seams import KEY, MATCH_MM, NOTCH, breaks_on, edges, loop, riprese_on, skips, to_sewn, up_normal
sys.path.insert(0, os.path.dirname(HERE))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO  # option Undo on edge B: pick edge A again

STICKY = "MatchNotches"


def mm(doc):
    return Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)


def near(doc, tol):
    return max(MATCH_MM * mm(doc), 10 * tol)


def pick(doc, ids, click, tol):
    """(panel id, its edge nearest the click, its riprese — skips) or None — panel not closed."""
    def dist(c):
        return c.PointAt(c.ClosestPoint(click)[1]).DistanceTo(click)
    oid, crv = min(((i, rs.coercecurve(i)) for i in ids), key=lambda ic: dist(ic[1]) if ic[1] else 1e300)
    lp = loop(crv, up_normal(crv, doc, tol)) if crv else None
    if lp is None:
        return None
    rips = riprese_on(doc, lp, near(doc, tol))
    es = edges(lp, sc.sticky.get(STICKY + "_angle", 30.0), tol, breaks_on(doc, lp, near(doc, tol)), rips)
    e = min(es, key=dist)
    return oid, e, skips(e, rips, near(doc, tol))


def length(p):
    """Sewn length of a picked edge (riprese out)."""
    return to_sewn(p[1].GetLength(), p[2])


def ask(prompt, undo):
    """Click with options (Undo) / Angle. A point, UNDO or None (Enter / Esc)."""
    gp = Rhino.Input.Custom.GetPoint()
    gp.AcceptNothing(True)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    while True:
        gp.ClearCommandOptions()
        gp.SetCommandPrompt(prompt)
        i_undo = gp.AddOption("Undo") if undo else -1
        gp.AddOptionDouble("Angle", a)
        r = gp.Get()
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_undo:
                return UNDO
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Per seam two clicks: near edge A, then near edge B sewn to it. Only checks: nothing is placed.
  The lengths of both edges and the difference are printed; a ripresa (Break.py Type=Ripresa) — measured without it
  Angle — a break larger than this angle = corner (edges are taken corner to corner)
  Undo — on edge B: pick edge A again"""  # printed at start


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select panels (closed curves = sew lines)", rs.filter.curve, preselect=True)
    ids = [i for i in ids or [] if not rs.GetUserText(i, KEY) and not rs.GetUserText(i, NOTCH)]  # cut lines, notches
    if not ids:
        return
    tol = doc.ModelAbsoluteTolerance
    k = mm(doc)
    while True:
        ca = ask(u"Edge A: click near it (Enter — done)", False)
        if ca is None:
            break
        cb = ask(u"Edge B (sewn to A): click near it", True)
        if cb is None:
            break
        if cb == UNDO:
            continue
        a, b = pick(doc, ids, ca, tol), pick(doc, ids, cb, tol)
        if not a or not b:
            print(u"Skipped: panel is not closed")
            continue
        la, lb = length(a), length(b)
        rip = sum(y - x for x, y in a[2] + b[2])
        print(u"Seam: edges %.1f → %.1f mm%s, difference %+.1f mm" % (
            la / k, lb / k, u" (sewn, ripresa %.1f mm out)" % (rip / k) if rip else u"", (lb - la) / k))


if __name__ == "__main__":
    main()
