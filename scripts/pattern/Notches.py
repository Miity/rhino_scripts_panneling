# -*- coding: utf-8 -*-
"""Notches — battute after PatternSmith (Pattern Editor > Design > Create Tools > Notches).
Select panels (closed curves = sew lines), click near an edge (corner to corner — a break larger than Angle;
several in a row, Enter — done). Where the click sits on the edge sets From, as in PatternSmith: first third —
Start (the corner nearest the click), middle third — Middle, last third — End (the other corner nearest the click).
Mode (PatternSmith tools):
  Single — one notch: Distance from From (Percent=Yes — % of the edge length; Middle — towards the click);
    Distance=0 — right at the click (snaps work);
  Mid — one notch at the middle of the edge;
  Evenly — Repeat Evenly Between: First from the corner nearest the click, Last from the other one, Count notches
    in all (both included), equal spacing;
  Repeat — Repeat Starting: from From, the first at Position, then Every; Middle + Both=Yes — both directions.
Tool Mark (pen, layer INK): Style Slit (a line) / V (opening Width on the line, tip Depth away), Placement In
(into the panel) / Out / Center (across the line), Depth.
Tool Cut (knife, layer INT — inner cuts) — a V for the circular blade (lama circolare), which cuts Overcut past
both ends of every line: each leg is its own short line pointing to the apex, from Overcut to Overcut + Move along
the leg; the blade's own overrun then cuts exactly from the edge to the apex — nothing behind the edge, the
triangle falls out. Legs are 2·Overcut + Move long, so the width follows: 2·√((2·Overcut + Move)² − Depth²)
(Overcut 1, Move 2, Depth 3 → ≈ 5.3 mm). Depth over 2·Overcut + Move — the legs meet straight: one slit.
Standard (Tool=Cut) — back to the plotter's standard: Repeat from the middle both ways, Position 0, Every 300,
Depth 3, Overcut 1, Move 2, Angle 30 (the last values are remembered otherwise).
If the panel has a cut line (Seams, Pattern::Seams), the notches sit on it — moved out from the sew line by the
edge's seam width; the next Seams change moves them again. A notch In that reaches the sew line
(Depth ≥ seam width) — warning. UserText on each notch: Notch (style), NotchW, NotchD, NotchPlace, NotchTool.
The notches of one click are one group; they also join the panel's groups (move with it).
"""
import math
import os
import sys

import Rhino
import System
import System.Drawing
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, Interval, LineCurve, PolylineCurve, Vector3d

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.modules.pop("Seams", None)  # Rhino keeps modules from the first run for the session
from Seams import KEY, NOTCH, edges, find_cut, loop, seam_data, up_normal
sys.path.insert(0, os.path.dirname(HERE))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

STICKY = "Notches"
MODES = ["Single", "Mid", "Evenly", "Repeat"]
STYLES = ["Slit", "V"]
PLACES = ["In", "Out", "Center"]
TOOLS = ["Mark", "Cut"]
LAYERS = {"Mark": ("INK", System.Drawing.Color.Blue), "Cut": ("INT", System.Drawing.Color.Orange)}  # INT — inner cuts
# defaults, mm (doc units at run time); counts, toggles, list indices as they are
DEFAULTS = {"mode": 3, "dist": 0.0, "pct": False, "first": 50.0, "last": 50.0, "count": 3, "pos": 0.0,
            "every": 200.0, "both": True, "style": 0, "width": 6.0, "depth": 5.0, "place": 0, "tool": 0,
            "kdepth": 3.0, "over": 1.0, "move": 2.0, "angle": 30.0}  # kdepth / over / move — knife V
# plotter standard for knife notches (option Standard; mm, list index, toggle as in DEFAULTS)
STANDARD = {"mode": 3, "pos": 0.0, "every": 300.0, "both": True, "kdepth": 3.0, "over": 1.0, "move": 2.0, "angle": 30.0}
MM_KEYS = ("dist", "first", "last", "pos", "every", "width", "depth", "kdepth", "over", "move")


def opt(name, doc=None):
    """Current option value from sc.sticky (lengths in doc units)."""
    v = DEFAULTS[name]
    if doc is not None and name in MM_KEYS:
        v *= Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    return sc.sticky.get(STICKY + "_" + name, v)


def use_standard(doc):
    """Option Standard: the plotter's standard values for knife notches into sc.sticky."""
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    sc.sticky.update(dict((STICKY + "_" + k, v * mm if k in MM_KEYS else v) for k, v in STANDARD.items()))


def positions(length, mode, s_click, o, eps=1e-6):
    """Lengths along the edge (from its start) of the notches of one click; s_click — the click's length.
    o — option values: dist, pct, first, last, count, pos, every, both (lengths in doc units)."""
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
    else:  # Repeat
        span = mid if third == 1 else length
        ds, k = [], 0
        while o["every"] > eps and o["pos"] + k * o["every"] <= span + eps:
            ds.append(o["pos"] + k * o["every"])
            k += 1
        if third == 1:
            out = [mid + sign * d for d in ds] + ([mid - sign * d for d in ds if d > eps] if o["both"] else [])
        else:
            out = ds if third == 0 else [length - d for d in ds]
    return sorted(min(max(s, 0.0), length) for s in out if -eps <= s <= length + eps)


