# -*- coding: utf-8 -*-
"""Підсилення-«D» під кінець кармана для труби (rinforzo a D).
Перша точка — верхній кут кармана (центр півкола D), друга — нижній кут (звідки D починається).
Деталь: прямокутник шириною 2R від другої точки до першої + півколо радіуса R за першою точкою
(R=50 → ширина 100, за кут кармана виходить на 50). Поки вибираєш другу точку — D видно наживо.
Цикл: кілька D підряд (обидва кінці кожного кармана), Enter — кінець. Деталь лежить на місці,
шар Parts::Reinforcements, підпис "RD<n>  R=…" у групі; нумерація RD продовжується між запусками.
Опція R — у запиті першої точки, запам'ятовується.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Arc, ArcCurve, Curve, Plane, Polyline, PolylineCurve, Vector3d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("ReinfCircle", None)  # Rhino тримає модулі з першого запуску за сесію
from ReinfCircle import LAYER, layer, next_number, text_style  # той самий шар, нумерація, стиль PAT

STICKY = "ReinfD"
PREFIX = "RD"  # Reinforcement D


def d_shape(top, bottom, r, normal, tol):
    """Замкнена крива D: прямокутник 2R від bottom до top + півколо радіуса R за top. None — точки збігаються."""
    u = top - bottom
    if u.Length <= tol:
        return None
    u.Unitize()
    v = Vector3d.CrossProduct(normal, u)
    v.Unitize()
    rect = PolylineCurve(Polyline([top + v * r, bottom + v * r, bottom - v * r, top - v * r]))
    cap = ArcCurve(Arc(top - v * r, top + u * r, top + v * r))
    joined = Curve.JoinCurves([rect, cap], tol)
    return joined[0] if len(joined) == 1 and joined[0].IsClosed else None


def get_top():
    """Перша точка з опцією R. (точка, r) або None."""
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Верхній кут кармана — центр D (Enter — кінець)")
    gp.AcceptNothing(True)
    r = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 50.0), 0.001, 1e6)
    gp.AddOptionDouble("R", r)
    while True:
        res = gp.Get()
        sc.sticky[STICKY] = r.CurrentValue
        if res == Rhino.Input.GetResult.Option:
            continue
        return (gp.Point(), r.CurrentValue) if res == Rhino.Input.GetResult.Point else None


def get_bottom(top, r, normal, tol):
    """Друга точка з живим D. Точка або None."""
    def draw(sender, e):
        c = d_shape(top, e.CurrentPoint, r, normal, tol)
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
        top, r = got
        bottom = get_bottom(top, r, normal, tol)
        if bottom is None:
            break
        crv = d_shape(top, bottom, r, normal, tol)
        if crv is None:
            print(u"Точки збігаються — пропущено")
            continue
        label = u"%s%d  R=%g" % (PREFIX, n, r)
        tp = Plane(rs.ViewCPlane())
        tp.Origin = (top + bottom) / 2.0
        te = Rhino.Geometry.TextEntity.Create(label, tp, text_style(doc, r), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        rs.AddObjectsToGroup([doc.Objects.AddCurve(crv, attrs), doc.Objects.AddText(te, attrs)], rs.AddGroup())
        doc.Views.Redraw()
        print(label)
        n += 1
        made += 1
    print(u"Підсилень D: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
