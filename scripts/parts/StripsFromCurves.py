# -*- coding: utf-8 -*-
"""Фаші (смуги) під виділені лінії: прямокутник висотою H і довжиною = довжина лінії.
Кожна вибрана крива — окрема смуга (нічого не з'єднується автоматично).
Якщо смуга має йти по кількох лініях — спершу об'єднай їх (_Join) в одну криву.
Fasce per bordatura del telo o rinforzo ai bordi — dipende dall'altezza scelta.

Смуги стають стовпчиком впритул одна до одної від вказаної точки (по CPlane), у шар Parts::Strips; кожна підписана "F1  L=… × H".
Той самий номер ставиться TextDot-ом посередині відповідної лінії, щоб знати, яка смуга куди.
"""
import re

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

STICKY = "StripsFromCurves"


def strips(curves):
    """Одна смуга на криву. Повертає [(довжина, середня точка)]."""
    out = []
    for c in curves:
        length = c.GetLength()
        ok, t = c.LengthParameter(length / 2.0)
        out.append((length, c.PointAt(t) if ok else c.PointAtStart))
    return out


def strips_layer():
    """Parts::Strips — створює, якщо нема."""
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer("Parts::Strips"):
        rs.AddLayer("Strips", parent="Parts")
    return "Parts::Strips"


def next_number(layer):
    """Наступний номер після найбільшого F<n>, що вже є в шарі (текст або TextDot)."""
    nums = [0]
    for o in rs.ObjectsByLayer(layer) or []:
        m = re.match(r"F(\d+)\b", rs.TextObjectText(o) if rs.IsText(o) else
                     rs.TextDotText(o) if rs.IsTextDot(o) else "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


def main():
    ids = rs.GetObjects(u"Виберіть криві для фаш (кожна крива — окрема смуга)", rs.filter.curve, preselect=True)
    if not ids:
        return
    prev_h, prev_extra = sc.sticky.get(STICKY, (50.0, 0.0))
    h = rs.GetReal(u"Висота фаші", prev_h, 0.001)
    if h is None:
        return
    extra = rs.GetReal(u"Запас по довжині (додається до кожної смуги)", prev_extra, 0.0)
    if extra is None:
        return
    sc.sticky[STICKY] = (h, extra)

    found = strips([rs.coercecurve(i) for i in ids])
    found.sort(key=lambda x: -x[0])

    base = rs.GetPoint(u"Точка, звідки ставити смуги (лівий верхній кут)")
    if not base:
        return
    plane = rs.MovePlane(rs.ViewCPlane(), base)
    layer = strips_layer()
    txt_h = min(h * 0.4, 30.0)
    rs.EnableRedraw(False)
    try:
        first = next_number(layer)
        for i, (length, mid) in enumerate(found, 1):
            n = first + i - 1
            w = length + extra
            p = Rhino.Geometry.Plane(plane.PointAt(0, -i * h), plane.XAxis, plane.YAxis)
            rect = rs.AddRectangle(p, w, h)
            rs.ObjectLayer(rect, layer)
            label = u"F%d  L=%.0f × %g" % (n, w, h)
            tp = Rhino.Geometry.Plane(p.PointAt(txt_h * 0.5, h / 2.0), p.XAxis, p.YAxis)
            t = rs.AddText(label, tp, txt_h, justification=131073)  # ліво-по центру висоти: не вилазить за смугу
            if t:
                rs.ObjectLayer(t, layer)
            d = rs.AddTextDot(u"F%d" % n, mid)
            rs.ObjectLayer(d, layer)
            print(u"F%d: довжина %.1f (+%g) → %.1f × %g" % (n, length, extra, w, h))
    finally:
        rs.EnableRedraw(True)
    print(u"Ліній: %d → смуг: %d" % (len(ids), len(found)))


if __name__ == "__main__":
    main()
