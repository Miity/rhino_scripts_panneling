# -*- coding: utf-8 -*-
"""Convert Notches — notch points of Notches (and notches already converted) into seam markers, the format you set
(PatternSmith: Patterns > Modify Notches).
Select the notches together with their panels (a window over the panels works). Taken:
  - notches of Notches (UserText Notch): its points, or pen / knife notches made here before (into another format);
  - older battute: points, seam circles (radius up to 10 mm, Crosses), lines in Parts::SewingMarks (old centre ticks).
Format: Tool Mark (pen, layer INK): Style Slit (a line) / V (opening Width on the line, tip Depth away), Placement In
(into the panel) / Out / Center (across the line), Depth. Tool Cut (knife, layer INT — inner cuts) — a V for the
circular blade (lama circolare), which cuts Overcut past both ends of every line: each leg is its own short line
pointing to the apex, from Overcut to Overcut + Move along the leg; the blade's own overrun then cuts exactly from
the edge to the apex — nothing behind the edge, the triangle falls out. Legs are 2·Overcut + Move long, so the width
follows: 2·√((2·Overcut + Move)² − Depth²) (Overcut 1, Move 3, Depth 2 → ≈ 9.2 mm). Depth over 2·Overcut + Move —
the legs meet straight: one slit. Standard (Tool=Cut) — the plotter's standard: Depth 2, Overcut 1, Move 3, Angle 30.
A notch In that reaches the sew line (Depth ≥ seam width) — warning. UserText on each notch: Notch (style), NotchW,
NotchD, NotchPlace, NotchTool; Seams moves them out to its new cut line. Enter — convert. Each notch / mark goes to the nearest panel edge within Reach
(perpendicular to the edge): one notch there, on the panel's cut line if it has one (Seams), else on the sew line;
marks of one spot (old point + its tick, two legs of a knife V) — one notch. The new notch keeps the groups of what
it replaces and joins the panel's groups. Notches are always replaced; older marks — Originals Delete / Keep.
Panels: the closed curves of the selection (or asked for if none); cut lines and notches are not panels.
"""
import math
import os
import sys

import Rhino
import System
import System.Drawing
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, LineCurve, Point, PolylineCurve, Vector3d
from Rhino.Geometry.Intersect import Intersection

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.modules.pop("Seams", None)  # Rhino keeps modules from the first run for the session
from Seams import BREAK, KEY, MATCH_MM, NOTCH, breaks_on, close_panel, edges, find_cut, loop, seam_data, up_normal
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "markup"))
sys.modules.pop("PointsToCrosses", None)
from PointsToCrosses import is_mark_circle  # seam circles up to 10 mm are marks, bigger ones (holes) are not

STICKY = "ConvertNotches"
OLD_LAYER = "Parts::SewingMarks"  # older Battute: points + centre tick
REACH_MM = 20.0  # a mark farther than this from every selected panel edge is skipped
STYLES = ["Slit", "V"]
PLACES = ["In", "Out", "Center"]
TOOLS = ["Mark", "Cut"]
LAYERS = {"Mark": ("INK", System.Drawing.Color.Blue), "Cut": ("INT", System.Drawing.Color.Orange)}  # INT — inner cuts
# defaults, mm (doc units at run time); list indices as they are
DEFAULTS = {"style": 0, "width": 6.0, "depth": 5.0, "place": 0, "tool": 0,
            "kdepth": 2.0, "over": 1.0, "move": 3.0, "angle": 30.0}  # kdepth / over / move — knife V
# plotter standard for knife notches (option Standard; mm)
STANDARD = {"kdepth": 2.0, "over": 1.0, "move": 3.0, "angle": 30.0}
MM_KEYS = ("width", "depth", "kdepth", "over", "move")


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


def spec(o):
    """Notch properties from option values o (lengths in doc units): Tool Mark — style / placement / depth / width
    as set; Cut — always the circular-blade V into the panel, width from Depth, Overcut, Move."""
    if TOOLS[o["tool"]] == "Cut":
        width, move = knife_width(o["kdepth"], o["over"], o["move"])
        return {"tool": "Cut", "style": "V", "place": "In", "depth": o["kdepth"], "width": width,
                "over": o["over"], "move": move}
    return {"tool": "Mark", "style": STYLES[o["style"]], "place": PLACES[o["place"]], "depth": o["depth"],
            "width": o["width"]}


