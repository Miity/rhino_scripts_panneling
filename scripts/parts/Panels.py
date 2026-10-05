# -*- coding: utf-8 -*-
"""Панелі → частини P1, P2, P3…
Вибираєш замкнені криві (панелі). Кожна панель копіюється на те саме місце в шар Parts::Panels
і отримує номер P<n>: текст усередині панелі в куті, біля якого клікнеш (Enter — правий верхній;
розміщення як у markup/DotToPanelText.py), стиль — опція Style (запам'ятовується),
і TextDot "P<n>" вище-зліва від краю панелі, щоб номер було видно при будь-якому зумі.
Номер пишеться і в UserText (Part = P<n>) на оригінал і на копію: повторний запуск
уже пронумеровані панелі пропускає, а нумерація продовжується з найбільшого P у шарі.
Крива, що лежить усередині іншої вибраної — виріз (отвір) цієї панелі: копіюється разом з нею
під тим самим номером, свого номера не забирає. Копія, вирізи, текст і TextDot — одна група.
"""
import os
import re
import sys

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
from Rhino.Geometry import Curve, RegionContainment

# розміщення тексту в куті панелі та вибір стилю — з scripts/markup/DotToPanelText.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
import DotToPanelText as D

LAYER = "Parts::Panels"
PREFIX = "P"
KEY = "Part"  # ключ UserText з номером панелі
STYLE = "Panels.style"


def bbox(crv, plane):
    """(xmin, ymin, xmax, ymax) кривої в координатах plane."""
    b = crv.GetBoundingBox(plane)
    return b.Min.X, b.Min.Y, b.Max.X, b.Max.Y


def classify(curves, plane, tol):
    """[(i, [індекси вирізів])] — зовнішні панелі в порядку читання: рядки згори вниз, у рядку зліва направо."""
    holes = {}
    outer = []
    for i, a in enumerate(curves):
        parent = None
        for j, b in enumerate(curves):
            if i != j and Curve.PlanarClosedCurveRelationship(a, b, plane, tol) == RegionContainment.AInsideB:
                if parent is None or Curve.PlanarClosedCurveRelationship(
                        curves[parent], b, plane, tol) == RegionContainment.AInsideB:
                    parent = j  # найбільший контейнер: виріз у вирізі все одно належить зовнішній панелі
        if parent is None:
            outer.append(i)
        else:
            holes.setdefault(parent, []).append(i)
    boxes = dict((i, bbox(curves[i], plane)) for i in outer)
    order, rows = sorted(outer, key=lambda i: -boxes[i][3]), []
    for i in order:  # новий рядок, коли верх панелі нижче за низ першої панелі поточного рядка
        if rows and boxes[i][3] > boxes[rows[-1][0]][1]:
            rows[-1].append(i)
        else:
            rows.append([i])
    return [(i, holes.get(i, [])) for row in rows for i in sorted(row, key=lambda k: boxes[k][0])]


def layer():
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Panels", parent="Parts")
    return LAYER


