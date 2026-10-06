# -*- coding: utf-8 -*-
"""Підсилення-«O» під кінець кармана на всю ширину панелі (rinforzo a O).
Як ReinfD, але без прямокутника: карман доходить до краю панелі, тож підсилення — коло
з центром у верхньому куті кармана, обрізане панеллю.
Вибираєш межу (панель або лінії кута; Enter — без обрізки, повне коло). Далі в циклі:
перша точка — верхній кут кармана (центр кола), друга — клік на лінії (напр. другий бік кармана):
R = відстань до кліку + Plus (опція, типово 5 см, запам'ятовується). Коло видно наживо. Enter — кінець.
З панеллю (замкнена крива) лишається тільки частина кола всередині панелі, що торкається центру;
з відкритими лініями — частина між ними з боку другого кліку.
Опція SA — припуск на шов (типово 1 см, лише з панеллю): сторони по краю панелі виходять назовні на SA
(дуга лишається на R — на ній шва немає); лінія шва — ребра панелі всередині кола, у групі.
SA=0 — без припуску. Plus і SA — у запиті другого кліку.
Деталь лежить на місці,
шар Parts::Reinforcements, підпис "RO<n>  R=…" у групі; нумерація RO продовжується між запусками.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import AreaMassProperties, ArcCurve, Circle, Curve, CurveOffsetCornerStyle, Plane, PointContainment

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("ReinfCircle", None)  # Rhino тримає модулі з першого запуску за сесію
from ReinfCircle import LAYER, layer, next_number, piece, text_style  # шар, нумерація, обрізка, стиль PAT

STICKY = "ReinfO"
PREFIX = "RO"  # Reinforcement O


def o_shape(curves, center, edge, plus, normal, tol):
    """Коло (центр center, R = відстань до edge + plus), обрізане curves. (крива або None, R)."""
    plane = Plane(center, normal)
    d = plane.ClosestPoint(edge).DistanceTo(center)
    r = d + plus
    if d <= tol or r <= tol:
        return None, r
    circle = ArcCurve(Circle(plane, r))
    closed = [c for c in curves if c.IsClosed]
    if closed:  # панель: тільки всередині неї, шматок з центром (або найближчий до нього)
        best = None
        for c in closed:
            for p in Curve.CreateBooleanIntersection(circle, c, tol) or []:
                inside = p.Contains(center, plane, tol) != PointContainment.Outside
                gap = 0.0 if inside else center.DistanceTo(p.PointAt(p.ClosestPoint(center)[1]))
                if best is None or gap < best[0]:
                    best = (gap, p)
        return (best[1] if best else None), r
    if curves:
        return piece(curves, center, edge, r, normal, tol), r
    return circle, r


def outward(crv, d, normal, tol):
    """Офсет замкненої crv на d назовні (з двох боків той, що більший). None — не вдався."""
    plane = Plane(crv.PointAtStart, normal)
    best = None
    for s in (d, -d):
        offs = crv.Offset(plane, s, tol, CurveOffsetCornerStyle.Sharp)
        offs = Curve.JoinCurves(offs, tol) if offs else None
        if offs and offs[0].IsClosed:
            a = AreaMassProperties.Compute(offs[0]).Area
            if best is None or a > best[0]:
                best = (a, offs[0])
    return best[1] if best else None


def grow(curves, sa, normal, tol):
    """Замкнені панелі, розширені назовні на sa (для лінії різу). [] — немає панелі або sa = 0."""
    if sa <= 0:
        return []
    return [g for g in (outward(c, sa, normal, tol) for c in curves if c.IsClosed) if g]


def seam_lines(crv, center, r, tol):
    """Ребра панелі на контурі crv — усе, крім дуги кола (центр center, радіус r)."""
    keep = [s for s in crv.DuplicateSegments() or [crv]
            if any(abs(center.DistanceTo(s.PointAtNormalizedLength(t)) - r) > tol for t in (0.25, 0.5, 0.75))]
    return list(Curve.JoinCurves(keep, tol)) if keep else []


def reinf(curves, center, edge, plus, sa, normal, tol, grown=None):
    """(різ, [лінії шва], R): різ = коло, обрізане панеллю + sa; шов — ребра панелі в колі. різ None — не вийшло."""
    crv, r = o_shape(curves, center, edge, plus, normal, tol)
    if grown is None:
        grown = grow(curves, sa, normal, tol)
    if crv is None or not grown:
        return crv, [], r
    cut = o_shape(grown, center, edge, plus, normal, tol)[0]
    return cut, (seam_lines(crv, center, r, tol) if cut else []), r


def get_edge(curves, center, normal, tol):
    """Друга точка з живим O і опціями Plus, SA. (точка, plus, sa) або None."""
    unit = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    plus = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 50.0 * unit), 0.0, 1e6)
    sa = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_sa", 10.0 * unit), 0.0, 1e6)

    grown = {}  # SA → розширені панелі: офсет панелі не рахуємо на кожен рух миші

    def draw(sender, e):
        s = sa.CurrentValue
        if s not in grown:
            grown[s] = grow(curves, s, normal, tol)
        cut, seams, _ = reinf(curves, center, e.CurrentPoint, plus.CurrentValue, s, normal, tol, grown[s])
        color = sc.doc.Layers.CurrentLayer.Color
        if cut:
            e.Display.DrawCurve(cut, color, 2)
        for c in seams:
            e.Display.DrawCurve(c, color, 1)
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Клік на лінії: R = відстань до неї + Plus")
    gp.SetBasePoint(center, True)
    gp.DrawLineFromPoint(center, True)
    gp.AddOptionDouble("Plus", plus)
    gp.AddOptionDouble("SA", sa)
    gp.DynamicDraw += draw
    try:
        while True:
            res = gp.Get()
            sc.sticky[STICKY] = plus.CurrentValue
            sc.sticky[STICKY + "_sa"] = sa.CurrentValue
            if res != Rhino.Input.GetResult.Option:
                return (gp.Point(), plus.CurrentValue, sa.CurrentValue) if res == Rhino.Input.GetResult.Point else None
    finally:
        gp.DynamicDraw -= draw


def main():
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    ids = rs.GetObjects(u"Виберіть межу: панель або лінії кута (Enter — без обрізки)", rs.filter.curve, preselect=True)
    curves = [rs.coercecurve(i) for i in ids or []]
    normal = rs.ViewCPlane().ZAxis
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer(), -1)
    n = next_number(LAYER, PREFIX)
    made = 0
    while True:
        center = rs.GetPoint(u"Верхній кут кармана — центр O (Enter — кінець)")
        if center is None:
            break
        got = get_edge(curves, center, normal, tol)
        if got is None:
            break
        crv, seams, r = reinf(curves, center, got[0], got[1], got[2], normal, tol)
        if crv is None:
            print(u"Не вдалось вирізати коло (точки збігаються? криві не в площині CPlane?)")
            continue
        if got[2] > 0 and not seams:  # ponytail: SA лише з замкненою панеллю; з лініями кута — без припуску
            print(u"SA пропущено: потрібна замкнена панель")
        label = u"%s%d  R=%g" % (PREFIX, n, round(r, 1))
        amp = AreaMassProperties.Compute(crv)
        tp = Plane(rs.ViewCPlane())
        tp.Origin = amp.Centroid if amp else center
        te = Rhino.Geometry.TextEntity.Create(label, tp, text_style(doc, r), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        new = [doc.Objects.AddCurve(c, attrs) for c in [crv] + seams] + [doc.Objects.AddText(te, attrs)]
        rs.AddObjectsToGroup(new, rs.AddGroup())
        doc.Views.Redraw()
        print(label)
        n += 1
        made += 1
    print(u"Підсилень O: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
