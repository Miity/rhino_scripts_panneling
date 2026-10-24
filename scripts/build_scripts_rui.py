# -*- coding: utf-8 -*-
"""Builds Scripts.rui (project root): 7 toolbars (Sizes / Curves / Parts / Pattern / Markup / Cut / Analysis) and one
toolbar group "Scripts" holding all 7 as tabs (one tick in Window → Toolbars shows them all).
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



# (group = tab name, group description, [(button, tooltip, macro, (right button, tooltip, macro) | None)])
# Order = the order of work: tabs and buttons in the order they are used on a cover.
# Button names: no spaces (CamelCase); tooltip: one short sentence, details — README / HELP.
GROUPS = [
    (u"Sizes", u"Sizes and extents", [
        (u"BBoxSize", u"Bounding box in the CPlane with XYZ sizes", py("sizes/BoundingBoxWithSize_Rhino8_CPlane.py"),
         (u"BBoxCenterLines", u"Flat box in the CPlane + two centre lines", py("sizes/BoundingBoxCenterLines.py"))),
        (u"LabelSizes", u"Size label inside each closed curve", py("sizes/LabelClosedCurveSizes.py"), None),
        (u"Rect1340", u"Rectangle 1340 × 6658 centred at a click", py("sizes/draw_centered_rectangle.py"), None),
    ]),
    (u"Curves", u"Curve editing", [
        (u"SplitByAngle", u"Split curves at corners sharper than the angle", py("curves/SplitCrvByAngle.py"),
         (u"SmoothCorners", u"Round polyline corners sharper than the angle", py("curves/smooth_corners.py"))),
        (u"CrvToPolyline", u"Curves → polylines, layer kept", py("curves/CrvToPolyline.py"), None),
        (u"TrimEnds", u"Trim curve ends by a distance", py("curves/TrimCrvEnds.py"),
         (u"KeepEnds", u"Keep only the curve ends of a given length", py("curves/KeepCrvEnds.py"))),
        (u"TrimOutside", u"Delete everything outside the panel contour", py("curves/TrimOutsidePanel.py"), None),
        (u"ExactConnection", u"Point on a curve at a fixed length from a point", py("curves/find_exact_connection.py"), None),
        (u"MidLine", u"Line between the midpoints of two curves", py("curves/MidLine.py"), None),
        (u"OffsetRigid", u"Copy of a curve moved along the normal, shape unchanged", py("curves/OffsetRigid.py"), None),
    ]),
    (u"Parts", u"Parts (strips, reinforcements…) in the Parts layer", [
        (u"Panels", u"Number panels P1, P2… in Parts::Panels", py("parts/Panels.py"), None),
        (u"JoinCorner", u"Join two open curves at a corner: click near it", py("parts/JoinCorner.py"), None),
        (u"MergeOutline", u"Panel + curve enclosing an area → one panel by the outer line", py("parts/MergeOutline.py"), None),
        (u"ZipCover", u"Zip cover Off<w>: panel edge + offset outward", py("parts/ZipCover.py"), None),
        (u"ZipStops", u"Zips Z<n> and tracks Can<n>: click panel edges", py("parts/ZipStops.py"),
         (u"ZipList", u"Zip and track order table → CSV + clipboard", py("parts/ZipList.py"))),
        (u"ReinfStrip", u"Rinforzo R<w>: strip inward along a panel edge", py("parts/Rinforzo.py"), None),
        (u"MarkReinf", u"Append R<w> to the selected labels, no part", py("parts/MarkReinf.py"), None),
        (u"RList", u"Reinforcement strip table → CSV + clipboard", py("parts/RList.py"), None),
        (u"ReinfD", u"D reinforcement RD<n> at a pocket end", py("parts/ReinfD.py"), None),
        (u"ReinfO", u"O reinforcement RO<n> at a full-width pocket", py("parts/ReinfO.py"), None),
        (u"Bordino", u"Bordino B<w>: separate strip folded over an edge", py("parts/Bordino.py"),
         (u"Pettola", u"Pettola Pt<w>: like Bordino, wider", py("parts/Pettola.py"))),
        (u"TubePockets", u"Tube pockets T<n> on a panel edge", py("parts/TubePockets.py"),
         (u"UpdatePockets", u"Change H / Trim / Hem of existing pockets", py("parts/UpdateTubePockets.py"))),
        (u"Strips", u"Fascia strips F<w> under the selected curves", py("parts/StripsFromCurves.py"), None),
        (u"PartPanel", u"Append the panel number P<n> to part labels", py("parts/PartPanel.py"), None),
        (u"Layout", u"Parts in a row on the cutting canvas", py("parts/LayoutParts.py"),
         (u"LayoutStack", u"Rinforzo / bordino strips stacked along X", py("parts/LayoutStack.py"))),
        (u"PackStrips", u"Pack straight strips into a block within the roll width", py("parts/PackStrips.py"), None),
    ]),
    (u"Pattern", u"Pattern tools after PatternSmith: seam allowance, notches", [
        (u"SquishJoined", u"Squish every surface, pieces joined along common sides", py("pattern/SquishJoined.py"),
         None),
        (u"SquishTo", u"3D marks onto the squished 2D surface", py("pattern/SquishTo.py"),
         (u"MarksTo2D", u"3D marks onto a 2D panel already worked on", py("pattern/MarksTo2D.py"))),
        (u"Break", u"Break point on a panel contour; Type=Ripresa", py("pattern/Break.py"), None),
        (u"Seams", u"Seam allowance: click an edge, Width", py("pattern/Seams.py"), None),
        (u"Notches", u"Notch points on the sew line", py("pattern/Notches.py"),
         (u"MatchNotches", u"Compare the lengths of two sewn edges", py("pattern/MatchNotches.py"))),
        (u"ConvertNotches", u"Notch points → pen / knife notches", py("pattern/ConvertNotches.py"), None),
    ]),
    (u"Markup", u"Markup on INK", [
        (u"Crosses", u"Points / small circles → crosses or circles", py("markup/PointsToCrosses.py"), None),
        (u"Linetype400,2", u"Linetype 400,2 on the selected curves", py("markup/line_type.py"), None),
        (u"TextStyles", u"Create / update the PAT text styles", py("markup/PatternTextStyles.py"), None),
        (u"TextToDot", u"Text → TextDot", py("markup/TextToDot.py"),
         (u"DotToPanelText", u"TextDot → text in the panel corner (INK)", py("markup/DotToPanelText.py"))),
        (u"TextToCurves", u"Text → curves for nesting, readable when mirrored", py("markup/TextToCurves.py"), None),
        (u"Legend", u"Legend of the label codes in the drawing", py("markup/Legend.py"), None),
        (u"PanelPage", u"A4 Layout page for the selection", py("markup/PanelPage.py"), None),
    ]),
    (u"Cut", u"Cut preparation", [
        (u"CurveOverlap", u"Delete duplicates, select the shorter of overlapping curves", py("cut/sel_curve_overlap.py"), None),
        (u"SplitToMaterial", u"Split panels to the fabric width: 1 cm seam, A–A pairs", py("cut/SplitPanelsToMaterial.py"), None),
        (u"PreparePanelCut", u"Panels → outer contour on CUT, inner lines on INT / INK", py("cut/PreparePanelCut.py"), None),
        (u"Preflight", u"Checks before the cutter: duplicates etc., changes nothing", py("cut/PreflightCut.py"), None),
    ]),
    (u"Analysis", u"Panel and cut analysis", [
        (u"SmallClosed", u"Select closed curves too small to cut", py("analysis/SelectSmallClosedCurves.py"), None),
        (u"CutRisks", u"Mark risky cut spots, geometry unchanged", py("analysis/CheckTangentialCutRisks.py"), None),
        (u"RecommendTabs", u"Select contours that need tabs", py("analysis/RecommendCutTabs.py"), None),
        (u"CutTabs", u"Add tabs to cut contours, click by click", py("analysis/AddCutTabs.py"), None),
        (u"Zigzags", u"Find micro zigzags: straighten or skip each", py("analysis/FindZigzags.py"), None),
    ]),
]

LANG = "IT"

# Italian toolbar: English name in GROUPS → (name, tooltip); groups → (tab name, description)
IT = {
    u"Sizes": (u"Misure", u"Misure e ingombri"),
    u"BBoxSize": (u"Ingombro", u"Ingombro nel CPlane con le misure XYZ"),
    u"BBoxCenterLines": (u"AssiIngombro", u"Riquadro piatto nel CPlane + due mezzerie"),
    u"LabelSizes": (u"ScriviMisure", u"Misura dentro ogni curva chiusa"),
    u"Rect1340": (u"Rett1340", u"Rettangolo 1340 × 6658 centrato nel clic"),
    u"Curves": (u"Curve", u"Modifica delle curve"),
    u"SplitByAngle": (u"DividiAdAngolo", u"Divide le curve negli angoli più acuti della soglia"),
    u"SmoothCorners": (u"ArrotondaAngoli", u"Arrotonda gli angoli più acuti della soglia"),
    u"CrvToPolyline": (u"Curva→Polilinea", u"Curve → polilinee, layer mantenuto"),
    u"TrimEnds": (u"AccorciaEstremi", u"Accorcia le estremità di una distanza"),
    u"KeepEnds": (u"TieniEstremi", u"Tiene solo le estremità di una lunghezza data"),
    u"TrimOutside": (u"TagliaFuori", u"Taglia tutto fuori dal contorno del pannello"),
    u"ExactConnection": (u"PuntoDiContatto", u"Punto su una curva a lunghezza fissa da un punto"),
    u"MidLine": (u"LineaDiMezzo", u"Linea tra i punti medi di due curve"),
    u"OffsetRigid": (u"OffsetRigido", u"Copia della curva spostata lungo la normale, forma invariata"),
    u"Parts": (u"Pezzi", u"Pezzi (fasce, rinforzi…) nel layer Parts"),
    u"Panels": (u"Pannelli", u"Numera i pannelli P1, P2… in Parts::Panels"),
    u"JoinCorner": (u"UnisciAng", u"Unisce due curve aperte in un angolo: clic vicino"),
    u"MergeOutline": (u"UnisciContorno", u"Pannello + curva che chiude un'area → un pannello lungo il contorno esterno"),
    u"ZipCover": (u"CopriZip", u"Copri zip Off<w>: lato del pannello + offset verso l'esterno"),
    u"ZipStops": (u"Zip", u"Cerniere Z<n> e canaline Can<n>: clic sui lati"),
    u"ZipList": (u"ZList", u"Tabella d'ordine cerniere e canaline → CSV + appunti"),
    u"ReinfStrip": (u"Rf", u"Rinforzo R<w>: striscia verso l'interno lungo un lato"),
    u"MarkReinf": (u"MarkR", u"Aggiunge R<w> alle etichette selezionate, senza pezzo"),
    u"RList": (u"ListaR", u"Tabella dei rinforzi R → CSV + appunti"),
    u"ReinfD": (u"RfD", u"Rinforzo a D RD<n> alla fine di una tasca"),
    u"ReinfO": (u"RfO", u"Rinforzo a O RO<n> a una tasca a tutta larghezza"),
    u"Bordino": (u"Bord", u"Bordino B<w>: striscia a parte ripiegata sul lato"),
    u"Pettola": (u"Pett", u"Pettola Pt<w>: come il Bordino, più larga"),
    u"TubePockets": (u"Tasche", u"Tasche per tubo T<n> su un lato del pannello"),
    u"UpdatePockets": (u"AggiornaTasche", u"Cambia H / Trim / Hem delle tasche esistenti"),
    u"Strips": (u"Fasce", u"Fasce F<w> sotto le curve selezionate"),
    u"PartPanel": (u"NPannello", u"Aggiunge il numero del pannello P<n> alle etichette dei pezzi"),
    u"Layout": (u"Piazzamento", u"Pezzi in fila sul piazzamento per il taglio"),
    u"LayoutStack": (u"PiazzaInPila", u"Strisce rinforzo / bordino in pila lungo X"),
    u"PackStrips": (u"CompattaStrisce", u"Compatta le strisce dritte in un blocco entro la larghezza del rotolo"),
    u"Pattern": (u"Modello", u"Strumenti del cartamodello: margini di cucitura, tacche"),
    u"SquishJoined": (u"SquishUniti", u"Squish di ogni superficie, pezzi uniti lungo i lati in comune"),
    u"SquishTo": (u"SquishTo", u"Segni 3D sulla superficie 2D fatta con Squish"),
    u"MarksTo2D": (u"SegniIn2D", u"Segni 3D su un pannello 2D già lavorato"),
    u"Break": (u"Spezza", u"Punto di interruzione sul contorno; Type=Ripresa"),
    u"Seams": (u"Margini", u"Margine di cucitura: clic su un lato, Width"),
    u"Notches": (u"Tacche", u"Tacche (punti) sulla linea di cucitura"),
    u"MatchNotches": (u"AbbinaTacche", u"Confronta le lunghezze di due lati cuciti insieme"),
    u"ConvertNotches": (u"ConvertiTacche", u"Tacche → segni di penna / lama"),
    u"Markup": (u"Segni", u"Segni su INK"),
    u"Crosses": (u"Croci", u"Punti / cerchietti → croci o cerchi"),
    u"Linetype400,2": (u"Linea400,2", u"Tipo di linea 400,2 sulle curve selezionate"),
    u"TextStyles": (u"StiliTesto", u"Crea / aggiorna gli stili di testo PAT"),
    u"TextToDot": (u"Testo→Dot", u"Testo → TextDot"),
    u"DotToPanelText": (u"Dot→Testo", u"TextDot → testo nell'angolo del pannello (INK)"),
    u"TextToCurves": (u"Testo→Curve", u"Testo → curve per il nesting, leggibile anche specchiato"),
    u"Legend": (u"Legenda", u"Legenda dei codici presenti nel disegno"),
    u"PanelPage": (u"PaginaPannello", u"Pagina Layout A4 per la selezione"),
    u"Cut": (u"Taglio", u"Preparazione al taglio"),
    u"CurveOverlap": (u"Sovrapposizioni", u"Elimina i doppioni, seleziona la più corta delle sovrapposte"),
    u"SplitToMaterial": (u"DividiPerTessuto", u"Divide i pannelli alla larghezza del tessuto: cucitura 1 cm, coppie A–A"),
    u"PreparePanelCut": (u"PreparaTaglio", u"Pannelli → contorno su CUT, linee interne su INT / INK"),
    u"Preflight": (u"ControlloTaglio", u"Controlli prima del taglio: doppioni ecc., non cambia nulla"),
    u"Analysis": (u"Analisi", u"Analisi di pannelli e taglio"),
    u"SmallClosed": (u"ChiusePiccole", u"Seleziona le curve chiuse troppo piccole da tagliare"),
    u"CutRisks": (u"RischiTaglio", u"Segna i punti di taglio a rischio, geometria invariata"),
    u"RecommendTabs": (u"PonticelliConsigliati", u"Seleziona i contorni che hanno bisogno di ponticelli"),
    u"CutTabs": (u"Ponticelli", u"Aggiunge ponticelli ai contorni, clic per clic"),
    u"Zigzags": (u"Microzigzag", u"Trova i microzigzag: raddrizza o salta"),
}

def tr(name, tip):
    """(shown name, tooltip) in LANG; name stays the key of the GUIDs. The tooltip always reads "name: explanation"."""
    name, tip = IT[name] if LANG == "IT" else (name, tip)
    return name, u"%s: %s" % (name, tip)


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
    out = u'      <tool_bar_item guid="%s">\n%s        <left_macro_id>%s</left_macro_id>\n' % (
        gid("item", key), loc("text", text, "        "), left)
    if right:
        out += u"        <right_macro_id>%s</right_macro_id>\n" % right
    return out + u"      </tool_bar_item>\n"


def toolbar(key, name, items):
    return u'    <tool_bar guid="%s">\n%s%s    </tool_bar>\n' % (gid("toolbar", key), loc("text", name, "      "), u"".join(items))


def bar_group(names):
    """the toolbar group "Scripts": every toolbar of GROUPS as a tab, the first one active"""
    items = [u'      <tool_bar_group_item guid="%s" major_version="1" minor_version="1">\n%s'
             u'        <tool_bar_id>%s</tool_bar_id>\n      </tool_bar_group_item>\n' % (
                 gid("group_item", key), loc("text", name, "        "), gid("toolbar", key)) for key, name in names]
    return (u'    <tool_bar_group guid="%s" active_tool_bar_group="%s" single_file="False" hide_single_tab="False">\n'
            u'%s%s      <dock_bar_info dpi_scale="100" docking="True" visible="True" floating="True" '
            u'dock_location="top" />\n    </tool_bar_group>\n') % (
        gid("group"), gid("group_item", names[0][0]), loc("text", u"Scripts", "      "), u"".join(items))


def build(groups):
    """RUI text with one toolbar per group + the group of them all."""
    del macros[:]
    bars = []
    for group, group_tip, buttons in groups:
        items = []
        for text, tip, script, right in buttons:
            name, tip = tr(text, tip)
            l = macro(text, name, tip, script)
            r = macro(right[0], *tr(right[0], right[1]) + (right[2],)) if right else None
            items.append(item(group + "/" + text, name, l, r))
        bars.append(toolbar(group, tr(group, group_tip)[0], items))
    names = [(group, tr(group, group_tip)[0]) for group, group_tip, _ in groups]
    return u'''<?xml version="1.0" encoding="utf-8"?>
<RhinoUI major_ver="3" minor_ver="0" guid="%s" localize="False" default_language_id="1033" dpi_scale="100">
  <extend_rhino_menus />
  <menus />
  <tool_bar_groups>
%s  </tool_bar_groups>
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
''' % (gid("file"), bar_group(names), u"".join(bars), u"".join(macros))


if __name__ == "__main__":
    import re
    rui = build(GROUPS)
    # Check: every .py/.gh in the macros exists on disk.
    missing = [p for p in re.findall(r'"([^"]+\.(?:py|gh))"', rui) if not os.path.isfile(p)]
    assert not missing, "Missing files: %s" % missing
    out = os.path.join(ROOT, "Scripts.rui")
    with open(out, "wb") as f:
        f.write(rui.encode("utf-8"))
    print("OK -> %s" % out)
