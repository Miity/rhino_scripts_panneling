# -*- coding: utf-8 -*-
"""Seams — seam allowance after PatternSmith (Pattern Editor > Toolbar > Seams).
The panel (closed curve) is the sew line. Its seam allowance is a separate closed cut line around it,
layer Pattern::Seams; the panel itself is not changed. Each edge (corner to corner — a break larger than Angle)
has its own width (an edge also ends at a break point, Break.py): select panels, then click near an edge (several in a row, Enter — done) — the edge gets
the current Width (typed, mm; remembered, default 10), Width=0 — the edge loses its seam. Where neighbouring seams meet, the corner style decides (Mode=Corner,
click near a corner): Extend — both seams extend to their intersection, but at most by one seam width;
Slant — each seam extends to the sew line of the neighbouring edge (corner cut straight across);
Return — the seam returns at 90° to the sew line at the corner. Inner corners — the seams are cut where they cross.
All — the same for every edge / corner of the selected panels.
The widths and corner styles live in the cut line's UserText (Seams, SeamCorners) by edge / corner number;
the cut line is found by geometry (the one around the panel), not by ids or coordinates — moving or rotating
the panel together with its cut line keeps the link; the next click on the panel rebuilds that cut line.
Notches of the panel (Notches.py) move with the seam: out to the new cut line (back to the sew line — no seam).
Later PreparePanelCut makes the cut line the outer contour on CUT and the panel edges the sew line on INK.
"""
import math
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import (Curve, CurveEnd, CurveExtensionStyle, CurveOffsetCornerStyle, CurveOrientation,
                            Line, LineCurve, Plane, Point, PointContainment, PolylineCurve, Vector3d)
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
NOTCH = "Notch"  # UserText of a notch (Notches.py)
BREAK, BREAKS = "Break", "Breaks"  # break points (Break.py): UserText, layer Pattern::Breaks
WIDTH_MM = 10.0  # default seam allowance
MODES = ["Seam", "Corner"]
STYLES = ["Extend", "Slant", "Return"]
MATCH_MM = 1.0  # a notch within this of the cut line lies on it
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


def break_objects(doc):
    """Break point objects (Break.py) of the document."""
    idx = doc.Layers.FindByFullPath(PARENT + "::" + BREAKS, -1)
    if idx < 0:
        return []
    s = Rhino.DocObjects.ObjectEnumeratorSettings()
    s.HiddenObjects = s.LockedObjects = True
    s.LayerIndexFilter = idx
    return [o for o in doc.Objects.GetObjectList(s) if isinstance(o.Geometry, Point) and o.Attributes.GetUserString(BREAK)]


def breaks_on(doc, lp, near):
    """Break points lying on the panel loop lp (found by geometry)."""
    pts = [o.Geometry.Location for o in break_objects(doc)]
    return [p for p in pts if lp.PointAt(lp.ClosestPoint(p)[1]).DistanceTo(p) <= near]


def edges(lp, angle, tol, breaks=()):
    """Edges corner to corner in loop order: edge k runs from corner k to corner k + 1. Corners — direction breaks
    larger than angle and the break points (PatternSmith Break) on the loop.
    Fewer than two corners (circle, drop) — one closed edge, the whole loop."""
    near = 10 * tol

    def cuts(s):  # parameters of the break points inside segment s
        ts = []
        for p in breaks:
            t = s.ClosestPoint(p)[1]
            q = s.PointAt(t)
            if q.DistanceTo(p) <= near and q.DistanceTo(s.PointAtStart) > near and q.DistanceTo(s.PointAtEnd) > near:
                ts.append(t)
        return sorted(ts)

    segs = []
    for s in lp.DuplicateSegments() or [lp.DuplicateCurve()]:
        if s.GetLength() <= tol:
            continue
        ts = cuts(s)
        if ts and s.IsClosed:  # one closed segment (circle): it starts at the first break point
            s = s.DuplicateCurve()
            s.ChangeClosedCurveSeam(ts[0])
            ts = cuts(s)
        b = [s.Domain.T0] + ts + [s.Domain.T1]
        segs += [p for p in (s.Trim(x, y) for x, y in zip(b, b[1:]) if y - x > 1e-9) if p] if ts else [s]
    n = len(segs)
    rad = math.radians(angle)
    corners = sorted(set(i for i in range(n) if Vector3d.VectorAngle(segs[i - 1].TangentAtEnd, segs[i].TangentAtStart) > rad)
                     | set(i for i in range(n) for p in breaks if segs[i].PointAtStart.DistanceTo(p) <= near))
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


