# -*- coding: utf-8 -*-
"""Seams — seam allowance after PatternSmith (Pattern Editor > Toolbar > Seams).
The panel (closed curve) is the sew line. Its seam allowance is a separate closed cut line around it,
layer Pattern::Seams; the panel itself is not changed. Each edge (corner to corner — a break larger than Angle)
has its own width: select panels, then click near an edge (several in a row, Enter — done) — the edge gets
the current Width (one of the presets, 8 / 10 / 12 / 15 / 20 mm; Edit — change them, kept in the .3dm),
Width=Off — the edge loses its seam. Where neighbouring seams meet, the corner style decides (Mode=Corner,
click near a corner): Extend — both seams extend to their intersection, but at most by one seam width;
Slant — each seam extends to the sew line of the neighbouring edge (corner cut straight across);
Return — the seam returns at 90° to the sew line at the corner. Inner corners — the seams are cut where they cross.
All — the same for every edge / corner of the selected panels.
The widths and corner styles live in the cut line's UserText (Seams, SeamCorners) keyed by points (edge middle,
corner), not by object ids: the next click on the panel finds its cut line again and rebuilds it.
Later PreparePanelCut makes the cut line the outer contour on CUT and the panel edges the sew line on INK.
"""
import math
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import (Curve, CurveEnd, CurveExtensionStyle, CurveOffsetCornerStyle, CurveOrientation,
                            Line, LineCurve, Point3d, PolylineCurve, Vector3d)
from Rhino.Geometry.Intersect import Intersection

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
sys.modules.pop("ZipCover", None)  # Rhino keeps modules from the first run for the session
from ZipCover import close_panel, layer_attrs  # "almost closed" DXF panels, <parent>::<name> layer
sys.path.insert(0, os.path.dirname(HERE))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

STICKY = "Seams"
PARENT, NAME = "Pattern", "Seams"  # cut lines: layer Pattern::Seams
KEY, CORNERS = "Seams", "SeamCorners"  # UserText on the cut line: edge widths, corner styles
PRESETS_MM = [8.0, 10.0, 12.0, 15.0, 20.0]  # PatternSmith: five preset widths
MODES = ["Seam", "Corner"]
STYLES = ["Extend", "Slant", "Return"]
MATCH_MM = 1.0  # a stored edge middle / corner within this of the panel — still the same edge / corner
ALL = "all"  # what the click prompt returns for the option All


def mid(c):
    ok, t = c.LengthParameter(c.GetLength() / 2.0)
    return c.PointAt(t if ok else c.Domain.Mid)


def loop(crv, normal):
    """Closed copy of the panel, counter-clockwise around normal (outside on the right of the direction), or None."""
    c = close_panel(crv)
    if c is None:
        return None
    c = c.DuplicateCurve()
    if c.ClosedCurveOrientation(normal) == CurveOrientation.Clockwise:
        c.Reverse()
    return c


def edges(lp, angle, tol):
    """Edges corner to corner in loop order: edge k runs from corner k to corner k + 1.
    Fewer than two corners (circle, drop) — one closed edge, the whole loop."""
    segs = [s for s in lp.DuplicateSegments() if s.GetLength() > tol] or [lp.DuplicateCurve()]
    n = len(segs)
    corners = [i for i in range(n)
               if Vector3d.VectorAngle(segs[i - 1].TangentAtEnd, segs[i].TangentAtStart) > math.radians(angle)]
    if len(corners) < 2:
        return [lp.DuplicateCurve()]
    out = []
    for j, s in enumerate(corners):
        k = (corners[(j + 1) % len(corners)] - s) % n or n
        out.append(Curve.JoinCurves([segs[(s + m) % n] for m in range(k)], tol)[0])
    return out


def offset(edge, w, normal, tol):
    """Edge moved by w to the right of its direction (outside the counter-clockwise panel); w = 0 — the edge itself."""
    if w <= tol:
        return edge.DuplicateCurve()
    t = edge.Domain.Mid
    side = Vector3d.CrossProduct(edge.TangentAt(t), normal)
    offs = edge.Offset(edge.PointAt(t) + side * w, normal, w, tol, CurveOffsetCornerStyle.Sharp)
    offs = Curve.JoinCurves(offs, tol) if offs else None
    if not offs:
        return None
    o = max(offs, key=lambda c: c.GetLength())
    if not o.IsClosed and o.PointAtStart.DistanceTo(edge.PointAtStart) > o.PointAtEnd.DistanceTo(edge.PointAtStart):
        o.Reverse()
    return o


def ray(p, d, q, e):
    """Distance along the unit direction d from p to the line through q along e; None — parallel."""
    ok, s, _ = Intersection.LineLine(Line(p, p + d), Line(q, q + e))
    return s if ok else None


