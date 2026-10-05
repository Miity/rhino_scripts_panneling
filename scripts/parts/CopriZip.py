# -*- coding: utf-8 -*-
"""Copri zip / copri canalina: клапан, що накриває блискавку на ребрі панелі.
Вибираєш панель (замкнена полілінія) і клікаєш біля ребра (кілька підряд, Enter — кінець).
Ребро — від кута до кута (кут — злам більший за Angle; дрібні зломи кривого краю не рахуються).
Деталь — замкнена полілінія: копія ребра + офсет на W назовні від панелі, кінці по продовженню
сусідніх ребер. Якщо сусід відходить гостріше ніж на 30° від ребра (продовження пішло б дуже
далеко) — кінець перпендикулярний, з попередженням. Деталь + підпис "CZ W" у групі, шар
Parts::CopriZip. Панель не змінюється: перед різом PreparePanelCut склеїть її з деталлю.
"""
import math
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import (Curve, CurveOffsetCornerStyle, CurveOrientation, LineCurve, Polyline,
                            PolylineCurve, Vector3d)
from Rhino.Geometry.Intersect import Intersection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Seam import label_frame, text_style  # підпис посередині смуги, стиль PAT під ширину

STICKY = "CopriZip"
LAYER = "Parts::CopriZip"
MIN_SIN = 0.5  # sin 30°: гостріше — перпендикулярний кінець


def unit(v):
    v = Vector3d(v)
    v.Unitize()
    return v


def flap(panel, click, w, angle, normal, tol):
    """(полілінія деталі, ребро, офсет, к-сть перпендикулярних кінців) або рядок-помилка."""
    ok, pl = panel.TryGetPolyline()
    if not ok or not panel.IsClosed:
        return u"панель не замкнена полілінія (спершу CrvToPolyline)"
    pts = list(pl)[:-1]
    n = len(pts)
    corners = set(i for i in range(n) if Vector3d.VectorAngle(pts[i] - pts[i - 1], pts[(i + 1) % n] - pts[i])
                  > math.radians(angle))
    if len(corners) < 2:
        return u"на панелі менше двох кутів більших за %g°" % angle
    i = int(pl.ClosestParameter(click)) % n  # сегмент pts[i] → pts[i+1]
    s, e = i, (i + 1) % n
    while s not in corners:
        s = (s - 1) % n
    while e not in corners:
        e = (e + 1) % n
    edge_pts = [pts[(s + k) % n] for k in range((e - s) % n + 1)]
    edge = PolylineCurve(Polyline(edge_pts))

    cw = panel.ClosedCurveOrientation(normal) == CurveOrientation.Clockwise
    def outward(t):  # назовні від панелі для напрямку обходу t
        return Vector3d.CrossProduct(normal, t) if cw else Vector3d.CrossProduct(t, normal)

    t0 = unit(edge_pts[1] - edge_pts[0])
    offs = edge.Offset(edge_pts[0] + t0 * (edge_pts[0].DistanceTo(edge_pts[1]) / 2) + outward(t0) * w,
                       normal, w, tol, CurveOffsetCornerStyle.Sharp)
    offs = Curve.JoinCurves(offs, tol) if offs else None
    ok, opl = offs[0].TryGetPolyline() if offs else (False, None)
    if not ok:
        return u"офсет ребра не вдався"
    opl = list(opl)
    if opl[0].DistanceTo(edge_pts[0]) > opl[-1].DistanceTo(edge_pts[0]):
        opl.reverse()
    off = PolylineCurve(Polyline(opl))
    big = 10 * w + edge.GetLength()  # офсет, подовжений прямими на обох кінцях
    ext = PolylineCurve(Polyline([opl[0] - unit(opl[1] - opl[0]) * big] + opl +
                                 [opl[-1] + unit(opl[-1] - opl[-2]) * big]))

    ends, square = [], 0
    for j, corner, d, t in ((0, edge_pts[0], unit(edge_pts[0] - pts[(s - 1) % n]), t0),
                            (-1, edge_pts[-1], unit(edge_pts[-1] - pts[(e + 1) % n]), unit(edge_pts[-1] - edge_pts[-2]))):
        k = d * outward(t)  # sin кута між сусідом і ребром (з боку деталі)
        p = None
        if k >= MIN_SIN:
            x = Intersection.CurveCurve(LineCurve(corner, corner + d * (w / k + big)), ext, tol, tol)
            p = min((ev.PointA for ev in x), key=corner.DistanceTo) if x and x.Count else None
        if p is None:
            p = opl[j]
            square += 1
        ends.append(ext.ClosestPoint(p)[1])
    if ends[0] >= ends[1] - tol:
        return u"ребро закоротке для клапана W=%g (продовження сусідів перетнулись)" % w
    ok, mid = ext.Trim(ends[0], ends[1]).TryGetPolyline()
    out = Polyline(edge_pts + list(reversed(list(mid))) + [edge_pts[0]])
    out.DeleteShortSegments(tol)
    return PolylineCurve(out), edge, off, square


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
    oid = rs.GetObject(u"Виберіть панель (замкнена полілінія)", rs.filter.curve, preselect=True)
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
