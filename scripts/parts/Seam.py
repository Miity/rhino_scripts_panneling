# -*- coding: utf-8 -*-
"""Припуск на шов (seam allowance / margine di cucitura) — окрема деталь, шар Parts::Seam.
На вході або лише замкнені криві (панелі), або лише відкриті; змішано — помилка.
- Панелі: як CopriZip — клікаєш біля ребра (кілька підряд, Enter — кінець), панель — найближча до кліку.
  Ребро — від кута до кута (кут — злам більший за Angle); деталь — ребро + офсет на W назовні,
  кінці по продовженню сусідніх ребер (геометрія — CopriZip.flap).
- Відкриті криві: кожна — ребро; клікаєш, з якого боку припуск; деталь — ребро + офсет W, торці
  прямі (кути гострі).
Деталь + підпис "SA <W>" у групі. Вхідні криві не змінюються.
Опція Points=Yes: ще й точки шва (логіка markup/sewing_points.py: центр ± k·Step) на копії ребра
в Parts::Seam — копія + точки в тій самій групі, що деталь.
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
    """Відкрите ребро → (деталь, ребро, офсет): ребро + офсет на w з боку side, торці прямі. None — не вдалося."""
    offs = crv.Offset(side, normal, w, tol, CurveOffsetCornerStyle.Sharp)
    offs = Curve.JoinCurves(offs, tol) if offs else None
    if not offs:
        return None
    o = max(offs, key=lambda c: c.GetLength())
    if o.PointAtStart.DistanceTo(crv.PointAtStart) > o.PointAtEnd.DistanceTo(crv.PointAtStart):
        o.Reverse()
    joined = Curve.JoinCurves([crv.DuplicateCurve(), o, LineCurve(crv.PointAtStart, o.PointAtStart),
                               LineCurve(crv.PointAtEnd, o.PointAtEnd)], tol)
    return (joined[0], crv, o) if len(joined) == 1 and joined[0].IsClosed else None


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


def ask(gp, with_angle=True):
    """Клік з опціями W / Angle (лише для панелей) / Points / Step. Точка або None (Enter / Esc)."""
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 10.0), 0.001, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    pts = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_points", False), "No", "Yes")
    step = Rhino.Input.Custom.OptionDouble(sc.sticky.get("sew_step", 20.0), 0.001, 1e6)  # спільний із sewing_points
    gp.AddOptionDouble("W", w)
    if with_angle:
        gp.AddOptionDouble("Angle", a)
    gp.AddOptionToggle("Points", pts)
    gp.AddOptionDouble("Step", step)
    while True:
        r = gp.Get()
        sc.sticky[STICKY] = w.CurrentValue
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        sc.sticky[STICKY + "_points"] = pts.CurrentValue
        sc.sticky["sew_step"] = step.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


def add_sewing_points(doc, crv, step, attrs):
    """Копія ребра (лінія шва) + точки шва на ній (як sewing_points), обидва з attrs (шар Parts::Seam)."""
    ids = [doc.Objects.AddCurve(crv, attrs)]
    for s in sewing_lengths(crv.GetLength(), step):
        ok, t = crv.LengthParameter(s)
        if ok:
            ids.append(doc.Objects.AddPoint(crv.PointAt(t), attrs))
    return ids


def plane_normal(crv, tol):
    ok, pl = crv.TryGetPlane(tol)
    return pl.ZAxis if ok else rs.ViewCPlane().ZAxis


def add_part(doc, res, normal, attrs):
    """Деталь + підпис SA W (+ копія ребра з точками шва, якщо Points=Yes) — одна група. Повертає к-сть точок."""
    crv, edge, off = res[:3]
    w = sc.sticky[STICKY]
    te = Rhino.Geometry.TextEntity.Create(u"SA %g" % w, label_frame(edge, off, normal),
                                          text_style(doc, w), False, 0, 0)
    te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
    te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
    pts = add_sewing_points(doc, edge, sc.sticky["sew_step"], attrs) if sc.sticky[STICKY + "_points"] else []
    rs.AddObjectsToGroup([doc.Objects.AddCurve(crv, attrs), doc.Objects.AddText(te, attrs)] + pts, rs.AddGroup())
    doc.Views.Redraw()
    return max(len(pts) - 1, 0)  # без копії ребра


def main():
    from CopriZip import flap  # тут, а не вгорі: CopriZip сам імпортує label_frame / text_style з Seam
    doc = sc.doc
    ids = rs.GetObjects(u"Виберіть панелі (замкнені криві) або ребра (відкриті криві)", rs.filter.curve,
                        preselect=True)
    if not ids:
        return
    curves = [rs.coercecurve(i) for i in ids]
    closed = set(c.IsClosed for c in curves)
    if len(closed) > 1:
        rs.MessageBox(u"Seam: виберіть АБО лише замкнені криві (панелі), АБО лише відкриті (ребра) — не змішуючи.",
                      16, u"Seam")
        return
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Seam", parent="Parts")
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(LAYER, -1)
    tol = doc.ModelAbsoluteTolerance
    made = n_pts = 0
    if closed == {True}:
        while True:
            gp = Rhino.Input.Custom.GetPoint()
            gp.SetCommandPrompt(u"Клікни біля ребра панелі під припуск на шов (Enter — кінець)")
            gp.AcceptNothing(True)
            click = ask(gp)
            if click is None:
                break
            panel = min(curves, key=lambda c: c.PointAt(c.ClosestPoint(click)[1]).DistanceTo(click))
            normal = plane_normal(panel, tol)
            res = flap(panel, click, sc.sticky[STICKY], sc.sticky[STICKY + "_angle"], normal, tol)
            if not isinstance(res, tuple):
                print(u"Пропущено: %s" % res)
                continue
            n_pts += add_part(doc, res, normal, attrs)
            made += 1
            if res[3]:
                print(u"Увага: %d кін. сусід гостріше 30° — кінець перпендикулярний" % res[3])
    else:
        for i, (oid, crv) in enumerate(zip(ids, curves), 1):
            rs.UnselectAllObjects()
            rs.SelectObject(oid)
            gp = Rhino.Input.Custom.GetPoint()
            gp.SetCommandPrompt(u"Крива %d/%d: клікни, з якого боку припуск (Esc — стоп)" % (i, len(ids)))
            side = ask(gp, with_angle=False)
            if side is None:
                break
            normal = plane_normal(crv, tol)
            res = strip(crv, side, sc.sticky[STICKY], normal, tol)
            if not res:
                print(u"Крива %d: офсет не вдався (неплоска чи самоперетин?) — пропущено" % i)
                continue
            n_pts += add_part(doc, res, normal, attrs)
            made += 1
        rs.UnselectAllObjects()
    print(u"Припуск на шов: %d деталей → %s" % (made, LAYER))
    if n_pts:
        print(u"Точок шва: %d на копіях ребер у %s" % (n_pts, LAYER))


if __name__ == "__main__":
    main()