def shapes(base, out, normal, p):
    """Curves of notch p at base on the line (out — outside of the edge there)."""
    if p["tool"] == "Cut":
        return knife(base, out, normal, p["depth"], p["width"], p["over"], p["move"])
    return [notch(base, out, normal, p["style"], p["place"], p["width"], p["depth"])]


def tell(p, w, tol):
    """Prints the knife V geometry and a warning if notch p reaches the sew line through a seam w."""
    if p["tool"] == "Cut":
        print(u"Knife V: width %g, depth %g; each leg — the knife drops %g along it from the edge, moves %g, lifts"
              % (round(p["width"], 2), p["depth"], p["over"], round(p["move"], 2)))
    inward = {"In": p["depth"], "Center": p["depth"] / 2.0}.get(p["place"], 0.0)
    if w > tol and inward >= w - tol:
        print(u"Warning: Depth %g reaches the sew line (seam %g)" % (p["depth"], w))


def notch_attrs(doc, p, groups):
    """Attributes of notch p: layer by its tool, the groups, UserText."""
    attrs = tool_attrs(doc, p["tool"])
    for g in groups:
        attrs.AddToGroup(g)
    for k, v in ((NOTCH, p["style"]), ("NotchW", "%.6g" % p["width"]), ("NotchD", "%.6g" % p["depth"]),
                 ("NotchPlace", p["place"]), ("NotchTool", p["tool"])):
        attrs.SetUserString(k, v)
    return attrs


def tool_attrs(doc, tool):
    """Mark — pen, layer INK; Cut — knife, layer INT (inner cuts; created if missing)."""
    name, color = LAYERS[tool]
    idx = doc.Layers.FindByFullPath(name, -1)
    if idx < 0:
        idx = doc.Layers.Add(name, color)
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = idx
    return attrs


def tool_numbers(doc):
    """Number fields of tool_options (lengths in doc units)."""
    C = Rhino.Input.Custom
    num = dict((k, C.OptionDouble(opt(k, doc), 0.0, 1e6)) for k in ("width", "depth", "kdepth", "over"))
    num["move"] = C.OptionDouble(opt("move", doc), 0.05, 1e6)  # the knife has to move a little
    return num


def tool_options(gp, num):
    """Adds Tool and its options — Mark: Style, Width (V), Depth, Placement; Cut: Depth, Overcut, Move, Standard.
    Returns ({option index: sticky key of the list}, index of Standard or -1)."""
    idx = {gp.AddOptionList("Tool", TOOLS, opt("tool")): "tool"}
    if TOOLS[opt("tool")] == "Cut":  # knife V: its width follows from these
        gp.AddOptionDouble("Depth", num["kdepth"])
        gp.AddOptionDouble("Overcut", num["over"])
        gp.AddOptionDouble("Move", num["move"])
        return idx, gp.AddOption("Standard")
    idx[gp.AddOptionList("Style", STYLES, opt("style"))] = "style"
    if STYLES[opt("style")] == "V":
        gp.AddOptionDouble("Width", num["width"])
    gp.AddOptionDouble("Depth", num["depth"])
    idx[gp.AddOptionList("Placement", PLACES, opt("place"))] = "place"
    return idx, -1


def kind(doc, oid):
    """"notch", "mark", "panel" or None for a selected object."""
    o = doc.Objects.FindId(oid)
    g = o.Geometry if o else None
    if o is None:
        return None
    if o.Attributes.GetUserString(NOTCH):
        return "notch"
    if o.Attributes.GetUserString(BREAK):  # break points (Break.py) are not marks
        return None
    if isinstance(g, Point) or (isinstance(g, Curve) and is_mark_circle(oid)):
        return "mark"
    if isinstance(g, Curve):
        if doc.Layers[o.Attributes.LayerIndex].FullPath == OLD_LAYER:
            return "mark"
        if not o.Attributes.GetUserString(KEY) and close_panel(g) is not None:
            return "panel"
    return None


