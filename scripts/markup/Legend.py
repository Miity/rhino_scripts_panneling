# -*- coding: utf-8 -*-
"""Label legend: finds texts and TextDots placed by the scripts in the document (Italian codes, numbers in cm:
P1, F5  l=120, CZ3, C1, Z2, Can1, R6, RC1  r=4, RD1, RO1  r=15, T1  h=8, joint letters A–A) and places one text
at the click point — the meaning of only those marks that actually exist in the drawing. Changes nothing in the document,
only adds text to the current layer. Options while clicking: Lang = UA / EN / IT (default IT — for the seamstresses), Height.
Font (FONTS): UA — Arial, because the single-stroke SLF-RHN Architect of the PAT styles has no Cyrillic;
EN / IT — SLF-RHN Architect, as in the labels themselves (the plotter writes in one pass).
"""
import re

LANGS = ("UA", "EN", "IT")
FONTS = {"UA": "Arial", "EN": "SLF-RHN Architect", "IT": "SLF-RHN Architect"}
TITLE = {"UA": u"Легенда (см)", "EN": u"Legend (cm)", "IT": u"Legenda (cm)"}

# (regex of the label's first line, legend lines UA / EN / IT) — in output order
ENTRIES = [
    (r"P\d+$", (u"P<n> — панель",
                u"P<n> — panel",
                u"P<n> — pannello")),
    (r"F[\d.]+\s", (u"F<w>  l — фаша (смуга): ширина w, довжина l",
                    u"F<w>  l — fascia strip: width w, length l",
                    u"F<w>  l — fascia: larghezza w, lunghezza l")),
    (r"CZ[\d.]+", (u"CZ<w> — клапан над блискавкою / каналіною, ширина w",
                   u"CZ<w> — zip / track cover flap, width w",
                   u"CZ<w> — copri zip / canalina, larghezza w")),
    (r"C[\d.]+(\s|$)", (u"C<w> — шов (з батутами), ширина w",
                        u"C<w> — seam allowance (with notches), width w",
                        u"C<w> — cucitura (con battute), larghezza w")),
    (r"Z\d+$", (u"Z<n> — блискавка (обидві сторони мають один номер)",
                u"Z<n> — zipper (both sides share the number)",
                u"Z<n> — cerniera (stesso numero su entrambi i lati)")),
    (r"Can\d+$", (u"Can<n> — каналіна (одна сторона)",
                  u"Can<n> — track (one side)",
                  u"Can<n> — canalina")),
    (r".*\bR[\d.]+(\s|$)", (u"R<w> — підсилення: смуга на панелі без згину, ширина w (l — довжина)",
                            u"R<w> — reinforcement strip laid on the panel, not folded, width w (l — length)",
                            u"R<w> — rinforzo sul pannello, senza piega, larghezza w (l — lunghezza)")),
    (r"RC\d+\s", (u"RC<n>  r — кутове підсилення, коло радіуса r",
                  u"RC<n>  r — corner reinforcement, circle of radius r",
                  u"RC<n>  r — rinforzo d'angolo, cerchio di raggio r")),
    (r"RD\d+$", (u"RD<n> — підсилення у формі D",
                 u"RD<n> — D-shaped reinforcement",
                 u"RD<n> — rinforzo a D")),
    (r"RO\d+\s", (u"RO<n>  r — підсилення у формі O, радіус r",
                  u"RO<n>  r — O-shaped reinforcement, radius r",
                  u"RO<n>  r — rinforzo a O, raggio r")),
    (r"T\d+\s", (u"T<n>  h — карман, висота h",
                 u"T<n>  h — pocket, height h",
                 u"T<n>  h — tasca, altezza h")),
    (r"[A-Z]{1,2}$", (u"A–A, B–B… — стик шматків панелі, розрізаної по ширині матеріалу (шов 1 см)",
                      u"A–A, B–B... — joint of panel pieces split to material width (1 cm seam)",
                      u"A–A, B–B... — giunzione dei pezzi di un pannello diviso per larghezza del materiale (cucitura 1 cm)")),
]


def legend_lines(texts, lang="IT"):
    """Legend lines in language lang for the marks found among texts (label lines)."""
    k = LANGS.index(lang)
    firsts = [t.strip().splitlines()[0].strip() for t in texts if t and t.strip()]
    return [lines[k] for rx, lines in ENTRIES if any(re.match(rx, s) for s in firsts)]


HELP = u"""Options:
  Lang — legend language: UA / EN / IT (default IT)
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
    lang = sc.sticky.get("Legend_lang", "IT")
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
    body = TITLE[lang] + u"\n" + u"\n".join(lines)
    plane = rs.ViewCPlane()
    plane.Origin = gp.Point()
    rs.AddText(body, plane, h.CurrentValue, FONTS[lang], justification=262145)  # 262145 = Left | Top
    sc.doc.Views.Redraw()
    print(u"Legend (%s): %d marks" % (lang, len(lines)))


if __name__ == "__main__":
    main()
