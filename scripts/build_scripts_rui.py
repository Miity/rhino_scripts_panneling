# -*- coding: utf-8 -*-
"""Builds Scripts.rui (project root): 6 separate toolbars (Sizes / Curves / Analysis / Cut / Parts / Markup)
shown as tabs in one Rhino panel.
Run with plain python3 outside Rhino: python3 scripts/build_scripts_rui.py
Build with Rhino closed; Rhino picks up the changes after a restart. How to connect it the first time — README.md.
To add a script — add a line to GROUPS (English) and to IT (Italian), and rerun this file.
LANG picks the toolbar language: "IT" (default, for the Italian shop) or "EN" (the English texts in GROUPS).
GUIDs are deterministic (uuid5 of the English name), so regenerating or switching LANG does not break the toolbar layout.
"""
import os
import uuid
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = ROOT + "/scripts/"
NS = uuid.UUID("5c7a1f7e-2b1d-4a38-9a51-6d0b3f2e8c11")


def py(name):
    return '!_-RunPythonScript "%s%s"' % (S, name)


GH_SEW = '! _-GrasshopperPlayer "%s/Grasshoper scripts/sew points.gh"\n\n\n\n' % ROOT

# (group = tab name, group description, [(button, tooltip, macro, (right button, tooltip, macro) | None)])
GROUPS = [
    (u"Sizes", u"Sizes and extents", [
        (u"BBoxSize", u"Bounding box in the CPlane with XYZ size labels", py("sizes/BoundingBoxWithSize_Rhino8_CPlane.py"),
         (u"BBoxCenterLines", u"Flat box in the CPlane + two centre lines", py("sizes/BoundingBoxCenterLines.py"))),
        (u"LabelSizes", u"Label the size inside each closed curve", py("sizes/LabelClosedCurveSizes.py"), None),
        (u"Rect 1340", u"Rectangle 1340 × 6658 centred on the CPlane", py("sizes/draw_centered_rectangle.py"), None),
    ]),
    (u"Curves", u"Curve editing", [
        (u"SplitByAngle", u"Split curves at corners sharper than the threshold", py("curves/SplitCrvByAngle.py"),
         (u"SmoothCorners", u"Round polyline corners sharper than the threshold", py("curves/smooth_corners.py"))),
        (u"CrvToPolyline", u"Convert curves to polylines (layer kept)", py("curves/CrvToPolyline.py"), None),
        (u"TrimEnds", u"Trim curve ends by a given distance", py("curves/TrimCrvEnds.py"),
         (u"KeepEnds", u"Cut out the middle of a curve, keep ends of a given length", py("curves/KeepCrvEnds.py"))),
        (u"TrimOutside", u"Trim everything outside the panel contour", py("curves/TrimOutsidePanel.py"), None),
        (u"ExactConnection", u"Contact point on a curve at a given length", py("curves/find_exact_connection.py"), None),
        (u"MidLine", u"Line from the midpoint of one curve to the midpoint of another", py("curves/MidLine.py"), None),
        (u"OffsetRigid", u"Copy of a curve without changing its shape, moved along the normal at the clicked point", py("curves/OffsetRigid.py"), None),
    ]),
    (u"Analysis", u"Panel and cut analysis", [
        (u"SmallClosed", u"Select closed curves smaller than the minimum cut area", py("analysis/SelectSmallClosedCurves.py"), None),
        (u"CutRisks", u"Mark risky cut spots (geometry unchanged)", py("analysis/CheckTangentialCutRisks.py"), None),
        (u"RecommendTabs", u"Select contours that need tabs (small or narrow)", py("analysis/RecommendCutTabs.py"), None),
        (u"CutTabs", u"Interactively add tabs to cut contours", py("analysis/AddCutTabs.py"), None),
    ]),
    (u"Cut", u"Cut preparation", [
        (u"PreparePanelCut", u"Panels → one outer contour on CUT, inner lines on INT/INK", py("cut/PreparePanelCut.py"), None),
        (u"SplitToMaterial", u"Split panels to the material width: 1 cm seam, pieces moved by 50", py("cut/SplitPanelsToMaterial.py"), None),
        (u"CurveOverlap", u"Delete exact duplicates (SelDup), select the shorter curve of each overlapping pair (among selected, or all curves)", py("cut/sel_curve_overlap.py"), None),
    ]),
    (u"Parts", u"Creating parts (strips, reinforcements…) in the Parts layer", [
        (u"Panels", u"Panels → copy in Parts::Panels numbered P1, P2… (text inside + TextDot)", py("parts/Panels.py"), None),
        (u"SewingPoints", u"Battute: panels / curves + click near an edge → points from the edge centre (corner to corner) both ways with Step (200 mm) + centre tick (Tick 10 mm, into the panel); Parts::SewingMarks", py("parts/sewing_points.py"),
         (u"SewPoints GH", u"Seam points (Grasshopper Player, old version)", GH_SEW)),
        (u"Strips", u"Fascia strips under the selected lines: width W, length = length of each curve; label F<w>  l=… (cm)", py("parts/StripsFromCurves.py"), None),
        (u"ZipCover", u"Zip cover: panel edge (corner to corner) + offset W outward, ends along the neighbouring edges; label Off<w> (cm, offset); EditPanel=Yes — the panel contour itself grows", py("parts/ZipCover.py"), None),
        (u"Join Corner", u"Join any two open curves at a corner, edge to edge: click near the corner → edges (corner to corner) extended / trimmed to their intersection, ends beyond removed, one curve", py("parts/JoinCorner.py"), None),
        (u"Merge Outline", u"Merge a closed panel and a curve that together enclose an area into one panel by the outer line; the old edge left inside becomes an open curve", py("parts/MergeOutline.py"), None),
        (u"ZipStops", u"Zips (Z<n>) and tracks (canalina Can<n>, option Type): click panel edges / curves; L-stops Trim in, junction ticks, number — all on the text side", py("parts/ZipStops.py"), None),
        (u"ZipList", u"Order table: zips (longer side, cm × pcs) and tracks (full length); CSV next to the .3dm + clipboard", py("parts/ZipList.py"), None),
        (u"Mark Reinf", u"Reinforcement strip without a part: select labels (Off / C…), the panel is found automatically → append R<w> (cm), edge length in UserText", py("parts/MarkReinf.py"), None),
        (u"Reinf Strip", u"Reinforcement R<w> laid on the panel, not folded: edge (corner to corner) + offset W (6 cm) into the panel, ends along the neighbouring edges; cut longer by Plus (10 cm), trimmed after sewing; label R<w>  l=… (cm)", py("parts/Rinforzo.py"), None),
        (u"Bordino", u"Bordino B<w>: panel edge (corner to corner) → separate straight strip W (3.5 cm; 4.5 rinforzato) × edge + Plus (6 cm) next to the panel + its copy Up (10000) up, label B<w> (cm); on the panel only B<w> after Z<n> R<w>", py("parts/Bordino.py"), None),
        (u"Pettola", u"Pettola Pt<w>: the same as Bordino, only wider (6–14 cm and more, default 10): separate straight strip W × edge + Plus (6 cm) next to the panel + its copy Up (10000) up, label Pt<w> (cm); on the panel only Pt<w> after Z<n> R<w> B<w>", py("parts/Pettola.py"), None),
        (u"Reinf D", u"D reinforcement at the end of a pocket: top corner → bottom corner, width W, extension R", py("parts/ReinfD.py"), None),
        (u"Reinf O", u"O reinforcement at the end of a full-width pocket: centre at the top corner → click on a line, R = distance + Plus (5 cm), only inside the panel", py("parts/ReinfO.py"), None),
        (u"RList", u"Reinforcement strip table: edge + Plus (10 cm), totals by width; CSV next to the .3dm + clipboard", py("parts/RList.py"), None),
        (u"Tube Pockets", u"Tube pockets T<n>: panel → click near an edge, W centred on the edge, height H, narrowing Trim, no seam allowance, hem allowance at the ends Hem, centre mark, Rigid — rigid offset", py("parts/TubePockets.py"), None),
        (u"Update Pockets", u"Update existing T pockets: new H / Trim / Hem / Notch / Rigid in place, same number (only what you changed changes)", py("parts/UpdateTubePockets.py"), None),
        (u"Part Panel", u"Panel number on parts: select parts (window) → \" P<n>\" added to each part's label; the panel is found from where the part sits on it (part up → back down; Bordino — its edge)", py("parts/PartPanel.py"), None),
        (u"Layout", u"Canvas: parts with contour, seam points, centre ticks and label codes in a row, in <layer>::Layout; the rest stays on the schema", py("parts/LayoutParts.py"), None),
        (u"Layout Stack", u"Strips that may turn along the grain — options Rinforzo / Bordini: copies on the canvas along CPlane X, stacked down from the click Gap apart (0 — touching), longest first; <layer>::Layout; Hide=Yes — the laid out parts are hidden", py("parts/LayoutStack.py"), None),
        (u"Pack Strips", u"Strips already along CPlane X (Layout Stack, Strips) moved into a compact block: rows as long as the longest strip, within the roll Width (rows get longer if needed), one block per strip width, Gap between strips (0 — touching); Enter — in place", py("parts/PackStrips.py"), None),
    ]),
    (u"Markup", u"Markup on INK", [
        (u"Crosses", u"Points → crosses or circles", py("markup/PointsToCrosses.py"), None),
        (u"Linetype 400,2", u"Assign linetype 400,2 to the selected curves", py("markup/line_type.py"), None),
        (u"TextStyles", u"Create/update PAT 2.5–40 mm text styles for 1:1 patterns", py("markup/PatternTextStyles.py"), None),
        (u"TextToDot", u"Text → TextDot", py("markup/TextToDot.py"),
         (u"DotToPanelText", u"TextDot → text in the top-right corner of the panel (INK)", py("markup/DotToPanelText.py"))),
        (u"TextToCurves", u"Text → curves for nesting (like Explode, but mirrored / upside-down text stays readable, as on screen)", py("markup/TextToCurves.py"), None),
        (u"Legend", u"Label legend (P, F, Off, C, Z, Can, R, RC, RD, RO, T, A–A): only those present in the drawing, as text at the click point; Lang IT / EN / UA", py("markup/Legend.py"), None),
        (u"Panel Page", u"A4 sheet for the selection: one new Layout P<n>, detail Top, like Zoom Selected on the whole selection", py("markup/PanelPage.py"), None),
    ]),
]