def prep(doc, oid, angle, tol):
    """Panel data: object, loop (counter-clockwise), edges, normal, seam widths, line the notches sit on."""
    obj = doc.Objects.FindId(oid)
    normal = up_normal(obj.Geometry, doc, tol)
    lp = loop(obj.Geometry, normal)
    if lp is None:
        return None
    near = max(MATCH_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem), 10 * tol)
    es = edges(lp, angle, tol, breaks_on(doc, lp, near))
    cut = find_cut(doc, lp, es, normal, tol)
    return {"obj": obj, "lp": lp, "es": es, "normal": normal, "widths": seam_data(cut, es, normal, tol)[0],
            "line": cut.Geometry if cut else lp}


def rough(o):
    """A point of the source: point, circle centre, curve middle."""
    g = o.Geometry
    if isinstance(g, Point):
        return g.Location
    ok, c = g.TryGetCircle()
    if ok:
        return c.Center
    return g.PointAt(g.Domain.Mid)


def anchor(o, pn, tol):
    """Point of the source on the axis of its notch (perpendicular to the edge there). Knife V leg: the V centre on
    the line, from where the leg's line meets it and the V width. Others: rough() — a slit, a pen V (its tip),
    a tick lie on the axis themselves."""
    a = o.Attributes
    if a.GetUserString("NotchTool") != "Cut":
        return rough(o)
    leg, line = o.Geometry, pn["line"]
    u = leg.PointAtEnd - leg.PointAtStart  # from the edge towards the apex
    u.Unitize()
    big = line.GetBoundingBox(True).Diagonal.Length
    x = Intersection.CurveCurve(LineCurve(leg.PointAtStart - u * big, leg.PointAtEnd + u * big), line, tol, tol)
    if not x or not x.Count:
        return rough(o)
    e = min((ev.PointA for ev in x), key=leg.PointAtStart.DistanceTo)
    t = line.TangentAt(line.ClosestPoint(e)[1])
    try:
        w = float(a.GetUserString("NotchW") or 0)
    except ValueError:
        w = 0.0
    return e + t * ((w if u * t > 0 else -w) / 2.0)


def ask(doc):
    """Options Tool / … / Originals / Reach / Angle. True — Enter (convert), False — Esc."""
    C = Rhino.Input.Custom
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    num = tool_numbers(doc)
    reach = C.OptionDouble(sc.sticky.get(STICKY + "_reach", REACH_MM * mm), 0.0, 1e6)
    keep = C.OptionToggle(sc.sticky.get(STICKY + "_keep", False), "Delete", "Keep")
    a = C.OptionDouble(opt("angle"), 1.0, 179.0)
    while True:
        go = C.GetOption()
        go.SetCommandPrompt(u"New notch format (Enter — convert)")
        go.AcceptNothing(True)
        idx, i_std = tool_options(go, num)
        go.AddOptionToggle("Originals", keep)
        go.AddOptionDouble("Reach", reach)
        go.AddOptionDouble("Angle", a)
        r = go.Get()
        for k, v in num.items():
            sc.sticky[STICKY + "_" + k] = v.CurrentValue
        sc.sticky.update({STICKY + "_reach": reach.CurrentValue, STICKY + "_keep": keep.CurrentValue,
                          STICKY + "_angle": a.CurrentValue})
        if r != Rhino.Input.GetResult.Option:
            return r == Rhino.Input.GetResult.Nothing
        i = go.OptionIndex()
        if i == i_std:  # plotter standard into sticky and into the option fields shown
            use_standard(doc)
            for k in ("kdepth", "over", "move"):
                num[k].CurrentValue = opt(k, doc)
            a.CurrentValue = opt("angle")
        if i in idx:
            sc.sticky[STICKY + "_" + idx[i]] = go.Option().CurrentListOptionIndex