def notch(base, out, normal, style, place, w, d):
    """Notch at base on the line, out — outside of the edge there. Slit: a line of length d; V: opening w on the
    line, tip d away. In — into the panel, Out — away from it, Center — across the line (half each way)."""
    u = -out if place == "In" else out
    a = base - u * (d / 2.0) if place == "Center" else base
    tip = a + u * d
    if style == "Slit":
        return LineCurve(a, tip)
    t = Vector3d.CrossProduct(out, normal)  # along the edge
    return PolylineCurve([a - t * (w / 2.0), tip, a + t * (w / 2.0)])


def knife_width(d, c, m):
    """(width, move) of the knife V of depth d for a blade cutting c past each line end, knife move m:
    legs 2c + m long. Deeper than that — move grows until the legs meet straight (width 0: a slit)."""
    m = max(m, d - 2 * c)
    return 2 * math.sqrt(max((2 * c + m) ** 2 - d * d, 0.0)), m


def knife(base, out, normal, d, w, c, m):
    """Knife V at base on the line (out — outside of the edge there), depth d, width w: per leg one line pointing
    to the apex, from c to c + m along it from its edge point (w = 0 — one line). The blade cutting c past both ends
    then cuts exactly edge point → apex."""
    t = Vector3d.CrossProduct(out, normal)  # along the edge
    apex = base - out * d
    lines = []
    for e in ([base] if w <= 1e-9 else [base - t * (w / 2.0), base + t * (w / 2.0)]):
        u = apex - e
        u.Unitize()
        lines.append(LineCurve(e + u * c, e + u * (c + m)))
    return lines


def tool_attrs(doc, tool):
    """Mark — pen, layer INK; Cut — knife, layer INT (inner cuts; created if missing)."""
    name, color = LAYERS[tool]
    idx = doc.Layers.FindByFullPath(name, -1)
    if idx < 0:
        idx = doc.Layers.Add(name, color)
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = idx
    return attrs


def place(doc, oid, click, tol):
    """Notches of one click on the edge of panel oid nearest the click. Number made, or why skipped."""
    obj = doc.Objects.FindId(oid)
    crv = obj.Geometry if obj else None
    if not isinstance(crv, Curve):
        return u"not a curve"
    normal = up_normal(crv, doc, tol)
    lp = loop(crv, normal)
    if lp is None:
        return u"panel is not closed"
    es = edges(lp, opt("angle"), tol)
    k = min(range(len(es)), key=lambda i: es[i].PointAt(es[i].ClosestPoint(click)[1]).DistanceTo(click))
    e = es[k]
    w = seam_data(find_cut(doc, lp, es, normal, tol), es, normal, tol)[0][k]  # notches on the cut line
    length = e.GetLength()
    t = e.ClosestPoint(click)[1]
    o = dict((k, opt(k, doc)) for k in DEFAULTS)
    ss = positions(length, MODES[o["mode"]], e.GetLength(Interval(e.Domain.T0, t)), o)
    if not ss:
        return u"no notch fits on the edge (%g)" % round(length, 1)
    tool = TOOLS[o["tool"]]
    if tool == "Cut":  # knife: always the circular-blade V, into the panel
        style, where, d = "V", "In", o["kdepth"]
        width, move = knife_width(d, o["over"], o["move"])
        print(u"Knife V: width %g, depth %g; each leg — the knife drops %g along it from the edge, moves %g, lifts"
              % (round(width, 2), d, o["over"], round(move, 2)))
    else:
        style, where, d, width = STYLES[o["style"]], PLACES[o["place"]], o["depth"], o["width"]
    attrs = tool_attrs(doc, tool)
    for g in list(obj.Attributes.GetGroupList() or []) + [doc.Groups.Add()]:  # panel's groups + one per click
        attrs.AddToGroup(g)
    for k, v in ((NOTCH, style), ("NotchW", "%.6g" % width), ("NotchD", "%.6g" % d),
                 ("NotchPlace", where), ("NotchTool", tool)):
        attrs.SetUserString(k, v)
    for s in ss:
        ok, ts = e.LengthParameter(s)
        p = e.PointAt(ts if ok else t)
        out = Vector3d.CrossProduct(e.TangentAt(ts if ok else t), normal)
        out.Unitize()
        base = p + out * w
        for g in (knife(base, out, normal, d, width, o["over"], move) if tool == "Cut" else
                  [notch(base, out, normal, style, where, width, d)]):
            doc.Objects.AddCurve(g, attrs)
    inward = {"In": d, "Center": d / 2.0}.get(where, 0.0)
    if w > tol and inward >= w - tol:
        print(u"Warning: Depth %g reaches the sew line (seam %g)" % (d, w))
    return len(ss)


