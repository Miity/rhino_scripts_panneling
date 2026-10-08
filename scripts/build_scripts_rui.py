# -*- coding: utf-8 -*-
"""Builds Scripts.rui (project root): 6 separate toolbars (Sizes / Curves / Analysis / Cut / Parts / Markup)
shown as tabs in one Rhino panel.
Run with plain python3 outside Rhino: python3 scripts/build_scripts_rui.py
Build with Rhino closed; Rhino picks up the changes after a restart. How to connect it the first time — README.md.
To add a script — add a line to GROUPS and rerun this file.
GUIDs are deterministic (uuid5 of the name), so regenerating does not break the toolbar layout.
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
        (u"Strips", u"Strips under the selected lines: height H, length = length of each curve; label S<n>", py("parts/StripsFromCurves.py"), None),
        (u"ZipCover", u"Zip cover / seam allowance: panel edge (corner to corner) + offset W outward, ends along the neighbouring edges; Points=No — ZC W, Points=Yes — seam points, SA W; EditPanel=Yes — the panel contour itself grows", py("parts/ZipCover.py"), None),
        (u"Join Corner", u"Join any two open curves at a corner, edge to edge: click near the corner → edges (corner to corner) extended / trimmed to their intersection, ends beyond removed, one curve", py("parts/JoinCorner.py"), None),
        (u"ZipStops", u"Zips (Z<n>) and tracks (Trk<n>, option Type): stops Trim in from the line ends + number, tick at junctions; lines untouched", py("parts/ZipStops.py"), None),
        (u"ZipList", u"Order table: zips (longer side, cm × pcs) and tracks (full length); CSV next to the .3dm + clipboard", py("parts/ZipList.py"), None),
        (u"Mark Reinf", u"Reinforcement strip without a part: select labels (ZC / SA…), the panel is found automatically → append R<H>, edge length in UserText", py("parts/MarkReinf.py"), None),
        (u"RList", u"Reinforcement strip table: edge + 5 cm on each side, totals by H; CSV next to the .3dm + clipboard", py("parts/RList.py"), None),
        (u"Reinf Circle", u"Corner reinforcement — circle of radius R trimmed by the sides of the corner (panel)", py("parts/ReinfCircle.py"), None),
        (u"Reinf D", u"D reinforcement at the end of a pocket: top corner → bottom corner, width W, extension R", py("parts/ReinfD.py"), None),
        (u"Reinf O", u"O reinforcement at the end of a full-width pocket: centre at the top corner → click on a line, R = distance + Plus (5 cm), only inside the panel, seam allowance SA (1 cm) along the panel edge", py("parts/ReinfO.py"), None),
        (u"Reinf Bord", u"Reinforced border: like ZipCover, but inward: edge (corner to corner) + offset H (6 / 10 cm) into the panel, ends along the neighbouring edges, JoinCorner joins at corners; SA — allowance on the inner edge (default 0)", py("parts/ReinfBord.py"), None),
        (u"Tube Pockets", u"Tube pockets: panel → click near an edge, W centred on the edge, height H, narrowing Trim, allowance SA, hem allowance at the ends Hem, centre mark, Rigid — rigid offset", py("parts/TubePockets.py"), None),
        (u"Update Pockets", u"Update existing TP pockets: new H / Trim / SA / Hem / Notch / Rigid in place, same number (only what you changed changes)", py("parts/UpdateTubePockets.py"), None),
        (u"Layout", u"Lay out parts: copies in a row from the click point, in <layer>::Layout; originals stay as markup", py("parts/LayoutParts.py"), None),
    ]),
    (u"Markup", u"Markup on INK", [
        (u"Crosses", u"Points → crosses or circles", py("markup/PointsToCrosses.py"), None),
        (u"SewingPoints", u"Seam points: curve centre + equal step both ways", py("markup/sewing_points.py"),
         (u"SewPoints GH", u"Seam points (Grasshopper Player, old version)", GH_SEW)),
        (u"Linetype 400,2", u"Assign linetype 400,2 to the selected curves", py("markup/line_type.py"), None),
        (u"TextStyles", u"Create/update PAT 2.5–40 mm text styles for 1:1 patterns", py("markup/PatternTextStyles.py"), None),
        (u"TextToDot", u"Text → TextDot", py("markup/TextToDot.py"),
         (u"DotToPanelText", u"TextDot → text in the top-right corner of the panel (INK)", py("markup/DotToPanelText.py"))),
        (u"TextToCurves", u"Text → curves for nesting (like Explode, but mirrored / upside-down text stays readable, as on screen)", py("markup/TextToCurves.py"), None),
        (u"Legend", u"Label legend (P, S, ZC, SA, Z, Trk, RC, TP, A–A): only those present in the drawing, as text at the click point", py("markup/Legend.py"), None),
        (u"Panel Page", u"A4 sheet for the selection: one new Layout P<n>, detail Top, like Zoom Selected on the whole selection", py("markup/PanelPage.py"), None),
    ]),
]


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
        l = macro(text, text, tip, script)
        r = macro(right[0], right[0], right[1], right[2]) if right else None
        items.append(item(group + "/" + text, text, l, r))
    bars.append(toolbar(group, group, items))

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