def convert(doc, panels, sources, tol):
    """Replaces sources (notch / mark objects) by notches in the current format. (made, skipped)."""
    angle = opt("angle")
    reach = sc.sticky.get(STICKY + "_reach", REACH_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters,
                                                                                    doc.ModelUnitSystem))
    near = max(MATCH_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem), 10 * tol)
    pns = [pn for pn in (prep(doc, i, angle, tol) for i in panels) if pn]
    spots = []  # [panel, point on the sew line, edge index, groups, source ids]
    skipped = 0
    for o in sources:
        r = rough(o)
        d, pn = min(((min(pn["lp"].PointAt(pn["lp"].ClosestPoint(r)[1]).DistanceTo(r),
                           pn["line"].PointAt(pn["line"].ClosestPoint(r)[1]).DistanceTo(r)), pn) for pn in pns),
                    key=lambda dp: dp[0]) if pns else (None, None)
        if pn is None or d > reach + tol:
            skipped += 1
            continue
        p = anchor(o, pn, tol)
        q = pn["lp"].PointAt(pn["lp"].ClosestPoint(p)[1])
        groups = set(o.Attributes.GetGroupList() or [])
        for s in spots:
            if s[0] is pn and s[1].DistanceTo(q) <= near:  # same spot: one notch
                s[3] |= groups
                s[4].append(o.Id)
                break
        else:
            es = pn["es"]
            k = min(range(len(es)), key=lambda i: es[i].PointAt(es[i].ClosestPoint(q)[1]).DistanceTo(q))
            spots.append([pn, q, k, groups, [o.Id]])
    p = spec(dict((k, opt(k, doc)) for k in DEFAULTS))
    keep = sc.sticky.get(STICKY + "_keep", False)
    for pn, q, k, groups, ids in spots:
        e = pn["es"][k]
        out = Vector3d.CrossProduct(e.TangentAt(e.ClosestPoint(q)[1]), pn["normal"])
        out.Unitize()
        attrs = notch_attrs(doc, p, sorted(groups | set(pn["obj"].Attributes.GetGroupList() or [])))
        for g in shapes(q + out * pn["widths"][k], out, pn["normal"], p):
            doc.Objects.AddCurve(g, attrs)
        for i in ids:
            if not keep or doc.Objects.FindId(i).Attributes.GetUserString(NOTCH):
                doc.Objects.Delete(i, True)
    if spots:  # knife V geometry; warning against the narrowest seam the notches sit on
        seams = [pn["widths"][k] for pn, q, k, g, i in spots if pn["widths"][k] > tol]
        tell(p, min(seams) if seams else 0.0, tol)
    return len(spots), skipped


HELP = u"""Options (the format of the new notches):
  Tool — Mark: pen, layer INK (Style Slit / V, Width for V, Depth, Placement In / Out / Center);
    Cut: knife, layer INT — the V for the circular blade (Depth, Overcut, Move; Standard — the plotter standard)
  Originals — older marks (points, seam circles, old ticks): Delete / Keep; notches are always replaced
  Reach — how far a mark may be from a panel edge (default 20 mm)
  Angle — a break larger than this angle = corner (edges are taken corner to corner)"""  # printed at start


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select the notches / older battute together with their panels", rs.filter.point |
                        rs.filter.curve, preselect=True)
    if not ids:
        return
    kinds = dict((i, kind(doc, i)) for i in ids)
    sources = [doc.Objects.FindId(i) for i in ids if kinds[i] in ("notch", "mark")]
    panels = [i for i in ids if kinds[i] == "panel"]
    if not sources:
        print(u"No notches or older battute in the selection.")
        return
    if not panels:
        more = rs.GetObjects(u"Select the panels (closed curves = sew lines)", rs.filter.curve) or []
        panels = [i for i in more if kind(doc, i) == "panel"]
        if not panels:
            return
    if not ask(doc):
        return
    made, skipped = convert(doc, panels, sources, doc.ModelAbsoluteTolerance)
    doc.Views.Redraw()
    print(u"Converted: %d notches from %d objects%s" % (
        made, len(sources), u"; skipped %d — no panel edge within Reach" % skipped if skipped else u""))


if __name__ == "__main__":
    main()
