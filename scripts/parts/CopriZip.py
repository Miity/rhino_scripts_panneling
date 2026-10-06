# -*- coding: utf-8 -*-
"""Copri zip / copri canalina: клапан, що накриває блискавку на ребрі панелі.
Вибираєш панель (замкнена крива: полілінія, лінії, дуги — будь-які сегменти) і клікаєш біля ребра
(кілька підряд, Enter — кінець). Ребро — від кута до кута (кут — злам дотичної більший за Angle;
дрібні зломи кривого краю не рахуються). Деталь — замкнена крива: копія ребра + офсет на W
назовні від панелі, кінці по продовженню сусідніх ребер. Якщо сусід відходить гостріше ніж на 30°
від ребра (продовження пішло б дуже далеко) — кінець перпендикулярний, з попередженням.
Деталь + підпис "CZ W" у групі, шар Parts::CopriZip. Панель не змінюється: перед різом
PreparePanelCut склеїть її з деталлю (для нього ребро має бути полілінією / лініями).
Опція Layout (галочка, типово No): Yes — як у Reinf (ReinfCircle.add_part): на місці лише розмітка (лінії клапана,
що не лежать на ребрі панелі, + підпис), повна деталь — на 10000 вгору по Y CPlane, для Layout.
"""
import math
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import (Curve, CurveEnd, CurveExtensionStyle, CurveOffsetCornerStyle, CurveOrientation,
                            LineCurve, PolylineCurve, Vector3d)
from Rhino.Geometry.Intersect import Intersection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Seam import label_frame, text_style  # підпис посередині смуги, стиль PAT під ширину

STICKY = "CopriZip"
LAYER = "Parts::CopriZip"
MIN_SIN = 0.5  # sin 30°: гостріше — перпендикулярний кінець
GAP_MM = 1.0  # розрив між кінцями «майже замкненої» панелі (DXF), який замикаємо самі


def pick_edge(panel, click, angle, tol):
    """(сегменти, індекс першого сегмента ребра, індекс сегмента після ребра, ребро) або рядок-помилка.
    Ребро — від кута до кута біля click; кут — злам дотичної більший за angle."""
    if not panel.IsClosed:
        gap = GAP_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
        panel = panel.DuplicateCurve()
        if not panel.MakeClosed(gap):
            return u"панель не замкнена (розрив між кінцями більший за %g мм)" % GAP_MM
    segs = [c for c in panel.DuplicateSegments() if c.GetLength() > tol] or [panel.DuplicateCurve()]
    n = len(segs)
    corners = set(i for i in range(n) if Vector3d.VectorAngle(segs[i - 1].TangentAtEnd, segs[i].TangentAtStart)
                  > math.radians(angle))  # кут i — початок сегмента i
    if len(corners) < 2:
        return u"на панелі менше двох кутів більших за %g°" % angle
    i = min(range(n), key=lambda k: segs[k].PointAt(segs[k].ClosestPoint(click)[1]).DistanceTo(click))
    s, e = i, (i + 1) % n
    while s not in corners:
        s = (s - 1) % n
    while e not in corners:
        e = (e + 1) % n
    edge = Curve.JoinCurves([segs[(s + k) % n] for k in range((e - s) % n or n)], tol)[0]
    return segs, s, e, edge


def along_panel(loop, corner, ext, back, tol):
    """(точка, шматок панелі) від кута по панелі до першого перетину з ext: back — назад за обходом
    (сусід перед ребром, шматок іде до кута), інакше вперед (шматок від кута). (None, None) — перетину немає."""
    c = loop.DuplicateCurve()
    c.ChangeClosedCurveSeam(c.ClosestPoint(corner)[1])  # кут — на шві: шматок не перетинає шов
    x = [ev.ParameterA for ev in Intersection.CurveCurve(c, ext, tol, tol) or []
         if ev.PointA.DistanceTo(corner) > tol]
    if not x:
        return None, None
    t = max(x) if back else min(x)
    piece = c.Trim(t, c.Domain.T1) if back else c.Trim(c.Domain.T0, t)
    return (c.PointAt(t), piece) if piece else (None, None)


