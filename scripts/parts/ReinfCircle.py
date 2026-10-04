# -*- coding: utf-8 -*-
"""Кутове підсилення — коло (rinforzo d'angolo, cerchio).
Вибираєш межу: замкнену панель або лінії, що утворюють кут. Задаєш радіус R.
Клікаєш біля кута з того боку, який лишити. Центр кола — найближча до кліку вершина
(злам кривої, кінець лінії або перетин ліній). Від кола лишається тільки частина між
сторонами кута. Деталь лежить на місці, у шарі Parts::Reinforcements, з підписом "RC<n>  R=…"
у групі. Нумерація RC продовжується між запусками. Вихідні криві не змінюються.
Підсилення нашивається поверх матеріалу, тому припуску на шов немає.
"""
import os
import re
import sys

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
from System.Collections.Generic import List
from Rhino.Geometry import (AreaMassProperties, ArcCurve, Circle, Continuity, Curve, CurveEnd,
                            CurveExtensionStyle, Plane, Point3d)
from Rhino.Geometry.Intersect import Intersection

try:  # стилі тексту PAT для лекал 1:1 (scripts/markup/PatternTextStyles.py)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
    import PatternTextStyles
except Exception:
    PatternTextStyles = None

STICKY = "ReinfCircle"
LAYER = "Parts::Reinforcements"
PREFIX = "RC"  # Reinforcement Circle; інші форми — свої префікси (RS, RT…)


def corners(curves, tol):
    """Кандидати в центр: зломи, кінці відкритих кривих, перетини кривих між собою."""
    pts = []
    for c in curves:
        if not c.IsClosed:
            pts += [c.PointAtStart, c.PointAtEnd]
        t, t1 = c.Domain.T0, c.Domain.T1
        while True:
            ok, t = c.GetNextDiscontinuity(Continuity.G1_locus_continuous, t, t1)
            if not ok:
                break
            pts.append(c.PointAt(t))
    for i in range(len(curves)):
        for j in range(i + 1, len(curves)):
            for e in Intersection.CurveCurve(curves[i], curves[j], tol, tol) or []:
                pts.append(e.PointA)
    # ponytail: скруглений (філетом) кут не має вершини — центр візьметься з найближчого зламу;
    # якщо треба — шукати віртуальний перетин продовжених сторін.
    return pts


def piece(curves, center, toward, r, normal, tol):
    """Частина кола (центр center, радіус r), що лежить між curves з боку точки toward. None — не вийшло."""
    plane = Plane(center, normal)
    d = plane.ClosestPoint(toward) - center
    if not d.Unitize():
        return None
    bounds = List[Curve]()
    bounds.Add(ArcCurve(Circle(plane, r)))
    for c in curves:
        # відкриті лінії продовжуємо за кут і за коло: коротка сторона теж замкне область
        ext = None if c.IsClosed else c.Extend(CurveEnd.Both, 2 * r, CurveExtensionStyle.Line)
        bounds.Add(ext or c)
    pts = List[Point3d]()
    pts.Add(center + d * (r * 0.5))  # точка всередині клину: клік може бути і далі за R
    res = Curve.CreateBooleanRegions(bounds, plane, pts, False, tol)
    if res is None or res.RegionCount == 0:
        return None
    region = res.RegionCurves(0)
    return region[0] if region and region[0].IsClosed else None


def layer():
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Reinforcements", parent="Parts")
    return LAYER


def next_number(lay):
    """Наступний номер після найбільшого RC<n>, що вже є в шарі."""
    nums = [0]
    for o in rs.ObjectsByLayer(lay) or []:
        m = re.match(PREFIX + r"(\d+)\b", rs.TextObjectText(o) if rs.IsText(o) else "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


def text_style(doc, r):
    """Стиль PAT, щоб підпис влазив у сектор (≈ R/10)."""
    if PatternTextStyles is None:
        return doc.DimStyles.Current
    styles = PatternTextStyles.ensure_styles(doc)
    fit = [h for h in PatternTextStyles.SERIES if h <= r / 10.0]
    return styles[fit[-1] if fit else PatternTextStyles.SERIES[0]]


def main():
    doc = sc.doc
    ids = rs.GetObjects(u"Виберіть межу: замкнену панель або лінії кута", rs.filter.curve, preselect=True)
    if not ids:
        return
    r = rs.GetReal(u"Радіус кола підсилення R", sc.sticky.get(STICKY, 40.0), 0.001)
    if r is None:
        return
    sc.sticky[STICKY] = r

    tol = doc.ModelAbsoluteTolerance
    curves = [rs.coercecurve(i) for i in ids]
    cands = corners(curves, tol)
    if not cands:
        print(u"У вибраних кривих немає кутів")
        return
    normal = rs.ViewCPlane().ZAxis
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer(), -1)
    style = text_style(doc, r)
    n = next_number(LAYER)
    made = 0
    while True:
        click = rs.GetPoint(u"Клікни біля кута, з того боку, що лишити (Enter — кінець)")
        if click is None:
            break
        center = min(cands, key=lambda p: p.DistanceTo(click))
        if center.DistanceTo(click) > r:
            print(u"Кут далі за R від кліку — клікни ближче до вершини")
            continue
        crv = piece(curves, center, click, r, normal, tol)
        if crv is None:
            print(u"Не вдалось вирізати сектор (клік на самій лінії? криві не в площині CPlane?)")
            continue
        label = u"%s%d  R=%g" % (PREFIX, n, r)
        amp = AreaMassProperties.Compute(crv)
        tp = Plane(rs.ViewCPlane())
        tp.Origin = amp.Centroid if amp else center
        te = Rhino.Geometry.TextEntity.Create(label, tp, style, False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        new = [doc.Objects.AddCurve(crv, attrs), doc.Objects.AddText(te, attrs)]
        rs.AddObjectsToGroup(new, rs.AddGroup())
        doc.Views.Redraw()
        print(label)
        n += 1
        made += 1
    print(u"Підсилень-кіл: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