LANG = "IT"

# Italian toolbar: English name in GROUPS → (name, tooltip); groups → (tab name, description)
IT = {
    u"Sizes": (u"Misure", u"Misure e ingombri"),
    u"BBoxSize": (u"Ingombro", u"Riquadro di ingombro nel CPlane con le misure XYZ"),
    u"BBoxCenterLines": (u"Assi ingombro", u"Riquadro piatto nel CPlane + due linee di mezzeria"),
    u"LabelSizes": (u"Scrivi misure", u"Scrive la misura dentro ogni curva chiusa"),
    u"Rect 1340": (u"Rett 1340", u"Rettangolo 1340 × 6658 centrato sul CPlane"),
    u"Curves": (u"Curve", u"Modifica delle curve"),
    u"SplitByAngle": (u"Dividi ad angolo", u"Divide le curve negli angoli più acuti della soglia"),
    u"SmoothCorners": (u"Arrotonda angoli", u"Arrotonda gli angoli della polilinea più acuti della soglia"),
    u"CrvToPolyline": (u"Curva → polilinea", u"Converte le curve in polilinee (layer mantenuto)"),
    u"TrimEnds": (u"Accorcia estremi", u"Taglia le estremità della curva di una distanza data"),
    u"KeepEnds": (u"Tieni estremi", u"Toglie il centro della curva, tiene le estremità di lunghezza data"),
    u"TrimOutside": (u"Taglia fuori", u"Taglia tutto ciò che è fuori dal contorno del pannello"),
    u"ExactConnection": (u"Punto di contatto", u"Punto di contatto su una curva a una lunghezza data"),
    u"MidLine": (u"Linea di mezzo", u"Linea dal punto medio di una curva al punto medio di un'altra"),
    u"OffsetRigid": (u"Offset rigido", u"Copia della curva senza cambiarne la forma, spostata lungo la normale nel punto cliccato"),
    u"Analysis": (u"Analisi", u"Analisi di pannelli e taglio"),
    u"SmallClosed": (u"Chiuse piccole", u"Seleziona le curve chiuse più piccole dell'area minima di taglio"),
    u"CutRisks": (u"Rischi taglio", u"Segna i punti di taglio a rischio (geometria invariata)"),
    u"RecommendTabs": (u"Ponticelli consigliati", u"Seleziona i contorni che hanno bisogno di ponticelli (piccoli o stretti)"),
    u"CutTabs": (u"Ponticelli", u"Aggiunge i ponticelli ai contorni di taglio, in modo interattivo"),
    u"Cut": (u"Taglio", u"Preparazione al taglio"),
    u"PreparePanelCut": (u"Prepara taglio", u"Pannelli → un contorno esterno su CUT, linee interne su INT/INK"),
    u"SplitToMaterial": (u"Dividi per tessuto", u"Divide i pannelli alla larghezza del tessuto: cucitura 1 cm, pezzi spostati di 50"),
    u"CurveOverlap": (u"Sovrapposizioni", u"Elimina i doppioni esatti (SelDup), seleziona la curva più corta di ogni coppia sovrapposta (tra le selezionate o tutte)"),
    u"Parts": (u"Pezzi", u"Creazione dei pezzi (fasce, rinforzi…) nel layer Parts"),
    u"Panels": (u"Pannelli", u"Pannelli → copia in Parts::Panels numerata P1, P2… (testo dentro + TextDot)"),
    u"Strips": (u"Fasce", u"Fasce sotto le linee selezionate: larghezza W, lunghezza = lunghezza di ogni curva; etichetta F<w>  l=… (cm)"),
    u"ZipCover": (u"CopriZip", u"Copri zip: lato del pannello (da angolo ad angolo) + offset W verso l'esterno, estremità lungo i lati vicini; etichetta Off<w> (cm, offset); EditPanel=Yes — cresce il contorno stesso del pannello"),
    u"Join Corner": (u"UnisciAng", u"Unisce due curve aperte in un angolo, lato a lato: clic vicino all'angolo → i lati (da angolo ad angolo) estesi / tagliati fino all'intersezione, le estremità oltre tolte, una curva"),
    u"Merge Outline": (u"UnisciContorno", u"Unisce un pannello chiuso e una curva che insieme racchiudono un'area in un solo pannello lungo il contorno esterno; il vecchio lato rimasto dentro diventa una curva aperta"),
    u"ZipStops": (u"Zip", u"Cerniere (Z<n>) e canaline (Can<n>, opzione Type): clic sui lati dei pannelli / curve; fermi a L rientrati di Trim, tacca alle giunzioni, numero — tutto dal lato del testo"),
    u"ZipList": (u"ZList", u"Tabella d'ordine: cerniere (lato più lungo, cm × pz) e canaline (lunghezza intera); CSV accanto al .3dm + appunti"),
    u"Mark Reinf": (u"MarkR", u"Rinforzo senza pezzo: seleziona le etichette (Off / C…), il pannello si trova da solo → aggiunge R<w> (cm), lunghezza del lato in UserText"),
    u"RList": (u"Lista R", u"Tabella dei rinforzi R: lato + Plus (10 cm), totali per larghezza; CSV accanto al .3dm + appunti"),
    u"Bordino": (u"Bord", u"Bordino B<w>: lato del pannello (da angolo ad angolo) → striscia diritta a parte W (3,5 cm; 4,5 rinforzato) × lato + Plus (6 cm) accanto al pannello + copia Up (10000) in alto, etichetta B<w> (cm); sul pannello solo B<w> dopo Z<n> R<w>"),
    u"Pettola": (u"Pett", u"Pettola Pt<w>: come il Bordino, solo più larga (6–14 cm e più, default 10): striscia diritta a parte W × lato + Plus (6 cm) accanto al pannello + copia Up (10000) in alto, etichetta Pt<w> (cm); sul pannello solo Pt<w> dopo Z<n> R<w> B<w>"),
    u"Reinf D": (u"RfD", u"Rinforzo a D (RD<n>) alla fine di una tasca: angolo alto → angolo basso, larghezza W, prolungamento R"),
    u"Reinf O": (u"RfO", u"Rinforzo a O (RO<n>) alla fine di una tasca a tutta larghezza: centro nell'angolo alto → clic su una linea, r = distanza + Plus (5 cm), solo dentro il pannello"),
    u"Reinf Strip": (u"Rf", u"Rinforzo R<w> sul pannello, senza piega: lato (da angolo ad angolo) + offset W (6 cm) verso l'interno, estremità lungo i lati vicini; tagliato più lungo di Plus (10 cm), rifilato dopo la cucitura; etichetta R<w>  l=… (cm)"),
    u"Tube Pockets": (u"Tasche", u"Tasche per tubo T<n>: pannello → clic vicino a un lato, W centrata sul lato, altezza H, restringimento Trim, senza margine di cucitura, orlo alle estremità Hem, tacca al centro, Rigid — offset rigido"),
    u"Update Pockets": (u"Aggiorna tasche", u"Aggiorna le tasche T esistenti: nuovi H / Trim / Hem / Notch / Rigid sul posto, stesso numero (cambia solo quello che hai cambiato)"),
    u"Part Panel": (u"N. pannello", u"Numero del pannello sui pezzi: seleziona i pezzi (finestra) → \" P<n>\" aggiunto all'etichetta di ogni pezzo; il pannello si trova dalla posizione del pezzo (pezzo in alto → riportato giù; Bordino — dal suo lato)"),
    u"Layout": (u"Piazzamento", u"Piazzamento per il taglio: pezzi con contorno, battute, tacche al centro e codici in fila, in <layer>::Layout; il resto resta sullo schema"),
    u"Layout Stack": (u"Piazza in pila", u"Strisce che si possono girare lungo il drittofilo — opzioni Rinforzo / Bordini: copie sul piazzamento lungo X del CPlane, in pila in giù dal clic a distanza Gap (0 — a contatto), le più lunghe prima; <layer>::Layout; Hide=Yes — i pezzi piazzati vengono nascosti"),
    u"Pack Strips": (u"Compatta strisce", u"Strisce già lungo X del CPlane (Piazza in pila, Fasce) spostate in un blocco compatto: righe lunghe quanto la striscia più lunga, entro la larghezza del rotolo Width (le righe si allungano se serve), un blocco per ogni larghezza, Gap tra le strisce (0 — a contatto); Invio — sul posto"),
    u"Markup": (u"Segni", u"Segni su INK"),
    u"Crosses": (u"Croci", u"Punti → croci o cerchi"),
    u"SewingPoints": (u"Battute", u"Battute: pannelli / curve + clic vicino a un lato → punti dal centro del lato (da angolo ad angolo) in entrambe le direzioni con passo Step (200 mm) + tacca centrale (Tick 10 mm, verso l'interno del pannello); Parts::SewingMarks"),
    u"SewPoints GH": (u"Battute GH", u"Battute (Grasshopper Player, versione vecchia)"),
    u"Linetype 400,2": (u"Linea 400,2", u"Assegna il tipo di linea 400,2 alle curve selezionate"),
    u"TextStyles": (u"Stili testo", u"Crea / aggiorna gli stili di testo PAT 2.5–40 mm per cartamodelli 1:1"),
    u"TextToDot": (u"Testo → Dot", u"Testo → TextDot"),
    u"DotToPanelText": (u"Dot → testo", u"TextDot → testo nell'angolo in alto a destra del pannello (INK)"),
    u"TextToCurves": (u"Testo → curve", u"Testo → curve per il nesting (come Explode, ma il testo specchiato / capovolto resta leggibile, come a schermo)"),
    u"Legend": (u"Legenda", u"Legenda delle etichette (P, F, Off, C, Z, Can, R, RC, RD, RO, T, A–A): solo quelle presenti nel disegno, come testo nel punto cliccato; lingua IT / EN / UA"),
    u"Panel Page": (u"Pagina pannello", u"Foglio A4 per la selezione: un nuovo Layout P<n>, vista Top, come Zoom Selected su tutta la selezione"),
}