def measured(e, line, normal, tol):
    """Seam width of edge e read off its cut line: from the edge middle straight out to the line (on it — 0)."""
    m = mid(e)
    if line.PointAt(line.ClosestPoint(m)[1]).DistanceTo(m) <= 10 * tol:
        return 0.0
    out = Vector3d.CrossProduct(e.TangentAt(e.ClosestPoint(m)[1]), normal)
    out.Unitize()
    x = Intersection.CurveCurve(LineCurve(m, m + out * line.GetBoundingBox(True).Diagonal.Length), line, tol, tol)
    d = [ev.PointA.DistanceTo(m) for ev in x] if x else []
    return round(min(d), 6) if d else 0.0


def seam_data(cut, es, normal, tol):
    """(widths, corner styles) of the edges es (loop order; corner k = start of edge k) from the cut line object
    (None — no seam yet). Stored by number; another edge count (panel edited) or an older drawing — widths read
    off the cut line itself, corners Extend."""
    n = len(es)
    if cut is None:
        return [0.0] * n, [STYLES[0]] * n
    a = cut.Attributes
    try:
        ws = [float(v) for v in (a.GetUserString(KEY) or "").split(";")]
    except ValueError:  # older drawing: "x,y,z=width" items
        ws = []
    cs = (a.GetUserString(CORNERS) or "").split(";")
    if len(ws) != n:
        ws = [measured(e, cut.Geometry, normal, tol) for e in es]
    if len(cs) != n or any(c not in STYLES for c in cs):
        cs = [STYLES[0]] * n
    return ws, cs


def find_cut(doc, lp, es, normal, tol):
    """Cut line object of the panel: the smallest closed curve on Pattern::Seams (UserText Seams) with every edge
    middle of the panel inside it or on it. By geometry — it follows panel + cut line moved / rotated together.
    None — not made yet."""
    # ponytail: a panel lying inside another panel's cut line (a hole) takes that one if it has none of its own
    idx = doc.Layers.FindByFullPath(PARENT + "::" + NAME, -1)
    if idx < 0:
        return None
    s = Rhino.DocObjects.ObjectEnumeratorSettings()
    s.HiddenObjects = s.LockedObjects = True
    s.LayerIndexFilter = idx
    plane = Plane(lp.PointAtStart, normal)
    pts = [mid(e) for e in es]
    best, size = None, None
    for o in doc.Objects.GetObjectList(s):
        c = o.Geometry
        if not o.Attributes.GetUserString(KEY) or not isinstance(c, Curve) or not c.IsClosed:
            continue
        if any(c.Contains(p, plane, tol) not in (PointContainment.Inside, PointContainment.Coincident) for p in pts):
            continue
        d = c.GetBoundingBox(True).Diagonal.Length
        if best is None or d < size:
            best, size = o, d
    return best


def ask(gp, doc):
    """Click with options Undo / Mode / Width (Seam) or Corner (Corner) / All / Angle.
    A point, UNDO, ALL or None (Enter / Esc). Mode, width, corner style, angle — in sc.sticky."""
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_width", WIDTH_MM * mm), 0.0, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    while True:
        mode = sc.sticky.setdefault(STICKY + "_mode", 0)
        gp.ClearCommandOptions()
        gp.SetCommandPrompt(u"Click near an edge — it gets the seam (Enter — done)" if mode == 0 else
                            u"Click near a corner — it gets the corner style (Enter — done)")
        i_undo = gp.AddOption("Undo")
        i_mode = gp.AddOptionList("Mode", MODES, mode)
        i_c = -1
        if mode == 0:
            gp.AddOptionDouble("Width", w)
        else:
            i_c = gp.AddOptionList("Corner", STYLES, sc.sticky.setdefault(STICKY + "_corner", 0))
        i_all = gp.AddOption("All")
        gp.AddOptionDouble("Angle", a)
        r = gp.Get()
        sc.sticky[STICKY + "_width"] = w.CurrentValue
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            i = gp.OptionIndex()
            if i == i_undo:
                return UNDO
            if i == i_all:
                return ALL
            if i == i_mode:
                sc.sticky[STICKY + "_mode"] = gp.Option().CurrentListOptionIndex
            elif i == i_c:
                sc.sticky[STICKY + "_corner"] = gp.Option().CurrentListOptionIndex
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


