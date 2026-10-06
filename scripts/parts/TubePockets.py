# -*- coding: utf-8 -*-
"""Tube pockets in a cover.
Select a panel (closed curve), then click near an edge (several in a row, Enter — done).
Edge — corner to corner (corner — tangent break larger than Angle, as in ZipCover). The pocket is a segment
of the edge of width W centred (middle by length; 0 — the whole edge), offset by height H into the panel;
the offset line is shorter by Trim at each end (the pocket narrows).
Seam allowance SA goes from the edge outward from the panel. The seam line is a copy of the segment in the group.
Option Notch — centre mark (a tick across the seam line at the middle). The part lies in place, in layer
Parts::Pockets, with label "TP<n>  H=…" in a group; TP numbering continues. The panel is not changed.
Option Rigid — pocket by rigid offset (curves/OffsetRigid.py): a copy of the segment without changing its shape,
moved by H along the normal at the pocket centre (Rigid=No — standard offset; SA is always a standard offset).
Option Hem — hem allowance at the ends (+Hem left and right): the end moves outward by Hem, the top and bottom
of the pocket are extended to it straight; the old end stays in the group as a fold line, in sublayer <layer>::Fold (Hem=0 — none).
Only markup stays on the panel (in place): ends + pocket top as one open curve (without seam line, SA and Hem)
+ label, its own group (UserText TP_Markup). The full part for cutting — UP (10000) up along CPlane Y
(UserText TP_Up), that is what Layout lays out. Both groups are linked by number (UserText TP_N).
Option Layout (default Yes): No — full part in place, no markup (like old pockets).
Options W / H / Trim / SA / Hem / Notch / Rigid / Layout / Angle — in the click prompt, remembered between runs.
"""
import os
import re
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import (Curve, CurveEnd, CurveExtensionStyle, CurveOffsetCornerStyle, CurveOrientation, LineCurve,
                            Polyline, PolylineCurve, Transform, Vector3d)
from Rhino.Geometry.Intersect import Intersection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _m in ("ZipCover", "Seam"):  # Rhino keeps modules from the first run for the session — take fresh ones
    sys.modules.pop(_m, None)
from ZipCover import pick_edge  # panel edge corner to corner near the click
from Seam import label_frame, text_style  # the same label along the strip and PAT style
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "curves"))
sys.modules.pop("OffsetRigid", None)
from OffsetRigid import shift  # rigid offset: move along the normal at a point

STICKY = "TubePockets"
LAYER = "Parts::Pockets"
PREFIX = "TP"  # Tube Pocket
UP = 10000.0  # the full part is this far up along CPlane Y from the markup on the panel


def offset(crv, toward, d, normal, tol):
    """Offset of an open curve by d towards point toward, in the same direction as crv. None — failed."""
    offs = crv.Offset(toward, normal, d, tol, CurveOffsetCornerStyle.Sharp)
    offs = Curve.JoinCurves(offs, tol) if offs else None
    if not offs:
        return None
    o = max(offs, key=lambda c: c.GetLength())
    if o.PointAtStart.DistanceTo(crv.PointAtStart) > o.PointAtEnd.DistanceTo(crv.PointAtStart):
        o.Reverse()
    return o


def pocket_side(seg, toward, h, normal, tol, rigid):
    """Pocket top: offset of seg by h towards toward; rigid — a copy of seg moved along the normal at the middle of seg."""
    if not rigid:
        return offset(seg, toward, h, normal, tol)
    ok, tm = seg.LengthParameter(seg.GetLength() / 2.0)
    v = shift(seg, tm if ok else seg.Domain.Mid, normal, toward, h)
    if v is None:
        return None
    c = seg.DuplicateCurve()
    c.Translate(v)
    return c


def trim_len(crv, a, b):
    """Piece of crv between lengths a and b from the start. None — failed."""
    ok0, t0 = crv.LengthParameter(a)
    ok1, t1 = crv.LengthParameter(b)
    return crv.Trim(t0, t1) if ok0 and ok1 and t1 > t0 else None