def tr(name, tip):
    """(shown name, tooltip) in LANG; name stays the key of the GUIDs."""
    return IT[name] if LANG == "IT" else (name, tip)


def gid(*parts):
    return str(uuid.uuid5(NS, "/".join(parts)))


def loc(tag, value, pad):
    return u"%s<%s>\n%s  <locale_1033>%s</locale_1033>\n%s</%s>\n" % (pad, tag, pad, escape(value), pad, tag)


macros = []


def macro(key, text, tip, script):
    g = gid("macro", key)
    macros.append(u'    <macro_item guid="%s">\n%s%s%s    <script>%s</script>\n    </macro_item>\n' % (
        g, loc("text", text, "      "), loc("tooltip", tip, "      "), loc("button_text", text, "      "), escape(script)))
    return g


def item(key, text, left, right=None):
    out = u'      <tool_bar_item guid="%s">\n%s        <left_macro_id>%s</left_macro_id>\n' % (gid("item", key), loc("text", text, "        "), left)
    if right:
        out += u"        <right_macro_id>%s</right_macro_id>\n" % right
    return out + u"      </tool_bar_item>\n"


def toolbar(key, name, items):
    return u'    <tool_bar guid="%s">\n%s%s    </tool_bar>\n' % (gid("toolbar", key), loc("text", name, "      "), u"".join(items))


