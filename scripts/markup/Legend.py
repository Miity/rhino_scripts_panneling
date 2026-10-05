# -*- coding: utf-8 -*-
"""Легенда підписів: знаходить у документі тексти й TextDot-и, поставлені скриптами (P1, F3  L=… × 30, CZ 20,
SA 10, Z2, Can1, RC1  R=…, TP1  H=…, літери стиків A–A), і ставить у точку кліку один текст —
розшифровку тільки тих позначок, що реально є в кресленні. Нічого в документі не змінює, лише додає текст
у поточний шар. Опції під час кліку: Lang = UA / EN / IT, Height — висота тексту.
Шрифт (FONTS): UA — Arial, бо одноштриховий SLF-RHN Architect зі стилів PAT не має кирилиці;
EN / IT — SLF-RHN Architect, як у самих підписах (плотер пише одним проходом).
"""
import re

LANGS = ("UA", "EN", "IT")
FONTS = {"UA": "Arial", "EN": "SLF-RHN Architect", "IT": "SLF-RHN Architect"}
TITLE = {"UA": u"Легенда", "EN": u"Legend", "IT": u"Legenda"}

# (regex першого рядка підпису, рядки легенди UA / EN / IT) — у порядку виводу
ENTRIES = [
    (r"P\d+$", (u"P<n> — панель (Parts::Panels)",
                u"P<n> — panel (Parts::Panels)",
                u"P<n> — pannello (Parts::Panels)")),
    (r"F\d+\s", (u"F<n>  L × H — фаша / смуга: довжина × висота",
                 u"F<n>  L × H — binding strip: length × height",
                 u"F<n>  L × H — fascia (bordatura / rinforzo): lunghezza × altezza")),
    (r"CZ\s", (u"CZ W — клапан над блискавкою (copri zip), ширина W",
               u"CZ W — zip cover flap, width W",
               u"CZ W — copri zip, larghezza W")),
    (r"SA\s", (u"SA W — припуск на шов, ширина W",
               u"SA W — seam allowance, width W",
               u"SA W — margine di cucitura, larghezza W")),
    (r"Z\d+$", (u"Z<n> — блискавка (обидві сторони мають один номер)",
                u"Z<n> — zipper (both sides share the number)",
                u"Z<n> — cerniera (stesso numero su entrambi i lati)")),
    (r"Can\d+$", (u"Can<n> — каналіна / guida",
                  u"Can<n> — canalina / track (one side)",
                  u"Can<n> — canalina / guida")),
    (r"RC\d+\s", (u"RC<n>  R — кутове підсилення, коло радіуса R",
                  u"RC<n>  R — corner reinforcement, circle of radius R",
                  u"RC<n>  R — rinforzo d'angolo, cerchio di raggio R")),
    (r"TP\d+\s", (u"TP<n>  H — карман для труби, висота H",
                  u"TP<n>  H — tube pocket, height H",
                  u"TP<n>  H — tasca per tubo, altezza H")),
    (r"[A-Z]{1,2}$", (u"A–A, B–B… — стик шматків панелі, розрізаної по ширині матеріалу (шов 1 см)",
                      u"A–A, B–B... — joint of panel pieces split to material width (1 cm seam)",
                      u"A–A, B–B... — giunzione dei pezzi di un pannello diviso per larghezza del materiale (cucitura 1 cm)")),
]


def legend_lines(texts, lang="UA"):
    """Рядки легенди мовою lang для позначок, що трапляються серед texts (рядки підписів)."""
    k = LANGS.index(lang)
    firsts = [t.strip().splitlines()[0].strip() for t in texts if t and t.strip()]
    return [lines[k] for rx, lines in ENTRIES if any(re.match(rx, s) for s in firsts)]


def main():
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    import Rhino

    texts = [rs.TextObjectText(o) if rs.IsText(o) else rs.TextDotText(o)
             for o in rs.ObjectsByType(512 | 8192) or []]  # 512 текст, 8192 TextDot
    if not legend_lines(texts):
        print(u"Підписів зі скриптів у документі не знайдено")
        return
    lang = sc.sticky.get("Legend_lang", "UA")
    h = Rhino.Input.Custom.OptionDouble(sc.sticky.get("Legend_h", 10), 0.1, 1e6)
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Клікни, де поставити легенду (лівий верхній кут)")
    while True:
        gp.ClearCommandOptions()
        i_lang = gp.AddOptionList("Lang", LANGS, LANGS.index(lang))
        gp.AddOptionDouble("Height", h)
        res = gp.Get()
        if res == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_lang:
                lang = LANGS[gp.Option().CurrentListOptionIndex]
            continue
        if res != Rhino.Input.GetResult.Point:
            return
        break
    sc.sticky["Legend_lang"], sc.sticky["Legend_h"] = lang, h.CurrentValue
    lines = legend_lines(texts, lang)
    body = u"%s (%s)\n" % (TITLE[lang], rs.UnitSystemName(abbreviate=True)) + u"\n".join(lines)
    plane = rs.ViewCPlane()
    plane.Origin = gp.Point()
    rs.AddText(body, plane, h.CurrentValue, FONTS[lang], justification=262145)  # 262145 = Left | Top
    sc.doc.Views.Redraw()
    print(u"Легенда (%s): %d позначок" % (lang, len(lines)))


if __name__ == "__main__":
    main()