def end_side(outer, seg, inner, tol):
    """End near the start: polyline bottom (outer) → seam line → top (inner)."""
    pts = [outer.PointAtStart]
    for p in (seg.PointAtStart, inner.PointAtStart):
        if p.DistanceTo(pts[-1]) > tol:
            pts.append(p)
    return PolylineCurve(Polyline(pts))


def hem_start(outer, seg, inner, hem, normal, tol):
    """Hem allowance near the start: the end moves outward by hem, outer and inner are extended to it straight.
    (outer, inner, new end, fold line) or None."""
    fold = end_side(outer, seg, inner, tol)
    big = 10 * (hem + fold.GetLength())
    side = offset(fold, seg.PointAtStart - seg.TangentAtStart * hem, hem, normal, tol)
    side = side.Extend(CurveEnd.Both, big, CurveExtensionStyle.Line) if side else None
    if side is None:
        return None
    out, ts = [], []
    for c in (outer, inner):
        cx = c.Extend(CurveEnd.Start, big, CurveExtensionStyle.Line)
        x = Intersection.CurveCurve(cx, side, tol, tol) if cx else None
        if not x or x.Count == 0:
            return None
        ev = min(x, key=lambda e: e.PointA.DistanceTo(c.PointAtStart))
        out.append(cx.Trim(ev.ParameterA, cx.Domain.T1))
        ts.append(ev.ParameterB)
    if None in out:
        return None
    return out[0], out[1], side.Trim(min(ts), max(ts)), fold


def reversed_copy(c):
    c = c.DuplicateCurve()
    c.Reverse()
    return c


def pocket(crv, click, w, h, trim, sa, notch, normal, tol, rigid=False, hem=0.0):
    """(contour, seam line, centre mark or None, fold lines, markup: ends + top, without seam line);
    string — the reason it failed."""
    length = crv.GetLength()
    seg = crv.DuplicateCurve() if w <= 0 or w >= length else trim_len(crv, (length - w) / 2.0, (length + w) / 2.0)
    if seg is None:
        return u"could not cut a segment of width W"
    ok, t = seg.ClosestPoint(click)
    base = seg.PointAt(t)
    away = base - (click - base)  # click mirrored across the line: allowance side
    inner = pocket_side(seg, click, h, normal, tol, rigid)
    if inner is None:
        return u"offset by H failed (non-planar curve or self-intersection?)"
    li = inner.GetLength()
    inner = trim_len(inner, trim, li - trim) if trim > 0 else inner
    if inner is None:
        return u"Trim %g on each side is longer than the pocket" % trim
    outer = offset(seg, away, sa, normal, tol) if sa > 0 else seg.DuplicateCurve()
    if outer is None:
        return u"seam allowance SA offset failed"
    simple = Curve.JoinCurves([inner, end_side(seg, seg, inner, tol),  # without seam line: the panel edge gives it
                               end_side(reversed_copy(seg), reversed_copy(seg), reversed_copy(inner), tol)], tol)
    if len(simple) != 1:
        return u"markup contour did not close"
    folds = []
    if hem > 0:
        a = hem_start(outer, seg, inner, hem, normal, tol)
        b = a and hem_start(reversed_copy(a[0]), reversed_copy(seg), reversed_copy(a[1]), hem, normal, tol)
        if not b:
            return u"hem allowance Hem failed"
        hemmed = reversed_copy(b[0]), reversed_copy(b[1])
        sides, folds = [a[2], b[2]], [a[3], b[3]]
    else:
        hemmed = outer, inner
        sides = [end_side(outer, seg, inner, tol),
                 end_side(reversed_copy(outer), reversed_copy(seg), reversed_copy(inner), tol)]
    joined = Curve.JoinCurves(list(hemmed) + sides, tol)
    if len(joined) != 1 or not joined[0].IsClosed:
        return u"pocket contour did not close"
    mark = None
    if notch:
        ok, tm = seg.LengthParameter(seg.GetLength() / 2.0)
        m = seg.PointAt(tm)
        q = inner.PointAt(inner.ClosestPoint(m)[1])
        d = q - m
        d.Unitize()
        # ponytail: goes H/10 into the pocket from the seam line; for a fixed depth — a separate option.
        mark = LineCurve(outer.PointAt(outer.ClosestPoint(m)[1]) if sa > 0 else m, m + d * (h / 10.0))
    return joined[0], seg, mark, folds, simple[0]


