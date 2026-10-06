# -*- coding: utf-8 -*-
"""Підсилення-«D» під кінець кармана для труби (rinforzo a D).
Перша точка — верхній кут кармана (центр півкола D), друга — нижній кут (звідки D починається).
Деталь: прямокутник шириною W від другої точки до першої + кінець, що виходить за першу точку на R
(W = 2R — півколо; інакше півеліпс W/2 × R, плавно, не ширший за W). Поки вибираєш другу точку — D видно наживо.
Цикл: кілька D підряд (обидва кінці кожного кармана), Enter — кінець. Деталь лежить на місці,
шар Parts::Reinforcements, підпис "RD<n>  W=…  R=…" у групі; нумерація RD продовжується між запусками.
Опції W і R — у запиті першої точки, запам'ятовуються.
На панелі — розмітка D без низу (низ лежить на краю), повна деталь — на 10000 вгору (ReinfCircle.add_part).
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Arc, ArcCurve, Curve, Plane, Polyline, PolylineCurve, Transform, Vector3d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("ReinfCircle", None)  # Rhino тримає модулі з першого запуску за сесію
from ReinfCircle import LAYER, add_part, layer, next_number, off_panel, text_style  # шар, нумерація, стиль PAT

STICKY = "ReinfD"
PREFIX = "RD"  # Reinforcement D


def d_shape(top, bottom, w, r, normal, tol):
    """Замкнена крива D: прямокутник ширини w від bottom до top + кінець на r за top
    (півколо при w = 2r, інакше півеліпс w/2 × r). None — точки збігаються."""
    u = top - bottom
    if u.Length <= tol:
        return None
    u.Unitize()
    v = Vector3d.CrossProduct(normal, u)
    v.Unitize()
    hw = w / 2.0
    rect = PolylineCurve(Polyline([top + v * hw, bottom + v * hw, bottom - v * hw, top - v * hw]))
    cap = ArcCurve(Arc(top - v * hw, top + u * hw, top + v * hw)).ToNurbsCurve()
    cap.Transform(Transform.Scale(Plane(top, u, v), r / hw, 1, 1))  # півколо → півеліпс уздовж осі
    joined = Curve.JoinCurves([rect, cap], tol)
    return joined[0] if len(joined) == 1 and joined[0].IsClosed else None


def get_top():
    """Перша точка з опціями W і R. (точка, w, r) або None."""
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Верхній кут кармана — центр D (Enter — кінець)")
    gp.AcceptNothing(True)
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_w", 100.0), 0.001, 1e6)
    r = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 50.0), 0.001, 1e6)
    gp.AddOptionDouble("W", w)
    gp.AddOptionDouble("R", r)
    while True:
        res = gp.Get()
        sc.sticky[STICKY + "_w"] = w.CurrentValue
        sc.sticky[STICKY] = r.CurrentValue
        if res == Rhino.Input.GetResult.Option:
            continue
        return (gp.Point(), w.CurrentValue, r.CurrentValue) if res == Rhino.Input.GetResult.Point else None


def get_bottom(top, w, r, normal, tol):
    """Друга точка з живим D. Точка або None."""
    def draw(sender, e):
        c = d_shape(top, e.CurrentPoint, w, r, normal, tol)
        if c:
            e.Display.DrawCurve(c, sc.doc.Layers.CurrentLayer.Color, 2)
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Нижній кут кармана — звідки починається D")
    gp.SetBasePoint(top, True)
    gp.DrawLineFromPoint(top, True)
    gp.DynamicDraw += draw
    try:
        return gp.Point() if gp.Get() == Rhino.Input.GetResult.Point else None
    finally:
        gp.DynamicDraw -= draw


def main():
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    normal = rs.ViewCPlane().ZAxis
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer(), -1)
    n = next_number(LAYER, PREFIX)
    made = 0
    while True:
        got = get_top()
        if got is None:
            break
        top, w, r = got
        bottom = get_bottom(top, w, r, normal, tol)
        if bottom is None:
            break
        crv = d_shape(top, bottom, w, r, normal, tol)
        if crv is None:
            print(u"Точки збігаються — пропущено")
            continue
        label = u"%s%d  W=%g  R=%g" % (PREFIX, n, w, r)
        tp = Plane(rs.ViewCPlane())
        tp.Origin = (top + bottom) / 2.0
        te = Rhino.Geometry.TextEntity.Create(label, tp, text_style(doc, min(r, w / 2.0)), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        base = min(crv.DuplicateSegments(), key=lambda g: g.PointAtNormalizedLength(0.5).DistanceTo(bottom))  # низ D
        add_part(doc, [crv], te, off_panel(crv, [base], tol), attrs)
        doc.Views.Redraw()
        print(label)
        n += 1
        made += 1
    print(u"Підсилень D: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