def corner(a, b, c, wa, wb, style, cap, tol):
    """How seam a (edge before corner c, width wa) meets seam b (edge after it, width wb):
    (trim parameter of a's end or None, straight extension of a's end, the same for b's start, connector points)."""
    x = Intersection.CurveCurve(a, b, tol, tol)
    if x and x.Count:  # seams cross (inner corner; seam-less edges meet at c) — both cut at the crossing nearest c
        # ponytail: nearest crossing to the corner; a narrow panel whose far seams cross too is not handled
        ev = min(x, key=lambda ev: ev.PointA.DistanceTo(c))
        return ev.ParameterA, 0.0, ev.ParameterB, 0.0, []
    pa, pb = a.PointAtEnd, b.PointAtStart
    da, db = a.TangentAtEnd, -b.TangentAtStart  # each seam's own direction past the corner
    if style == "Return":  # 90° back to the sew line at the corner
        return None, 0.0, None, 0.0, [pa, c, pb]
    if style == "Slant":  # each seam to the sew line of the other edge (its tangent line at the corner)
        la, lb = ray(pa, da, c, db), ray(pb, db, c, da)
    else:  # Extend: to the intersection of both, at most by one seam width
        la, lb = ray(pa, da, pb, db), ray(pb, db, pa, da)
        la, lb = min(la or 0.0, wa), min(lb or 0.0, wb)
    # ponytail: an almost parallel neighbour would send Slant far away — capped at 10 seam widths
    la, lb = max(0.0, min(la or 0.0, cap)), max(0.0, min(lb or 0.0, cap))
    return None, la, None, lb, [pa + da * la, pb + db * lb]


def piece(o, t0, t1):
    """o between the trim parameters (None — its own end); None — nothing left."""
    d = o.Domain
    t0 = d.T0 if t0 is None else t0
    t1 = d.T1 if t1 is None else t1
    eps = 1e-9 * max(1.0, d.Length)
    if t1 - t0 <= eps:
        return None
    if t0 <= d.T0 + eps and t1 >= d.T1 - eps:
        return o.DuplicateCurve()
    return o.Trim(t0, t1)


def build(es, widths, styles, normal, tol):
    """Closed cut line around the edges es (counter-clockwise; corner k = start of edge k), or None."""
    if len(es) == 1:
        o = offset(es[0], widths[0], normal, tol)
        return o if o is not None and o.IsClosed else None
    offs = [offset(e, w, normal, tol) for e, w in zip(es, widths)]
    if any(o is None for o in offs):
        return None
    n, cap = len(es), 10 * max(widths)
    cs = [corner(offs[k - 1], offs[k], es[k].PointAtStart, widths[k - 1], widths[k], styles[k], cap, tol)
          for k in range(n)]
    pieces = []
    for k in range(n):
        s, e = cs[k], cs[(k + 1) % n]
        o = piece(offs[k], s[2], e[0])
        if o is not None and s[3] > tol:
            o = o.Extend(CurveEnd.Start, s[3], CurveExtensionStyle.Line)
        if o is not None and e[1] > tol:
            o = o.Extend(CurveEnd.End, e[1], CurveExtensionStyle.Line)
        if o is None:
            return None  # edge eaten by its neighbours' seams, or extension failed
        pieces.append(o)
        pieces += [LineCurve(p, q) for p, q in zip(e[4], e[4][1:]) if p.DistanceTo(q) > tol]
    joined = Curve.JoinCurves(pieces, 2 * tol)
    if len(joined) != 1 or not joined[0].IsClosed:
        return None
    out = joined[0]
    ok, pl = out.TryGetPolyline()  # a clean polyline if everything is straight (PreparePanelCut)
    if ok:
        pl.DeleteShortSegments(tol)
        out = PolylineCurve(pl)
    return out


def parse(text):
    """UserText "x,y,z=value;…" → [(point, value)]."""
    out = []
    for item in (text or "").split(";"):
        if "=" in item:
            p, v = item.split("=", 1)
            x, y, z = (float(c) for c in p.split(","))
            out.append((Point3d(x, y, z), v))
    return out


def dump(items):
    return ";".join("%.4f,%.4f,%.4f=%s" % (p.X, p.Y, p.Z, v) for p, v in items)


def width_of(edge, stored, near):
    """Stored width of the edge: the stored middle lying on it (nearest its own middle); none — 0."""
    m = mid(edge)
    on = [(p.DistanceTo(m), float(v)) for p, v in stored
          if edge.PointAt(edge.ClosestPoint(p)[1]).DistanceTo(p) <= near]
    return min(on)[1] if on else 0.0