def ask(gp, doc):
    """Click with options Undo / Mode / (mode options) / Tool / Style, Width (V), Depth, Placement (Mark) or
    Depth, Overcut, Move, Standard (Cut) / Angle. A point, UNDO or None (Enter / Esc). Values — in sc.sticky."""
    C = Rhino.Input.Custom
    num = dict((k, C.OptionDouble(opt(k, doc), 0.0, 1e6)) for k in ("dist", "first", "last", "pos", "every", "width",
                                                                     "depth", "kdepth", "over"))
    num["move"] = C.OptionDouble(opt("move", doc), 0.05, 1e6)  # the knife has to move a little
    count = C.OptionInteger(opt("count"), 1, 1000)
    pct = C.OptionToggle(opt("pct"), "No", "Yes")
    both = C.OptionToggle(opt("both"), "No", "Yes")
    a = C.OptionDouble(opt("angle"), 1.0, 179.0)
    while True:
        mode, style = MODES[opt("mode")], STYLES[opt("style")]
        gp.ClearCommandOptions()
        gp.SetCommandPrompt(u"Click near an edge: first third — from its nearer corner, middle third — from the middle (Enter — done)")
        i_undo = gp.AddOption("Undo")
        i_std = -1
        idx = {}
        idx[gp.AddOptionList("Mode", MODES, opt("mode"))] = "mode"
        if mode == "Single":
            gp.AddOptionDouble("Distance", num["dist"])
            gp.AddOptionToggle("Percent", pct)
        elif mode == "Evenly":
            gp.AddOptionDouble("First", num["first"])
            gp.AddOptionDouble("Last", num["last"])
            gp.AddOptionInteger("Count", count)
        elif mode == "Repeat":
            gp.AddOptionDouble("Position", num["pos"])
            gp.AddOptionDouble("Every", num["every"])
            gp.AddOptionToggle("Both", both)
        idx[gp.AddOptionList("Tool", TOOLS, opt("tool"))] = "tool"
        if TOOLS[opt("tool")] == "Cut":  # knife V: its width follows from these
            gp.AddOptionDouble("Depth", num["kdepth"])
            gp.AddOptionDouble("Overcut", num["over"])
            gp.AddOptionDouble("Move", num["move"])
            i_std = gp.AddOption("Standard")
        else:
            idx[gp.AddOptionList("Style", STYLES, opt("style"))] = "style"
            if style == "V":
                gp.AddOptionDouble("Width", num["width"])
            gp.AddOptionDouble("Depth", num["depth"])
            idx[gp.AddOptionList("Placement", PLACES, opt("place"))] = "place"
        gp.AddOptionDouble("Angle", a)
        r = gp.Get()
        for k, v in num.items():
            sc.sticky[STICKY + "_" + k] = v.CurrentValue
        sc.sticky.update({STICKY + "_count": count.CurrentValue, STICKY + "_pct": pct.CurrentValue,
                          STICKY + "_both": both.CurrentValue, STICKY + "_angle": a.CurrentValue})
        if r == Rhino.Input.GetResult.Option:
            i = gp.OptionIndex()
            if i == i_undo:
                return UNDO
            if i == i_std:  # plotter standard into sticky and into the option fields shown
                use_standard(doc)
                for k in ("pos", "every", "kdepth", "over", "move"):
                    num[k].CurrentValue = opt(k, doc)
                both.CurrentValue, a.CurrentValue = opt("both"), opt("angle")
            if i in idx:
                sc.sticky[STICKY + "_" + idx[i]] = gp.Option().CurrentListOptionIndex
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options (where the click sits on the edge sets From: first third — Start = nearer corner, middle — Middle, last — End):
  Mode — Single: one notch at Distance from From (0 — at the click, Percent=Yes — % of the edge); Mid: middle of the edge;
    Evenly: First / Last from the corners (First — the corner nearer the click), Count notches in all, equal spacing;
    Repeat: from From, first at Position, then Every; Middle + Both=Yes — both directions
  Tool — Mark: pen, layer INK; Cut: knife, layer INT (inner cuts), always the V for the circular blade
  Mark: Style — Slit: a line; V: opening Width on the line, tip Depth away; Depth — notch depth;
    Placement — In: into the panel, Out: away from it, Center: across the line
  Cut: Depth — real V depth (default 3); Overcut — how far the blade cuts past each end of a line (measure: cut a
    1 mm line on scrap, Overcut = (slit − 1) / 2); Move — knife move per leg; the width follows (printed)
  Standard — (Tool=Cut) back to the plotter standard: Repeat from the middle, Both, Position 0, Every 300, Depth 3,
    Overcut 1, Move 2, Angle 30
  Angle — a break larger than this angle = corner (edges are taken corner to corner)
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
    print(u"Notches: %d → INK / INT" % sum(made))


if __name__ == "__main__":
    main()
