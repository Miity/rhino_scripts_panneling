# -*- coding: utf-8 -*-
"""Кутове підсилення — коло (rinforzo d'angolo, cerchio).
Вибираєш межу: замкнену панель або лінії, що утворюють кут. Задаєш радіус R.
Клікаєш біля кута з того боку, який лишити. Центр кола — найближча до кліку вершина
(злам кривої, кінець лінії або перетин ліній). Від кола лишається тільки частина між
сторонами кута. Деталь лежить на місці, у шарі Parts::Reinforcements, з підписом "RC<n>  R=…"
у групі. Нумерація RC продовжується між запусками. Вихідні криві не змінюються.
Опція Layout (типово Yes) — як у всіх Reinf (add_part): на панелі лишається тільки розмітка — лінії деталі, що не лежать на кривих
панелі, + підпис; повна деталь (різ, шов, підпис) — на UP (10000) вгору по Y CPlane, її розкладати Layout.
Layout=No — повна деталь на місці, без розмітки.
Підсилення нашивається поверх матеріалу, тому припуску на шов немає.
"""
import os
import re
import sys

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import System
from System.Collections.Generic import List
from Rhino.Geometry import (AreaMassProperties, ArcCurve, Circle, Continuity, Curve, CurveEnd,
                            CurveExtensionStyle, Plane, Point3d, Transform)
from Rhino.Geometry.Intersect import Intersection

try:  # стилі тексту PAT для лекал 1:1 (scripts/markup/PatternTextStyles.py)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
    import PatternTextStyles
except Exception:
    PatternTextStyles = None

STICKY = "ReinfCircle"
LAYER = "Parts::Reinforcements"
PREFIX = "RC"  # Reinforcement Circle; інші форми — свої префікси (RS, RT…)
UP = 10000.0  # повна деталь — на стільки вгору по Y CPlane від розмітки (як TubePockets)


def off_panel(crv, curves, tol):
    """Розмітка: сегменти crv, що не лежать на curves (лінії панелі не дублюємо), з'єднані."""
    def on(p):
        return any(c.PointAt(c.ClosestPoint(p)[1]).DistanceTo(p) <= tol for c in curves)
    keep = [s for s in crv.DuplicateSegments() or [crv]
            if not all(on(s.PointAtNormalizedLength(t)) for t in (0.25, 0.5, 0.75))]
    return list(Curve.JoinCurves(keep, tol)) if keep else []


def add_part(doc, full, te, markup, attrs, layout=True):
    """layout: повна деталь (геометрія full + підпис te) — на UP вгору по Y CPlane, своя група;
    на місці — розмітка (криві markup + той самий підпис), своя група. Повертає (id повної, id розмітки).
    Без layout — повна деталь на місці, розмітки немає (id розмітки = []).
    Пара зв'язана UserText PartLink (спільний id); повна деталь має LayoutUp (вектор зсуву), розмітка — PartMarkup.
    JoinCorner за ними з'єднує деталі угорі й перебудовує розмітку."""
    xf = Transform.Translation(rs.ViewCPlane().YAxis * (UP if layout else 0.0))

    def add(geo):
        geo = geo.Duplicate()
        geo.Transform(xf)
        return doc.Objects.Add(geo, attrs)
    ids = [add(c) for c in full] + [add(te)], []
    if layout:
        ids = ids[0], [doc.Objects.AddCurve(c, attrs) for c in markup] + [doc.Objects.AddText(te, attrs)]
    if layout:
        link, up = str(System.Guid.NewGuid()), rs.ViewCPlane().YAxis * UP
        for o in ids[0] + ids[1]:
            rs.SetUserText(o, "PartLink", link)
        for o in ids[0]:
            rs.SetUserText(o, "LayoutUp", "%r,%r,%r" % (up.X, up.Y, up.Z))
        for o in ids[1]:
            rs.SetUserText(o, "PartMarkup", "1")
    for g in ids:
        if g:
            rs.AddObjectsToGroup(g, rs.AddGroup())
    return ids


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


def next_number(lay, prefix=PREFIX):
    """Наступний номер після найбільшого <prefix><n> (RC, RD…), що вже є в шарі."""
    nums = [0]
    for o in rs.ObjectsByLayer(lay) or []:
        m = re.match(prefix + r"(\d+)\b", rs.TextObjectText(o) if rs.IsText(o) else "")
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


HELP = u"""Опції:
  R — радіус кола підсилення (центр — кут панелі)
  Layout — Yes: на панелі лише розмітка, повна деталь на 10000 вгору; No: повна деталь на місці"""  # друкується на старті — видно під полями опцій


def main():
    print(HELP)
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
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Клікни біля кута, з того боку, що лишити (Enter — кінець)")
        gp.AcceptNothing(True)
        lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", True), "No", "Yes")
        gp.AddOptionToggle("Layout", lay)
        while gp.Get() == Rhino.Input.GetResult.Option:
            pass
        sc.sticky[STICKY + "_layout"] = lay.CurrentValue
        if gp.CommandResult() != Rhino.Commands.Result.Success or gp.Result() != Rhino.Input.GetResult.Point:
            break
        click = gp.Point()
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
        add_part(doc, [crv], te, off_panel(crv, curves, tol), attrs, lay.CurrentValue)
        doc.Views.Redraw()
        print(label)
        n += 1
        made += 1
    print(u"Підсилень-кіл: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
