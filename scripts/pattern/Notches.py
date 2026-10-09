# -*- coding: utf-8 -*-
"""Notches — battute after PatternSmith (Pattern Editor > Design > Create Tools > Notches), as points.
Select panels (closed curves = sew lines), click near an edge (corner to corner — a break larger than Angle;
several in a row, Enter — done; an edge also ends at a break point, Break.py). Where the click sits on the edge
sets From, as in PatternSmith: first third — Start (the corner nearest the click), middle third — Middle,
last third — End (the other corner nearest the click).
Mode (PatternSmith tools):
  Single — one notch: Distance from From (Percent=Yes — % of the edge length; Middle — towards the click);
    Distance=0 — right at the click (snaps work);
  Mid — one notch at the middle of the edge;
  Evenly — Repeat Evenly Between: First from the corner nearest the click, Last from the other one, Count notches
    in all (both included), equal spacing;
  Repeat — always from the middle of the edge (wherever the click is): one at the middle, then every Every both ways
    to the corners.
Each notch is a point on the sew line (seen at any zoom), layer Pattern::Notches, UserText Notch = Point; the points
of one click are one group, also in the panel's groups (move with it). Convert Notches turns them into the real
notches — pen (INK) or knife V (INT) — on the cut line if the panel has one.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, Interval, Point

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.modules.pop("Seams", None)  # Rhino keeps modules from the first run for the session
from Seams import KEY, MATCH_MM, NOTCH, PARENT, breaks_on, edges, layer_attrs, loop, up_normal
sys.path.insert(0, os.path.dirname(HERE))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

STICKY = "Notches"
LAYER = "Notches"  # points: layer Pattern::Notches
MODES = ["Single", "Mid", "Evenly", "Repeat"]
# defaults, mm (doc units at run time); counts, toggles, list indices as they are
DEFAULTS = {"mode": 3, "dist": 0.0, "pct": False, "first": 50.0, "last": 50.0, "count": 3, "every": 300.0,
            "angle": 30.0}
MM_KEYS = ("dist", "first", "last", "every")


def opt(name, doc=None):
    """Current option value from sc.sticky (lengths in doc units)."""
    v = DEFAULTS[name]
    if doc is not None and name in MM_KEYS:
        v *= Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    return sc.sticky.get(STICKY + "_" + name, v)


def positions(length, mode, s_click, o, eps=1e-6):
    """Lengths along the edge (from its start) of the notches of one click; s_click — the click's length.
    o — option values: dist, pct, first, last, count, every (lengths in doc units)."""
    third = 0 if s_click < length / 3.0 else (2 if s_click > 2 * length / 3.0 else 1)  # From: Start / Middle / End
    mid, sign = length / 2.0, (1 if s_click >= length / 2.0 else -1)  # Middle: towards the click
    if mode == "Single":
        d = o["dist"] * length / 100.0 if o["pct"] else o["dist"]
        out = [s_click] if d <= eps else [[d, mid + sign * d, length - d][third]]
    elif mode == "Mid":
        out = [mid]
    elif mode == "Evenly":  # First from the corner nearest the click
        a, b = (o["first"], length - o["last"]) if s_click < mid else (o["last"], length - o["first"])
        n = int(o["count"])
        out = [] if b < a - eps else ([a + (b - a) * i / (n - 1.0) for i in range(n)] if n > 1 else [(a + b) / 2.0])
    else:  # Repeat: always from the middle, both ways
        ds = [k * o["every"] for k in range(int((mid + eps) / o["every"]) + 1)] if o["every"] > eps else []
        out = [mid + d for d in ds] + [mid - d for d in ds[1:]]
    return sorted(min(max(s, 0.0), length) for s in out if -eps <= s <= length + eps)


def place(doc, oid, click, tol):
    """Notch points of one click on the edge of panel oid nearest the click. Number made, or why skipped."""
    obj = doc.Objects.FindId(oid)
    crv = obj.Geometry if obj else None
    if not isinstance(crv, Curve):
        return u"not a curve"
    lp = loop(crv, up_normal(crv, doc, tol))
    if lp is None:
        return u"panel is not closed"
    near = max(MATCH_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem), 10 * tol)
    es = edges(lp, opt("angle"), tol, breaks_on(doc, lp, near))  # edges also end at break points
    e = min(es, key=lambda c: c.PointAt(c.ClosestPoint(click)[1]).DistanceTo(click))
    length = e.GetLength()
    t = e.ClosestPoint(click)[1]
    o = dict((k, opt(k, doc)) for k in DEFAULTS)
    ss = positions(length, MODES[o["mode"]], e.GetLength(Interval(e.Domain.T0, t)), o)
    if not ss:
        return u"no notch fits on the edge (%g)" % round(length, 1)
    attrs = layer_attrs(doc, LAYER, PARENT)
    attrs.SetUserString(NOTCH, "Point")
    for g in list(obj.Attributes.GetGroupList() or []) + [doc.Groups.Add()]:  # panel's + one per click
        attrs.AddToGroup(g)
    for s in ss:
        ok, ts = e.LengthParameter(s)
        doc.Objects.Add(Point(e.PointAt(ts if ok else t)), attrs)
    return len(ss)


def ask(gp, doc):
    """Click with options Undo / Mode / (mode options) / Angle. A point, UNDO or None (Enter / Esc).
    Values — in sc.sticky."""
    C = Rhino.Input.Custom
    num = dict((k, C.OptionDouble(opt(k, doc), 0.0, 1e6)) for k in MM_KEYS)
    count = C.OptionInteger(opt("count"), 1, 1000)
    pct = C.OptionToggle(opt("pct"), "No", "Yes")
    a = C.OptionDouble(opt("angle"), 1.0, 179.0)
    while True:
        mode = MODES[opt("mode")]
        gp.ClearCommandOptions()
        gp.SetCommandPrompt(u"Click near an edge: first third — from its nearer corner, middle third — from the middle (Enter — done)")
        i_undo = gp.AddOption("Undo")
        i_mode = gp.AddOptionList("Mode", MODES, opt("mode"))
        if mode == "Single":
            gp.AddOptionDouble("Distance", num["dist"])
            gp.AddOptionToggle("Percent", pct)
        elif mode == "Evenly":
            gp.AddOptionDouble("First", num["first"])
            gp.AddOptionDouble("Last", num["last"])
            gp.AddOptionInteger("Count", count)
        elif mode == "Repeat":
            gp.AddOptionDouble("Every", num["every"])
        gp.AddOptionDouble("Angle", a)
        r = gp.Get()
        for k, v in num.items():
            sc.sticky[STICKY + "_" + k] = v.CurrentValue
        sc.sticky.update({STICKY + "_count": count.CurrentValue, STICKY + "_pct": pct.CurrentValue,
                          STICKY + "_angle": a.CurrentValue})
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_undo:
                return UNDO
            if gp.OptionIndex() == i_mode:
                sc.sticky[STICKY + "_mode"] = gp.Option().CurrentListOptionIndex
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options (where the click sits on the edge sets From: first third — Start = nearer corner, middle — Middle, last — End):
  Mode — Single: one notch at Distance from From (0 — at the click, Percent=Yes — % of the edge); Mid: middle of the edge;
    Evenly: First / Last from the corners (First — the corner nearer the click), Count notches in all, equal spacing;
    Repeat: always from the middle of the edge — one at the middle, then every Every both ways (default 300)
  Angle — a break larger than this angle = corner (edges are taken corner to corner)
  Undo — take back the last click (again — the click before it)
Notches are points (Pattern::Notches); Convert Notches turns them into pen / knife notches"""  # printed at start


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select panels (closed curves = sew lines)", rs.filter.curve, preselect=True)
    ids = [i for i in ids or [] if not rs.GetUserText(i, KEY) and not rs.GetUserText(i, NOTCH)]  # cut lines, notches
    if not ids:
        return
    tol = doc.ModelAbsoluteTolerance
    steps = Steps(doc)
    made = []  # notches per click (Undo takes the last off)
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.AcceptNothing(True)
        click = ask(gp, doc)
        if click is None:
            break
        if click == UNDO:
            if steps.undo() and made:
                made.pop()
            continue
        steps.start()
        crvs = [(i, rs.coercecurve(i)) for i in ids]
        oid = min((ic for ic in crvs if ic[1]), key=lambda ic: ic[1].PointAt(ic[1].ClosestPoint(click)[1]).DistanceTo(click))[0]
        res = place(doc, oid, click, tol)
        if isinstance(res, int):
            made.append(res)
        else:  # nothing added: Undo skips this click too
            print(u"Skipped: %s" % res)
        doc.Views.Redraw()
    print(u"Notches: %d points → Pattern::%s (Convert Notches — into pen / knife notches)" % (sum(made), LAYER))


if __name__ == "__main__":
    main()
