# -*- coding: utf-8 -*-
"""Підсилення-«O» під кінець кармана на всю ширину панелі (rinforzo a O).
Як ReinfD, але без прямокутника: карман доходить до краю панелі, тож підсилення — коло
з центром у верхньому куті кармана, обрізане панеллю.
Вибираєш межу (панель або лінії кута; Enter — без обрізки, повне коло). Далі в циклі:
перша точка — верхній кут кармана (центр кола), друга — точка на колі (радіус; можна ввести число),
з того боку, що лишити. Коло видно наживо. Enter — кінець. Деталь лежить на місці,
шар Parts::Reinforcements, підпис "RO<n>  R=…" у групі; нумерація RO продовжується між запусками.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import AreaMassProperties, ArcCurve, Circle, Plane

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("ReinfCircle", None)  # Rhino тримає модулі з першого запуску за сесію
from ReinfCircle import LAYER, layer, next_number, piece, text_style  # шар, нумерація, обрізка, стиль PAT

PREFIX = "RO"  # Reinforcement O


def o_shape(curves, center, edge, normal, tol):
    """Коло (центр center, через edge), обрізане curves з боку edge. None — точки збігаються / не вийшло."""
    r = Plane(center, normal).ClosestPoint(edge).DistanceTo(center)
    if r <= tol:
        return None, r
    if not curves:
        return ArcCurve(Circle(Plane(center, normal), r)), r
    return piece(curves, center, edge, r, normal, tol), r


def get_edge(curves, center, normal, tol):
    """Друга точка з живим O. Точка або None."""
    def draw(sender, e):
        c = o_shape(curves, center, e.CurrentPoint, normal, tol)[0]
        if c:
            e.Display.DrawCurve(c, sc.doc.Layers.CurrentLayer.Color, 2)
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Точка на колі — радіус R, з того боку, що лишити")
    gp.SetBasePoint(center, True)
    gp.DrawLineFromPoint(center, True)
    gp.DynamicDraw += draw
    try:
        return gp.Point() if gp.Get() == Rhino.Input.GetResult.Point else None
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
        edge = get_edge(curves, center, normal, tol)
        if edge is None:
            break
        crv, r = o_shape(curves, center, edge, normal, tol)
        if crv is None:
            print(u"Не вдалось вирізати коло (точки збігаються? криві не в площині CPlane?)")
            continue
        label = u"%s%d  R=%g" % (PREFIX, n, round(r, 1))
        amp = AreaMassProperties.Compute(crv)
        tp = Plane(rs.ViewCPlane())
        tp.Origin = amp.Centroid if amp else center
        te = Rhino.Geometry.TextEntity.Create(label, tp, text_style(doc, r), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        rs.AddObjectsToGroup([doc.Objects.AddCurve(crv, attrs), doc.Objects.AddText(te, attrs)], rs.AddGroup())
        doc.Views.Redraw()
        print(label)
        n += 1
        made += 1
    print(u"Підсилень O: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
