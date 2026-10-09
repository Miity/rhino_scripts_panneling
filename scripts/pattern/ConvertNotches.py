# -*- coding: utf-8 -*-
"""Convert Notches — notches already made, into another format (PatternSmith: Patterns > Modify Notches).
Select the notches together with their panels (a window over the panels works). Taken:
  - notches made by Notches (UserText Notch) — pen (Mark) or knife (Cut), any style;
  - older battute: points, seam circles (radius up to 10 mm, Crosses), lines in Parts::SewingMarks (old centre ticks).
Set the new format with the options of Notches (Tool Mark: Style, Width, Depth, Placement; Tool Cut: the knife V —
Depth, Overcut, Move, Standard), Enter — convert. Each notch / mark goes to the nearest panel edge within Reach
(perpendicular to the edge): one notch there, on the panel's cut line if it has one (Seams), else on the sew line;
marks of one spot (old point + its tick, two legs of a knife V) — one notch. The new notch keeps the groups of what
it replaces and joins the panel's groups. Notches are always replaced; older marks — Originals Delete / Keep.
Panels: the closed curves of the selection (or asked for if none); cut lines and notches are not panels.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, LineCurve, Point, Vector3d
from Rhino.Geometry.Intersect import Intersection

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _m in ("Seams", "Notches"):  # Rhino keeps modules from the first run for the session
    sys.modules.pop(_m, None)
from Notches import notch_attrs, opt, shapes, spec, tell, tool_numbers, tool_options, use_standard
from Seams import BREAK, KEY, MATCH_MM, NOTCH, breaks_on, close_panel, edges, find_cut, loop, seam_data, up_normal
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "markup"))
sys.modules.pop("PointsToCrosses", None)
from PointsToCrosses import is_mark_circle  # seam circles up to 10 mm are marks, bigger ones (holes) are not

STICKY = "ConvertNotches"  # own option values, the defaults of Notches
OLD_LAYER = "Parts::SewingMarks"  # older Battute: points + centre tick
REACH_MM = 20.0  # a mark farther than this from every selected panel edge is skipped


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
    """Options Tool / … (Notches) / Originals / Reach / Angle. True — Enter (convert), False — Esc."""
    C = Rhino.Input.Custom
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    num = tool_numbers(doc, STICKY)
    reach = C.OptionDouble(sc.sticky.get(STICKY + "_reach", REACH_MM * mm), 0.0, 1e6)
    keep = C.OptionToggle(sc.sticky.get(STICKY + "_keep", False), "Delete", "Keep")
    a = C.OptionDouble(opt("angle", prefix=STICKY), 1.0, 179.0)
    while True:
        go = C.GetOption()
        go.SetCommandPrompt(u"New notch format (Enter — convert)")
        go.AcceptNothing(True)
        idx, i_std = tool_options(go, num, STICKY)
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
            use_standard(doc, STICKY)
            for k in ("kdepth", "over", "move"):
                num[k].CurrentValue = opt(k, doc, STICKY)
            a.CurrentValue = opt("angle", prefix=STICKY)
        if i in idx:
            sc.sticky[STICKY + "_" + idx[i]] = go.Option().CurrentListOptionIndex


def convert(doc, panels, sources, tol):
    """Replaces sources (notch / mark objects) by notches in the current format. (made, skipped)."""
    angle = opt("angle", prefix=STICKY)
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
    p = spec(dict((k, opt(k, doc, STICKY)) for k in ("tool", "style", "place", "depth", "width", "kdepth", "over",
                                                      "move")))
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


HELP = u"""Options (the new format, as in Notches):
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
