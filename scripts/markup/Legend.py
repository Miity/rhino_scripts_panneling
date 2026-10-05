# -*- coding: utf-8 -*-
"""Легенда підписів: знаходить у документі тексти й TextDot-и, поставлені скриптами (P1, F3  L=… × 30, CZ 20,
SA 10, Z2, Can1, RC1  R=…, TP1  H=…, літери стиків A–A), і ставить у точку кліку один текст —
розшифровку тільки тих позначок, що реально є в кресленні. Нічого в документі не змінює, лише додає текст
у поточний шар (висоту питає). Шрифт звичайний (FONT): одноштриховий SLF-RHN Architect
зі стилів PAT не має кирилиці.
"""
import re

FONT = "Arial"

# (regex першого рядка підпису, рядок легенди) — у порядку виводу
ENTRIES = [
    (r"P\d+$", u"P<n> — панель (Parts::Panels)"),
    (r"F\d+\s", u"F<n>  L × H — фаша / смуга: довжина × висота"),
    (r"CZ\s", u"CZ W — клапан над блискавкою (copri zip), ширина W"),
    (r"SA\s", u"SA W — припуск на шов, ширина W"),
    (r"Z\d+$", u"Z<n> — блискавка (обидві сторони мають один номер)"),
    (r"Can\d+$", u"Can<n> — каналіна / guida"),
    (r"RC\d+\s", u"RC<n>  R — кутове підсилення, коло радіуса R"),
    (r"TP\d+\s", u"TP<n>  H — карман для труби, висота H"),
    (r"[A-Z]{1,2}$", u"A–A, B–B… — стик шматків панелі, розрізаної по ширині матеріалу (шов 1 см)"),
]


def legend_lines(texts):
    """Рядки легенди для позначок, що трапляються серед texts (рядки підписів)."""
    firsts = [t.strip().splitlines()[0].strip() for t in texts if t and t.strip()]
    return [line for rx, line in ENTRIES if any(re.match(rx, s) for s in firsts)]


def main():
    import rhinoscriptsyntax as rs
    import scriptcontext as sc

    texts = [rs.TextObjectText(o) if rs.IsText(o) else rs.TextDotText(o)
             for o in rs.ObjectsByType(512 | 8192) or []]  # 512 текст, 8192 TextDot
    lines = legend_lines(texts)
    if not lines:
        print(u"Підписів зі скриптів у документі не знайдено")
        return
    units = rs.UnitSystemName(abbreviate=True)
    body = u"Легенда (%s)\n" % units + u"\n".join(lines)
    h = rs.GetReal(u"Висота тексту легенди", sc.sticky.get("Legend_h", 10), 0.1)
    if h is None:
        return
    sc.sticky["Legend_h"] = h
    pt = rs.GetPoint(u"Клікни, де поставити легенду (лівий верхній кут)")
    if pt is None:
        return
    plane = rs.ViewCPlane()
    plane.Origin = pt
    rs.AddText(body, plane, h, FONT, justification=262145)  # 262145 = Left | Top
    sc.doc.Views.Redraw()
    print(u"Легенда: %d позначок" % len(lines))


if __name__ == "__main__":
    main()
