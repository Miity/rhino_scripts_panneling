# -*- coding: utf-8 -*-
"""Label legend: finds texts and TextDots placed by the scripts in the document (P1, S3  L=… × 30, ZC 20,
SA 10, Z2, Trk1, RC1  R=…, TP1  H=…, joint letters A–A) and places one text at the click point —
the meaning of only those marks that actually exist in the drawing. Changes nothing in the document, only adds text
to the current layer. Options while clicking: Lang = UA / EN / IT, Height — text height.
Font (FONTS): UA — Arial, because the single-stroke SLF-RHN Architect of the PAT styles has no Cyrillic;
EN / IT — SLF-RHN Architect, as in the labels themselves (the plotter writes in one pass).
"""
import re

LANGS = ("UA", "EN", "IT")
FONTS = {"UA": "Arial", "EN": "SLF-RHN Architect", "IT": "SLF-RHN Architect"}
TITLE = {"UA": u"Легенда", "EN": u"Legend", "IT": u"Legenda"}

# (regex of the label's first line, legend lines UA / EN / IT) — in output order
ENTRIES = [
    (r"P\d+$", (u"P<n> — панель (Parts::Panels)",
                u"P<n> — panel (Parts::Panels)",
                u"P<n> — pannello (Parts::Panels)")),
    (r"S\d+\s", (u"S<n>  L × H — фаша / смуга: довжина × висота",
                 u"S<n>  L × H — binding strip: length × height",
                 u"S<n>  L × H — fascia (bordatura / rinforzo): lunghezza × altezza")),
    (r"ZC\s", (u"ZC W — клапан над блискавкою, ширина W",
               u"ZC W — zip cover flap, width W",
               u"ZC W — copri zip, larghezza W")),
    (r"SA\s", (u"SA W — припуск на шов, ширина W",
               u"SA W — seam allowance, width W",
               u"SA W — margine di cucitura, larghezza W")),
    (r"Z\d+$", (u"Z<n> — блискавка (обидві сторони мають один номер)",
                u"Z<n> — zipper (both sides share the number)",
                u"Z<n> — cerniera (stesso numero su entrambi i lati)")),
    (r"Trk\d+$", (u"Trk<n> — каналіна (одна сторона)",
                  u"Trk<n> — track (one side)",
                  u"Trk<n> — canalina / guida")),
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
    """Legend lines in language lang for the marks found among texts (label lines)."""
    k = LANGS.index(lang)
    firsts = [t.strip().splitlines()[0].strip() for t in texts if t and t.strip()]
    return [lines[k] for rx, lines in ENTRIES if any(re.match(rx, s) for s in firsts)]


HELP = u"""Options:
  Lang — legend language: UA / EN / IT
  Height — legend text height"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    import Rhino

    texts = [rs.TextObjectText(o) if rs.IsText(o) else rs.TextDotText(o)
             for o in rs.ObjectsByType(512 | 8192) or []]  # 512 text, 8192 TextDot
    if not legend_lines(texts):
        print(u"No script labels found in the document")
        return
    lang = sc.sticky.get("Legend_lang", "UA")
    h = Rhino.Input.Custom.OptionDouble(sc.sticky.get("Legend_h", 14), 0.1, 1e6)
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Click where to place the legend (top-left corner)")
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
    print(u"Legend (%s): %d marks" % (lang, len(lines)))


if __name__ == "__main__":
    main()