def next_number(lay):
    """Наступний номер після найбільшого P<n> у шарі (UserText, текст або TextDot)."""
    nums = [0]
    for o in rs.ObjectsByLayer(lay) or []:
        s = rs.GetUserText(o, KEY) or (rs.TextObjectText(o) if rs.IsText(o) else
                                       rs.TextDotText(o) if rs.IsTextDot(o) else "")
        m = re.match(PREFIX + r"(\d+)$", s or "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


def get_corner(doc, crv, name, style):
    """Клік біля кута панелі для тексту; Enter — правий верхній; опція Style. Повертає (точка або None, стиль)."""
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Клікни біля кута панелі для %s (Enter — правий верхній, стиль: %s)" % (name, style))
        gp.AcceptNothing(True)
        opt = gp.AddOption("Style")
        res = gp.Get()
        if res == Rhino.Input.GetResult.Option and gp.OptionIndex() == opt:
            style = D.pick_style(doc, style)
            sc.sticky[STYLE] = style
            continue
        if res == Rhino.Input.GetResult.Point:
            return gp.Point(), style
        if res == Rhino.Input.GetResult.Nothing:
            return crv.GetBoundingBox(True).Max, style
        return None, style


def main():
    doc = sc.doc
    ids = rs.GetObjects(u"Виберіть панелі (замкнені криві)", rs.filter.curve, preselect=True)
    if not ids:
        return
    picked = list(ids)
    tol = doc.ModelAbsoluteTolerance
    plane = rs.ViewCPlane()

    live = set(rs.GetUserText(o, KEY) for o in rs.ObjectsByLayer(LAYER) or [] if rs.IsCurve(o)) if rs.IsLayer(LAYER) else set()
    live.discard(None)  # непронумеровані криві в шарі не роблять «пронумерованими» всі криві без мітки
    # пронумерована — лише якщо її копія з цим номером ще є (після Undo чи видалення копії мітка не заважає)
    done = [i for i in ids if rs.GetUserText(i, KEY) in live]
    bad = [i for i in ids if i not in done and not (rs.IsCurveClosed(i) and rs.IsCurvePlanar(i))]
    ids = [i for i in ids if i not in done and i not in bad]
    if done:
        print(u"Вже пронумеровані, пропущено: %d" % len(done))
    if bad:
        print(u"Не замкнені або не плоскі, пропущено: %d" % len(bad))
    if not ids:
        return

    curves = [rs.coercecurve(i) for i in ids]
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer(), -1)
    n = next_number(LAYER)
    D.pts.ensure_styles(doc)
    style = sc.sticky.get(STYLE)
    if not style or doc.DimStyles.FindName(style) is None:  # за замовчуванням — PAT за шириною першої панелі
        x0, y0, x1, y1 = bbox(curves[0], plane)
        style = D.pts.style_name(D.pts.height_for(min(x1 - x0, y1 - y0)))
    made = 0
    for i, hole_idx in classify(curves, plane, tol):
        name = u"%s%d" % (PREFIX, n)
        crv = curves[i]
        rs.UnselectAllObjects()
        rs.SelectObject(ids[i])  # підсвітити, яку панель зараз підписуємо
        click, style = get_corner(doc, crv, name, style)
        if click is None:
            break
        sc.sticky[STYLE] = style
        ds = doc.DimStyles.FindName(style)
        # TextDot біля верхнього лівого краю панелі: найближча до кута габариту точка кривої, трохи вгору-вліво
        x0, y0, x1, y1 = bbox(crv, plane)
        ok, t = crv.ClosestPoint(plane.PointAt(x0, y1))
        gap = 2 * ds.TextHeight * ds.DimensionScale
        dot = Rhino.Geometry.TextDot(name, crv.PointAt(t) + (plane.YAxis - plane.XAxis) * gap)

        tagged = attrs.Duplicate()
        tagged.SetUserString(KEY, name)
        new = [doc.Objects.AddCurve(curves[k], tagged) for k in [i] + hole_idx]
        for k in [i] + hole_idx:  # ModifyAttributes, а не rs.SetUserText: так мітку відкочує Undo
            obj = doc.Objects.FindId(ids[k])
            a = obj.Attributes.Duplicate()
            a.SetUserString(KEY, name)
            doc.Objects.ModifyAttributes(obj, a, True)
        tid = D.place_text(doc, name, crv, click, ds, attrs, tol)
        if not tid:
            print(u"%s: текст не влазить у панель (менший стиль — опція Style), лишився TextDot" % name)
        new += [o for o in (tid, doc.Objects.AddTextDot(dot, attrs)) if o]
        rs.AddObjectsToGroup(new, rs.AddGroup())
        doc.Views.Redraw()
        print(u"%s%s" % (name, u"  (вирізів: %d)" % len(hole_idx) if hole_idx else u""))
        n += 1
        made += 1
    rs.UnselectAllObjects()
    rs.SelectObjects(picked)  # вибір як був
    print(u"Панелей: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