def edge_of(es, q, widths):
    """Index of the edge whose seam line (offset by its width) q lies on: q right beside the edge (not past its ends)
    first, then the smallest miss."""
    def key(k):
        e = es[k]
        t = e.ClosestPoint(q)[1]
        eps = 1e-9 * max(1.0, e.Domain.Length)
        return (not e.Domain.T0 + eps < t < e.Domain.T1 - eps, abs(e.PointAt(t).DistanceTo(q) - widths[k]))
    return min(range(len(es)), key=key)


def move_notches(doc, es, old, new, line, normal, steps, near):
    """Notches lying on line (the old cut line, or the panel if it had none; knife V legs — within their depth of it)
    move with the seam: along the outside of their edge by its new − old width (PatternSmith: notches move out
    to the cut line)."""
    # ponytail: a notch on an edge shared with another panel's sew line moves with whichever panel changes first
    s = Rhino.DocObjects.ObjectEnumeratorSettings()
    s.HiddenObjects = s.LockedObjects = True
    for o in doc.Objects.GetObjectList(s):
        g = o.Geometry
        if not o.Attributes.GetUserString(NOTCH) or not isinstance(g, Curve):
            continue
        ok, q, r = g.ClosestPoints(line)
        reach = 0.0
        if o.Attributes.GetUserString("NotchTool") == "Cut":  # knife V legs start inside, within its depth
            try:
                reach = float(o.Attributes.GetUserString("NotchD") or 0)
            except ValueError:
                pass
        if not ok or q.DistanceTo(r) > near + reach:
            continue
        k = edge_of(es, r, old)
        d = new[k] - old[k]
        if abs(d) < 1e-9:
            continue
        out = Vector3d.CrossProduct(es[k].TangentAt(es[k].ClosestPoint(r)[1]), normal)
        out.Unitize()
        g = g.Duplicate()
        g.Translate(out * d)
        steps.change(o.Id)
        doc.Objects.Replace(o.Id, g)


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
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    near = max(MATCH_MM * mm, 10 * tol)
    es = edges(lp, sc.sticky.get(STICKY + "_angle", 30.0), tol, breaks_on(doc, lp, near))
    cut = find_cut(doc, lp, es, normal, tol)
    attrs = cut.Attributes.Duplicate() if cut else None
    widths, styles = seam_data(cut, es, normal, tol)
    old, line = list(widths), cut.Geometry.Duplicate() if cut else lp  # notches sit on line now
    mode = sc.sticky.get(STICKY + "_mode", 0)
    if click is None:
        pick = range(len(es))
    elif mode == 0:
        pick = [min(range(len(es)), key=lambda k: es[k].PointAt(es[k].ClosestPoint(click)[1]).DistanceTo(click))]
    else:
        pick = [min(range(len(es)), key=lambda k: es[k].PointAtStart.DistanceTo(click))]
    if mode == 0:
        w = sc.sticky.get(STICKY + "_width", WIDTH_MM * mm)
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
            move_notches(doc, es, old, widths, line, normal, steps, near)
        return None
    new = build(es, widths, styles, normal, tol)
    if new is None:
        return u"cut line did not close (edge too short for its seam?)"
    if attrs is None:
        attrs = layer_attrs(doc, NAME, PARENT)
        for g in obj.Attributes.GetGroupList() or []:  # moves / selects together with the panel
            attrs.AddToGroup(g)
    attrs.SetUserString(KEY, ";".join("%.6g" % w for w in widths))  # by edge number, loop order
    attrs.SetUserString(CORNERS, ";".join(styles))  # by corner number
    if cut:
        steps.change(cut.Id)
        doc.Objects.Replace(cut.Id, new)
        doc.Objects.ModifyAttributes(cut.Id, attrs, True)
    else:
        doc.Objects.AddCurve(new, attrs)
    move_notches(doc, es, old, widths, line, normal, steps, near)
    return None


HELP = u"""Options:
  Mode — Seam: click near a panel edge, it gets the seam Width; Corner: click near a corner, it gets the Corner style
  Width — seam allowance (mm), type the one you need now; 0 — the edge loses its seam
  Corner — Extend: seams extend to their intersection, at most one seam width; Slant: each seam to the neighbour's
    sew line (corner cut across); Return: the seam returns at 90° to the sew line
  All — the same for every edge / corner of the selected panels
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