bars = []
for group, group_tip, buttons in GROUPS:
    items = []
    for text, tip, script, right in buttons:
        name, tip = tr(text, tip)
        l = macro(text, name, tip, script)
        r = macro(right[0], *tr(right[0], right[1]) + (right[2],)) if right else None
        items.append(item(group + "/" + text, name, l, r))
    bars.append(toolbar(group, tr(group, group_tip)[0], items))

rui = u'''<?xml version="1.0" encoding="utf-8"?>
<RhinoUI major_ver="3" minor_ver="0" guid="%s" localize="False" default_language_id="1033" dpi_scale="100">
  <extend_rhino_menus />
  <menus />
  <tool_bar_groups />
  <tool_bars>
%s  </tool_bars>
  <macros>
%s  </macros>
  <bitmaps>
    <small_bitmap item_width="16" item_height="16" />
    <normal_bitmap item_width="24" item_height="24" />
    <large_bitmap item_width="32" item_height="32" />
  </bitmaps>
  <scripts />
</RhinoUI>
''' % (gid("file"), u"".join(bars), u"".join(macros))

if __name__ == "__main__":
    # Check: every .py/.gh in the macros exists on disk.
    import re
    missing = [p for p in re.findall(r'"([^"]+\.(?:py|gh))"', rui) if not os.path.isfile(p)]
    assert not missing, "Missing files: %s" % missing
    out = os.path.join(ROOT, "Scripts.rui")
    with open(out, "wb") as f:
        f.write(rui.encode("utf-8"))
    print("OK -> %s" % out)
