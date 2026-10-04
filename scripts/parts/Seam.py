# -*- coding: utf-8 -*-
"""Припуск на шов (seam allowance / margine di cucitura) під виділені ребра.
Кожна вибрана крива — окреме ребро: клікаєш, з якого боку припуск, і отримуєш замкнену смугу
між ребром і його офсетом на ширину W (кути гострі). Смуга + підпис "SA <W>" ідуть у шар
Parts::Seam і групуються. Оригінальна крива (лінія шва) не змінюється.
Замкнена крива дає кільце: копія контуру + офсет у групі (одною кривою кільце не замкнути).
Опція Points=Yes: ще й точки шва (логіка markup/sewing_points.py: центр ± k·Step) на копії ребра
в Parts::Seam — копія + точки в тій самій групі, що смуга. Оригінал і його шар не чіпаються.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, CurveOffsetCornerStyle, LineCurve, Plane, Vector3d

try:  # стилі тексту PAT для лекал 1:1 (scripts/markup/PatternTextStyles.py)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
    import PatternTextStyles
except Exception:
    PatternTextStyles = None
from sewing_points import sewing_lengths  # той самий markup/ у sys.path

STICKY = "Seam"
LAYER = "Parts::Seam"


def strip(crv, side, w, normal, tol):
    """(криві смуги, офсет): [замкнена крива] для відкритого ребра, [копія, офсет] для замкненого; None — офсет не вдався."""
    offs = crv.Offset(side, normal, w, tol, CurveOffsetCornerStyle.Sharp)
    offs = Curve.JoinCurves(offs, tol) if offs else None
    if not offs:
        return None
    o = max(offs, key=lambda c: c.GetLength())
    if crv.IsClosed:
        return [crv.DuplicateCurve(), o], o
    if o.PointAtStart.DistanceTo(crv.PointAtStart) > o.PointAtEnd.DistanceTo(crv.PointAtStart):
        o.Reverse()
    parts = [crv.DuplicateCurve(), o,
             LineCurve(crv.PointAtStart, o.PointAtStart), LineCurve(crv.PointAtEnd, o.PointAtEnd)]
    joined = Curve.JoinCurves(parts, tol)
    return ([joined[0]], o) if len(joined) == 1 and joined[0].IsClosed else None


def label_frame(crv, offset, normal):
    """Точка посередині смуги і напрямок уздовж ребра (текст читається зліва направо)."""
    ok, t = crv.LengthParameter(crv.GetLength() / 2.0)
    t = t if ok else crv.Domain.Mid
    m = crv.PointAt(t)
    q = offset.PointAt(offset.ClosestPoint(m)[1])
    u = crv.TangentAt(t)
    if u.X < -1e-9 or (abs(u.X) < 1e-9 and u.Y < 0):
        u = -u
    return Plane((m + q) / 2.0, u, Vector3d.CrossProduct(normal, u))


def text_style(doc, w):
    """Стиль PAT, що влазить у смугу ширини w (≈ 0.6·w)."""
    if PatternTextStyles is None:
        return doc.DimStyles.Current
    styles = PatternTextStyles.ensure_styles(doc)
    fit = [h for h in PatternTextStyles.SERIES if h <= w * 0.6]
    return styles[fit[-1] if fit else PatternTextStyles.SERIES[0]]


def ask_settings():
    """Ширина + опції Points (точки шва) і Step (крок, спільний із sewing_points). None — скасовано."""
    gn = Rhino.Input.Custom.GetNumber()
    gn.SetCommandPrompt(u"Ширина припуску на шов")
    gn.SetDefaultNumber(sc.sticky.get(STICKY, 10.0))
    gn.SetLowerLimit(0.0, True)
    pts = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_points", False), "No", "Yes")
    step = Rhino.Input.Custom.OptionDouble(sc.sticky.get("sew_step", 20.0), 0.001, 1e6)
    gn.AddOptionToggle("Points", pts)
    gn.AddOptionDouble("Step", step)
    while True:
        r = gn.Get()
        if r == Rhino.Input.GetResult.Option:
            continue
        if r != Rhino.Input.GetResult.Number:
            return None
        w = gn.Number()
        sc.sticky[STICKY] = w
        sc.sticky[STICKY + "_points"] = pts.CurrentValue
        sc.sticky["sew_step"] = step.CurrentValue
        return w, pts.CurrentValue, step.CurrentValue


def add_sewing_points(doc, crv, step, attrs):
    """Копія ребра (лінія шва) + точки шва на ній (як sewing_points), обидва з attrs (шар Parts::Seam)."""
    ids = [doc.Objects.AddCurve(crv, attrs)]
    for s in sewing_lengths(crv.GetLength(), step):
        ok, t = crv.LengthParameter(s)
        if ok:
            ids.append(doc.Objects.AddPoint(crv.PointAt(t), attrs))
    return ids


def main():
    doc = sc.doc
    ids = rs.GetObjects(u"Виберіть ребра для припуску на шов", rs.filter.curve, preselect=True)
    if not ids:
        return
    settings = ask_settings()
    if settings is None:
        return
    w, with_points, step = settings

    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Seam", parent="Parts")
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(LAYER, -1)
    tol = doc.ModelAbsoluteTolerance
    style = text_style(doc, w)
    cplane_z = rs.ViewCPlane().ZAxis
    made = n_pts = 0
    for i, oid in enumerate(ids, 1):
        crv = rs.coercecurve(oid)
        rs.UnselectAllObjects()
        rs.SelectObject(oid)
        side = rs.GetPoint(u"Ребро %d/%d: клікни, з якого боку припуск (Esc — стоп)" % (i, len(ids)))
        if side is None:
            break
        ok, pl = crv.TryGetPlane(tol)
        normal = pl.ZAxis if ok else cplane_z
        res = strip(crv, side, w, normal, tol)
        if not res:
            print(u"Ребро %d: офсет не вдався (крива неплоска чи самоперетин?) — пропущено" % i)
            continue
        new = [doc.Objects.AddCurve(c, attrs) for c in res[0]]
        te = Rhino.Geometry.TextEntity.Create(u"SA %g" % w, label_frame(crv, res[1], normal), style, False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        new.append(doc.Objects.AddText(te, attrs))
        if with_points:
            pts = add_sewing_points(doc, crv, step, attrs)
            new += pts
            n_pts += len(pts) - 1
        rs.AddObjectsToGroup(new, rs.AddGroup())
        made += 1
    rs.UnselectAllObjects()
    doc.Views.Redraw()
    print(u"Припуск %g: смуг %d з %d ребер → %s" % (w, made, len(ids), LAYER))
    if with_points:
        print(u"Точок шва: %d (крок %g) на копіях ребер у %s" % (n_pts, step, LAYER))


if __name__ == "__main__":
    main()
