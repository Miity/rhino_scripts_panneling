# -*- coding: utf-8 -*-
"""Copri zip / copri canalina: клапан, що накриває блискавку на ребрі панелі.
Вибираєш панель (замкнена крива: полілінія, лінії, дуги — будь-які сегменти) і клікаєш біля ребра
(кілька підряд, Enter — кінець). Ребро — від кута до кута (кут — злам дотичної більший за Angle;
дрібні зломи кривого краю не рахуються). Деталь — замкнена крива: копія ребра + офсет на W
назовні від панелі, кінці по продовженню сусідніх ребер. Якщо сусід відходить гостріше ніж на 30°
від ребра (продовження пішло б дуже далеко) — кінець перпендикулярний, з попередженням.
Деталь + підпис "CZ W" у групі, шар Parts::CopriZip. Панель не змінюється: перед різом
PreparePanelCut склеїть її з деталлю (для нього ребро має бути полілінією / лініями).
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

    ends, square = [], 0
    for corner, d, t, own in ((edge.PointAtStart, segs[(s - 1) % n].TangentAtEnd * side, t0, off.PointAtStart),
                              (edge.PointAtEnd, -segs[e].TangentAtStart * side, edge.TangentAtEnd, off.PointAtEnd)):
        k = d * outward(t)  # sin кута між продовженням сусіда і ребром (з боку деталі)
        p = None
        if k >= MIN_SIN:
            x = Intersection.CurveCurve(LineCurve(corner, corner + d * (w / k + big)), ext, tol, tol)
            p = min((ev.PointA for ev in x), key=corner.DistanceTo) if x and x.Count else None
        if p is None:
            p, square = own, square + 1
        ends.append(p)
    ta, tb = ext.ClosestPoint(ends[0])[1], ext.ClosestPoint(ends[1])[1]
    if ta >= tb - tol:
        return u"ребро закоротке для клапана W=%g (продовження сусідів перетнулись)" % w
    top = ext.Trim(ta, tb)
    top.Reverse()
    joined = Curve.JoinCurves([edge, LineCurve(edge.PointAtEnd, top.PointAtStart), top,
                               LineCurve(top.PointAtEnd, edge.PointAtStart)], tol)
    if len(joined) != 1 or not joined[0].IsClosed:
        return u"деталь не замкнулась"
    out = joined[0]
    ok, pl = out.TryGetPolyline()  # для PreparePanelCut — чиста полілінія, якщо все прямо
    if ok:
        pl.DeleteShortSegments(tol)
        out = PolylineCurve(pl)
    return out, edge, off, square


def ask(gp):
    """Клік біля ребра з опціями W / Angle. Точка або None (Enter / Esc)."""
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 25.0), 0.001, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    gp.AddOptionDouble("W", w)
    gp.AddOptionDouble("Angle", a)
    while True:
        r = gp.Get()
        sc.sticky[STICKY] = w.CurrentValue
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


def main():
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
        rs.AddObjectsToGroup([doc.Objects.AddCurve(crv, attrs), doc.Objects.AddText(te, attrs)], rs.AddGroup())
        made += 1
        if square:
            print(u"Увага: %d кін. сусід гостріше 30° — кінець перпендикулярний" % square)
        doc.Views.Redraw()
    print(u"Copri zip: %d деталей → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