def style_of(pt, stored, near):
    on = [(p.DistanceTo(pt), v) for p, v in stored if p.DistanceTo(pt) <= near and v in STYLES]
    return min(on)[1] if on else STYLES[0]


def find_cut(doc, lp, near):
    """Cut line object of the panel loop lp: on Pattern::Seams, most of its stored edge middles lie on the panel
    (a neighbour sharing one edge has fewer). None — not made yet."""
    idx = doc.Layers.FindByFullPath(PARENT + "::" + NAME, -1)
    if idx < 0:
        return None
    s = Rhino.DocObjects.ObjectEnumeratorSettings()
    s.HiddenObjects = s.LockedObjects = True
    s.LayerIndexFilter = idx
    best, score = None, 0
    for o in doc.Objects.GetObjectList(s):
        pts = [p for p, _ in parse(o.Attributes.GetUserString(KEY))]
        k = sum(1 for p in pts if lp.PointAt(lp.ClosestPoint(p)[1]).DistanceTo(p) <= near)
        if 2 * k > len(pts) and k > score:
            best, score = o, k
    return best


def presets(doc):
    """Preset widths in mm: from the .3dm (Edit), else PRESETS_MM."""
    s = doc.Strings.GetValue(STICKY, "presets")
    try:
        vals = [float(v) for v in s.split()] if s else []
    except ValueError:
        vals = []
    return [v for v in vals if v > 0] or list(PRESETS_MM)


def edit_presets(doc):
    cur = " ".join("%g" % p for p in presets(doc))
    gs = Rhino.Input.Custom.GetString()
    gs.SetCommandPrompt(u"Seam allowance presets, mm (separated by spaces)")
    gs.SetDefaultString(cur)
    gs.AcceptNothing(True)
    if gs.GetLiteralString() != Rhino.Input.GetResult.String:  # not rs.GetString: there space = Enter
        return  # Esc / Enter — nothing to change
    s = gs.StringResult()
    try:
        vals = [float(v) for v in (s or "").replace(";", " ").replace(",", ".").split()]  # 12,5 = 12.5
    except ValueError:
        vals = []
    if vals and all(v > 0 for v in vals):
        doc.Strings.SetString(STICKY, "presets", " ".join("%g" % v for v in vals))
    else:
        print(u"Presets not changed: %s" % s)


def label(v):
    return ("%g" % v).replace(".", "_")  # option values: no dots


def ask(gp, doc):
    """Click with options Undo / Mode / Width / Edit (Seam) or Corner (Corner) / All / Angle.
    A point, UNDO, ALL or None (Enter / Esc). Mode, width index, corner style, angle — in sc.sticky."""
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    while True:
        mode = sc.sticky.setdefault(STICKY + "_mode", 0)
        gp.ClearCommandOptions()
        gp.SetCommandPrompt(u"Click near an edge — it gets the seam (Enter — done)" if mode == 0 else
                            u"Click near a corner — it gets the corner style (Enter — done)")
        i_undo = gp.AddOption("Undo")
        i_mode = gp.AddOptionList("Mode", MODES, mode)
        i_w = i_edit = i_c = -1
        if mode == 0:
            labels = [label(v) for v in presets(doc)] + ["Off"]
            w = min(sc.sticky.setdefault(STICKY + "_width", 1), len(labels) - 1)
            i_w = gp.AddOptionList("Width", labels, w)
            i_edit = gp.AddOption("Edit")
        else:
            i_c = gp.AddOptionList("Corner", STYLES, sc.sticky.setdefault(STICKY + "_corner", 0))
        i_all = gp.AddOption("All")
        gp.AddOptionDouble("Angle", a)
        r = gp.Get()
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            i = gp.OptionIndex()
            if i == i_undo:
                return UNDO
            if i == i_all:
                return ALL
            if i == i_mode:
                sc.sticky[STICKY + "_mode"] = gp.Option().CurrentListOptionIndex
            elif i == i_w:
                sc.sticky[STICKY + "_width"] = gp.Option().CurrentListOptionIndex
            elif i == i_edit:
                edit_presets(doc)
            elif i == i_c:
                sc.sticky[STICKY + "_corner"] = gp.Option().CurrentListOptionIndex
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


def up_normal(crv, doc, tol):
    """Plane normal of the curve, turned to the CPlane up (one up direction for every panel)."""
    view = doc.Views.ActiveView
    up = view.ActiveViewport.ConstructionPlane().ZAxis if view else Vector3d.ZAxis  # headless: WorldXY
    ok, plane = crv.TryGetPlane(tol)
    n = plane.ZAxis if ok else up
    return -n if n * up < 0 else n