def add_pocket(doc, res, h, trim, sa, notch, n, attrs, normal, tol, rigid=False, hem=0.0, up=None):
    """Adds a pocket: res (contour, seam line, mark, fold lines, markup, toward) — in place.
    up=None — full part in place (old pockets); otherwise the full part is moved by up,
    and the markup stays in place (ends + top without seam line + label). Parameters — UserText for UpdateTubePockets."""
    outline, seg, mark, folds, simple, toward = res
    xf = Transform.Translation(up if up is not None else Vector3d.Zero)
    te = Rhino.Geometry.TextEntity.Create(u"%s%d  H=%g" % (PREFIX, n, h),
                                          label_frame(seg, pocket_side(seg, toward, h, normal, tol, rigid), normal),
                                          text_style(doc, h / 4.0), False, 0, 0)
    te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
    te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle

    def add(geo, a):
        geo = geo.Duplicate()
        geo.Transform(xf)
        return doc.Objects.Add(geo, a)

    fa = attrs.Duplicate()
    fa.LayerIndex = fold_layer(doc, attrs.LayerIndex) if folds else attrs.LayerIndex
    full = [add(outline, attrs)] + [add(f, fa) for f in folds]
    if sa > 0:
        full.append(add(seg, attrs))  # seam line
    if mark:
        full.append(add(mark, attrs))
    full.append(add(te, attrs))
    groups = [full]
    if up is not None:
        groups.append([doc.Objects.AddCurve(simple, attrs), doc.Objects.AddText(te, attrs)])
    for i, ids in enumerate(groups):
        for o in ids:
            for k, v in (("H", h), ("Trim", trim), ("SA", sa), ("Notch", int(notch)), ("Rigid", int(rigid)),
                         ("Hem", hem), ("N", n)):
                rs.SetUserText(o, "TP_" + k, "%g" % v)
            if up is not None:
                rs.SetUserText(o, "TP_Up", "%r,%r,%r" % (up.X, up.Y, up.Z))
            if i == 1:
                rs.SetUserText(o, "TP_Markup", "1")
        rs.AddObjectsToGroup(ids, rs.AddGroup())
    doc.Views.Redraw()
    return u"%s%d  H=%g" % (PREFIX, n, h)


def fold_layer(doc, index):
    """Sublayer Fold (fold lines) under the pocket layer, same colour."""
    lay = doc.Layers[index]
    full = lay.FullPath + "::Fold"
    if not rs.IsLayer(full):
        rs.AddLayer("Fold", lay.Color, parent=lay.FullPath)
    return doc.Layers.FindByFullPath(full, -1)


def layer():
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Pockets", parent="Parts")
    return LAYER