def flap(panel, click, w, angle, normal, tol, inward=False):
    """(крива деталі, ребро, офсет, к-сть перпендикулярних кінців) або рядок-помилка.
    inward — деталь усередину панелі (ReinfBord): кінці по самих сусідніх ребрах, а не по їх продовженню."""
    res = pick_edge(panel, click, angle, tol)
    if not isinstance(res, tuple):
        return res
    segs, s, e, edge = res
    n = len(segs)

    cw = panel.ClosedCurveOrientation(normal) == CurveOrientation.Clockwise
    side = -1 if inward else 1
    def outward(t):  # у бік деталі (назовні від панелі, або всередину при inward) для напрямку обходу t
        return (Vector3d.CrossProduct(normal, t) if cw else Vector3d.CrossProduct(t, normal)) * side

    t0, tm = edge.TangentAtStart, edge.Domain.Mid
    offs = edge.Offset(edge.PointAt(tm) + outward(edge.TangentAt(tm)) * w, normal, w, tol, CurveOffsetCornerStyle.Sharp)
    offs = Curve.JoinCurves(offs, tol) if offs else None
    if not offs:
        return u"офсет ребра не вдався"
    off = max(offs, key=lambda c: c.GetLength())
    if off.PointAtStart.DistanceTo(edge.PointAtStart) > off.PointAtEnd.DistanceTo(edge.PointAtStart):
        off.Reverse()
    big = 10 * w + edge.GetLength()
    ext = off.Extend(CurveEnd.Both, big, CurveExtensionStyle.Line)  # офсет, подовжений прямими
    if ext is None:
        return u"не вдалося подовжити офсет"

    loop = Curve.JoinCurves(segs, tol)[0] if inward else None  # замкнена панель: торці по ній
    ends, sides, square = [], [], 0
    for back, corner, d, t, own in ((True, edge.PointAtStart, segs[(s - 1) % n].TangentAtEnd * side, t0, off.PointAtStart),
                                    (False, edge.PointAtEnd, -segs[e].TangentAtStart * side, edge.TangentAtEnd, off.PointAtEnd)):
        k = d * outward(t)  # sin кута між продовженням сусіда і ребром (з боку деталі)
        p = piece = None
        if k >= MIN_SIN and inward:  # по самому сусідньому ребру (воно може гнутись), до лінії офсету
            p, piece = along_panel(loop, corner, ext, back, tol)
        elif k >= MIN_SIN:
            x = Intersection.CurveCurve(LineCurve(corner, corner + d * (w / k + big)), ext, tol, tol)
            p = min((ev.PointA for ev in x), key=corner.DistanceTo) if x and x.Count else None
        if p is None:
            p, piece, square = own, None, square + 1
        ends.append(p)
        sides.append(piece or (LineCurve(p, corner) if back else LineCurve(corner, p)))
    ta, tb = ext.ClosestPoint(ends[0])[1], ext.ClosestPoint(ends[1])[1]
    if ta >= tb - tol:
        return u"ребро закоротке для клапана W=%g (продовження сусідів перетнулись)" % w
    top = ext.Trim(ta, tb)
    top.Reverse()
    joined = Curve.JoinCurves([edge, sides[1], top, sides[0]], tol)
    if len(joined) != 1 or not joined[0].IsClosed:
        return u"деталь не замкнулась"
    out = joined[0]
    ok, pl = out.TryGetPolyline()  # для PreparePanelCut — чиста полілінія, якщо все прямо
    if ok:
        pl.DeleteShortSegments(tol)
        out = PolylineCurve(pl)
    return out, edge, off, square


def ask(gp):
    """Клік біля ребра з опціями W / Angle / Layout. Точка або None (Enter / Esc)."""
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 25.0), 0.001, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    gp.AddOptionDouble("W", w)
    lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", False), "No", "Yes")
    gp.AddOptionDouble("Angle", a)
    gp.AddOptionToggle("Layout", lay)
    while True:
        r = gp.Get()
        sc.sticky[STICKY + "_layout"] = lay.CurrentValue
        sc.sticky[STICKY] = w.CurrentValue
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


HELP = u"""Опції:
  W — ширина клапана: офсет від ребра назовні панелі
  Angle — злам, більший за цей кут, = кут панелі (ребро береться від кута до кута)
  Layout — Yes: на панелі лише розмітка, повна деталь на 10000 вгору; No: повна деталь на місці"""  # друкується на старті — видно під полями опцій


def main():
    print(HELP)
    sys.modules.pop("ReinfCircle", None)  # тут, а не вгорі: Rhino кешує модулі за сесію
    from ReinfCircle import add_part, off_panel  # Layout: розмітка на місці + деталь угорі
    doc = sc.doc
    oid = rs.GetObject(u"Виберіть панель (замкнена крива)", rs.filter.curve, preselect=True)
    if not oid:
        return
    panel = rs.coercecurve(oid)
    tol = doc.ModelAbsoluteTolerance
    ok, plane = panel.TryGetPlane(tol)
    normal = plane.ZAxis if ok else rs.ViewCPlane().ZAxis
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("CopriZip", parent="Parts")
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(LAYER, -1)
    made = 0
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Клікни біля ребра під клапан (Enter — кінець)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        w, angle = sc.sticky[STICKY], sc.sticky[STICKY + "_angle"]
        res = flap(panel, click, w, angle, normal, tol)
        if not isinstance(res, tuple):
            print(u"Пропущено: %s" % res)
            continue
        crv, edge, off, square = res
        te = Rhino.Geometry.TextEntity.Create(u"CZ %g" % w, label_frame(edge, off, normal),
                                              text_style(doc, w), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        add_part(doc, [crv], te, off_panel(crv, [panel], tol), attrs, sc.sticky[STICKY + "_layout"])
        made += 1
        if square:
            print(u"Увага: %d кін. сусід гостріше 30° — кінець перпендикулярний" % square)
        doc.Views.Redraw()
    print(u"Copri zip: %d деталей → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