def apply(doc, oid, click, steps, tol):
    """Mode Seam: the edge near click (None — every edge) gets the current width; Mode Corner: the corner near click
    (None — every corner) gets the current style. The panel's cut line is made / rebuilt / deleted (no seam left).
    None — done, else why skipped."""
    obj = doc.Objects.FindId(oid)
    crv = obj.Geometry if obj else None
    if not isinstance(crv, Curve):
        return u"not a curve"
    normal = up_normal(crv, doc, tol)
    lp = loop(crv, normal)
    if lp is None:
        return u"panel is not closed"
    es = edges(lp, sc.sticky.get(STICKY + "_angle", 30.0), tol)
    near = max(MATCH_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem), 10 * tol)
    cut = find_cut(doc, lp, near)
    attrs = cut.Attributes.Duplicate() if cut else None
    widths = [width_of(e, parse(attrs.GetUserString(KEY)) if attrs else [], near) for e in es]
    styles = [style_of(e.PointAtStart, parse(attrs.GetUserString(CORNERS)) if attrs else [], near) for e in es]
    mode = sc.sticky.get(STICKY + "_mode", 0)
    if click is None:
        pick = range(len(es))
    elif mode == 0:
        pick = [min(range(len(es)), key=lambda k: es[k].PointAt(es[k].ClosestPoint(click)[1]).DistanceTo(click))]
    else:
        pick = [min(range(len(es)), key=lambda k: es[k].PointAtStart.DistanceTo(click))]
    if mode == 0:
        ps = presets(doc)
        i = sc.sticky.get(STICKY + "_width", 1)
        w = ps[i] * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem) if i < len(ps) else 0.0
        for k in pick:
            widths[k] = w
    elif cut is None:
        return u"no seam on this panel yet (Mode=Seam first)"
    else:
        for k in pick:
            styles[k] = STYLES[sc.sticky.get(STICKY + "_corner", 0)]
    if max(widths) <= tol:
        if cut:
            steps.delete(cut.Id)
        return None
    new = build(es, widths, styles, normal, tol)
    if new is None:
        return u"cut line did not close (edge too short for its seam?)"
    if attrs is None:
        attrs = layer_attrs(doc, NAME, PARENT)
        for g in obj.Attributes.GetGroupList() or []:  # moves / selects together with the panel
            attrs.AddToGroup(g)
    attrs.SetUserString(KEY, dump([(mid(e), "%.6g" % w) for e, w in zip(es, widths)]))
    attrs.SetUserString(CORNERS, dump([(e.PointAtStart, s) for e, s in zip(es, styles)]))
    if cut:
        steps.change(cut.Id)
        doc.Objects.Replace(cut.Id, new)
        doc.Objects.ModifyAttributes(cut.Id, attrs, True)
    else:
        doc.Objects.AddCurve(new, attrs)
    return None


HELP = u"""Options:
  Mode — Seam: click near a panel edge, it gets the seam Width; Corner: click near a corner, it gets the Corner style
  Width — seam allowance, one of the presets (mm); Off — the edge loses its seam
  Edit — change the preset widths (kept in the .3dm)
  Corner — Extend: seams extend to their intersection, at most one seam width; Slant: each seam to the neighbour's
    sew line (corner cut across); Return: the seam returns at 90° to the sew line
  All — the same for every edge / corner of the selected panels
  Angle — a break larger than this angle = corner (edges are taken corner to corner)
  Undo — take back the last click (again — the click before it)"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select panels (closed curves = sew lines)", rs.filter.curve, preselect=True)
    ids = [i for i in ids or [] if not rs.GetUserText(i, KEY)]  # own cut lines are not panels
    if not ids:
        return
    tol = doc.ModelAbsoluteTolerance
    steps = Steps(doc)
    made = 0
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.AcceptNothing(True)
        click = ask(gp, doc)
        if click is None:
            break
        if click == UNDO:
            if steps.undo():
                made -= 1
            continue
        steps.start()
        if click == ALL:
            todo = [(i, None) for i in ids]
        else:
            crvs = [(i, rs.coercecurve(i)) for i in ids]
            near = min((ic for ic in crvs if ic[1]), key=lambda ic: ic[1].PointAt(ic[1].ClosestPoint(click)[1]).DistanceTo(click))
            todo = [(near[0], click)]
        for oid, pt in todo:
            res = apply(doc, oid, pt, steps, tol)
            if res:
                print(u"Skipped: %s" % res)
        made += 1
        doc.Views.Redraw()
    print(u"Seams: %d clicks → %s::%s" % (made, PARENT, NAME))


if __name__ == "__main__":
    main()