def next_number(lay):
    """Next number after the largest TP<n> already in the layer."""
    nums = [0]
    for o in rs.ObjectsByLayer(lay) or []:
        m = re.match(PREFIX + r"(\d+)\b", rs.TextObjectText(o) if rs.IsText(o) else "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


def inward(panel, edge, normal):
    """Point inside the panel near the edge middle (the edge follows the panel direction)."""
    tm = edge.Domain.Mid
    t = edge.TangentAt(tm)
    cw = panel.ClosedCurveOrientation(normal) == CurveOrientation.Clockwise
    out = Vector3d.CrossProduct(normal, t) if cw else Vector3d.CrossProduct(t, normal)
    out.Unitize()
    return edge.PointAt(tm) - out


def ask(gp):
    """Click near an edge with options W, H, Trim, SA, Hem, Notch, Rigid, Angle. (point, values) or None."""
    get = sc.sticky.get
    w = Rhino.Input.Custom.OptionDouble(get(STICKY + "_w", 2000.0), 0.0, 1e7)
    h = Rhino.Input.Custom.OptionDouble(get(STICKY + "_h", 130.0), 0.001, 1e6)
    trim = Rhino.Input.Custom.OptionDouble(get(STICKY + "_trim", 50.0), 0.0, 1e6)
    sa = Rhino.Input.Custom.OptionDouble(get(STICKY + "_sa", 10.0), 0.0, 1e6)
    hem = Rhino.Input.Custom.OptionDouble(get(STICKY + "_hem", 20.0), 0.0, 1e6)
    notch = Rhino.Input.Custom.OptionToggle(get(STICKY + "_notch", True), "No", "Yes")
    rigid = Rhino.Input.Custom.OptionToggle(get(STICKY + "_rigid", False), "No", "Yes")
    angle = Rhino.Input.Custom.OptionDouble(get("ZipCover_angle", 30.0), 1.0, 179.0)  # shared with ZipCover
    gp.AddOptionDouble("W", w)
    gp.AddOptionDouble("H", h)
    gp.AddOptionDouble("Trim", trim)
    gp.AddOptionDouble("SA", sa)
    gp.AddOptionDouble("Hem", hem)
    gp.AddOptionToggle("Notch", notch)
    gp.AddOptionToggle("Rigid", rigid)
    lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", True), "No", "Yes")
    gp.AddOptionToggle("Layout", lay)
    gp.AddOptionDouble("Angle", angle)
    while True:
        r = gp.Get()
        vals = (w.CurrentValue, h.CurrentValue, trim.CurrentValue, sa.CurrentValue, notch.CurrentValue, rigid.CurrentValue,
                hem.CurrentValue)
        for k, v in zip(("_w", "_h", "_trim", "_sa", "_notch", "_rigid", "_hem"), vals):
            sc.sticky[STICKY + k] = v
        sc.sticky["ZipCover_angle"] = angle.CurrentValue
        sc.sticky[STICKY + "_layout"] = lay.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            continue
        return (gp.Point(), vals + (angle.CurrentValue,)) if r == Rhino.Input.GetResult.Point else None


HELP = u"""Options:
  W — pocket width centred on the edge (0 — the whole edge)
  H — pocket height from the edge into the panel
  Trim — how much shorter the pocket top is at each end
  SA — seam allowance from the edge outward from the panel
  Hem — hem allowance at the ends, on each side (0 — none)
  Notch — pocket centre mark (a tick across the seam line)
  Rigid — Yes: top is a copy of the edge without changing its shape; No: regular offset
  Layout — Yes: only markup on the panel, full part 10000 up; No: full part in place
  Angle — a break larger than this angle = panel corner (the edge is taken corner to corner)"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    oid = rs.GetObject(u"Select a panel (closed curve)", rs.filter.curve, preselect=True)
    if not oid:
        return
    panel = rs.coercecurve(oid)
    tol = doc.ModelAbsoluteTolerance
    ok, plane = panel.TryGetPlane(tol)
    normal = plane.ZAxis if ok else rs.ViewCPlane().ZAxis
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer(), -1)
    n = next_number(LAYER)
    made = 0
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near the edge for a pocket (W=0 — whole edge; Enter — done)")
        gp.AcceptNothing(True)
        got = ask(gp)
        if got is None:
            break
        click, (w, h, trim, sa, notch, rigid, hem, angle) = got
        res = pick_edge(panel, click, angle, tol)
        if not isinstance(res, tuple):
            print(u"Skipped: " + res)
            continue
        edge = res[3]
        if 0 < edge.GetLength() <= w:
            print(u"W %g ≥ edge length %.1f — pocket over the whole edge" % (w, edge.GetLength()))
        toward = inward(panel, edge, normal)
        res = pocket(edge, toward, w, h, trim, sa, notch, normal, tol, rigid, hem)
        if not isinstance(res, tuple):
            print(u"Skipped: " + res)
            continue
        res = res + (toward,)
        label = add_pocket(doc, res, h, trim, sa, notch, n, attrs, normal, tol, rigid, hem,
                           rs.ViewCPlane().YAxis * UP if sc.sticky[STICKY + "_layout"] else None)
        print(label)
        n += 1
        made += 1
    print(u"Pockets: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
