# -*- coding: utf-8 -*-
"""Будує Scripts.rui (корінь проєкту): 6 окремих тулбарів (Розміри / Криві / Аналіз / Різ / Parts / Розмітка),
що стоять вкладками в одній панелі Rhino.
Запуск звичайним python3 поза Rhino: python3 scripts/build_scripts_rui.py
Збирати при закритому Rhino; Rhino підхоплює зміни після перезапуску. Як підключити вперше — README.md.
Щоб додати скрипт — допиши рядок у GROUPS і перезапусти цей файл.
GUID-и детерміновані (uuid5 від назви), тож перегенерація не ламає розташування тулбарів.
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

# (група = назва вкладки, опис групи, [(кнопка, підказка, макрос, (права кнопка, підказка, макрос) | None)])
GROUPS = [
    (u"Розміри", u"Розміри та габарити", [
        (u"BBoxSize", u"Габаритний бокс по CPlane з підписами розмірів XYZ", py("sizes/BoundingBoxWithSize_Rhino8_CPlane.py"),
         (u"BBoxCenterLines", u"Плаский бокс по CPlane + дві центральні лінії", py("sizes/BoundingBoxCenterLines.py"))),
        (u"LabelSizes", u"Підписати розмір усередині кожної замкненої кривої", py("sizes/LabelClosedCurveSizes.py"), None),
        (u"Rect 1340", u"Прямокутник 1340 × 6658 по центру CPlane", py("sizes/draw_centered_rectangle.py"), None),
    ]),
    (u"Криві", u"Редагування кривих", [
        (u"SplitByAngle", u"Розбити криві в кутах, гостріших за поріг", py("curves/SplitCrvByAngle.py"),
         (u"SmoothCorners", u"Заокруглити кути полілайнів, гостріші за поріг", py("curves/smooth_corners.py"))),
        (u"CrvToPolyline", u"Перетворити криві на полілайни (шар зберігається)", py("curves/CrvToPolyline.py"), None),
        (u"TrimEnds", u"Обрізати кінці кривих на задану відстань", py("curves/TrimCrvEnds.py"),
         (u"KeepEnds", u"Вирізати середину кривої, лишити кінці заданої довжини", py("curves/KeepCrvEnds.py"))),
        (u"TrimOutside", u"Обрізати все, що виходить за контур панелі", py("curves/TrimOutsidePanel.py"), None),
        (u"ExactConnection", u"Точка контакту на кривій із заданою довжиною", py("curves/find_exact_connection.py"), None),
        (u"MidLine", u"Лінія від середини однієї кривої до середини іншої", py("curves/MidLine.py"), None),
        (u"OffsetRigid", u"Копія кривої без зміни форми, зсунута по нормалі в точці кліку", py("curves/OffsetRigid.py"), None),
    ]),
    (u"Аналіз", u"Аналіз панелі та різу", [
        (u"SmallClosed", u"Виділити замкнені криві, менші за мінімальну площу різу", py("analysis/SelectSmallClosedCurves.py"), None),
        (u"CutRisks", u"Позначити ризиковані місця різу (геометрія не змінюється)", py("analysis/CheckTangentialCutRisks.py"), None),
        (u"RecommendTabs", u"Виділити контури, яким потрібні перемички (малі або вузькі)", py("analysis/RecommendCutTabs.py"), None),
        (u"CutTabs", u"Інтерактивно додати перемички (tabs) на контури різу", py("analysis/AddCutTabs.py"), None),
    ]),
    (u"Різ", u"Підготовка до різу", [
        (u"PreparePanelCut", u"Панелі → один зовнішній контур на CUT, внутрішні лінії на INT/INK", py("cut/PreparePanelCut.py"), None),
        (u"SplitToMaterial", u"Обрізати панелі по ширині матеріалу: шов 1 см, шматки відсунути на 50", py("cut/SplitPanelsToMaterial.py"), None),
        (u"CurveOverlap", u"Видалити точні дублікати (SelDup), виділити коротшу криву з кожної пари, що перекриваються (серед виділених, або всі криві)", py("cut/sel_curve_overlap.py"), None),
    ]),
    (u"Parts", u"Створення частин (фаші, підсилення…) у шар Parts", [
        (u"Panels", u"Панелі → копія в Parts::Panels з номером P1, P2… (текст усередині + TextDot)", py("parts/Panels.py"), None),
        (u"Strips", u"Фаші під виділені лінії: висота H, довжина = довжина кожної кривої", py("parts/StripsFromCurves.py"), None),
        (u"CopriZip", u"Клапан над блискавкою: ребро панелі (кут–кут) + офсет W назовні, кінці по сусідніх ребрах; підпис CZ W", py("parts/CopriZip.py"), None),
        (u"Seam", u"Припуск на шов: ребро панелі (кут–кут) + офсет W назовні, кінці по сусідніх ребрах; підпис SA W; Points=Yes — ще й точки шва", py("parts/Seam.py"), None),
        (u"Join Corner", u"З'єднати дві деталі в куті (CopriZip / Seam, різні W): клік у виріз між деталями → торці геть, зовнішні краї до перетину, одна крива", py("parts/JoinCorner.py"), None),
        (u"ZipStops", u"Блискавки (Z<n>) і каналіна (Can<n>, опція Type): усі лінії на всіх панелях → Parts::Zip / Parts::Canalina, стопи на кінцях, риска на стику", py("parts/ZipStops.py"), None),
        (u"ZipList", u"Таблиця для замовлення: блискавки (довша сторона, см × шт) і каналіна (повна довжина); CSV поруч із .3dm + буфер обміну", py("parts/ZipList.py"), None),
        (u"Reinf Circle", u"Кутове підсилення — коло радіуса R, обрізане сторонами кута (панеллю)", py("parts/ReinfCircle.py"), None),
        (u"Reinf D", u"Підсилення-D під кінець кармана: верхній кут → нижній кут, ширина W, виступ R", py("parts/ReinfD.py"), None),
        (u"Reinf O", u"Підсилення-O під кінець кармана на всю ширину: центр у верхньому куті → клік на лінії, R = відстань + Plus (5 см), лише всередині панелі, припуск SA (1 см) по краю панелі", py("parts/ReinfO.py"), None),
        (u"Reinf Bord", u"Bordino rinforzato: як CopriZip, але всередину: ребро (кут–кут) + офсет H (6 / 10 см) всередину, кінці по сусідніх ребрах, JoinCorner з'єднує в куті; SA — припуск на внутрішньому краї (типово 0)", py("parts/ReinfBord.py"), None),
        (u"Tube Pockets", u"Кармани для труб: панель → клік біля ребра, W по центру ребра, висота H, звуження Trim, припуск SA, запас на підгин торців Hem, мітка центру, Rigid — жорсткий офсет", py("parts/TubePockets.py"), None),
        (u"Update Pockets", u"Оновити готові кармани TP: нові H / Trim / SA / Hem / Notch / Rigid на місці, той самий номер (змінюється лише те, що змінив)", py("parts/UpdateTubePockets.py"), None),
        (u"Layout", u"Розкласти деталі: копії в ряд від точки кліку, у <шар>::Layout; оригінали лишаються розміткою", py("parts/LayoutParts.py"), None),
    ]),
    (u"Розмітка", u"Розмітка на INK", [
        (u"Crosses", u"Точки → хрестики або кружечки", py("markup/PointsToCrosses.py"), None),
        (u"SewingPoints", u"Точки шва: центр кривої + рівний крок в обидва боки", py("markup/sewing_points.py"),
         (u"SewPoints GH", u"Точки шва (Grasshopper Player, стара версія)", GH_SEW)),
        (u"Linetype 400,2", u"Призначити тип лінії 400,2 вибраним кривим", py("markup/line_type.py"), None),
        (u"TextStyles", u"Створити/оновити стилі тексту PAT 2.5–40 mm для лекал 1:1", py("markup/PatternTextStyles.py"), None),
        (u"TextToDot", u"Текст → TextDot", py("markup/TextToDot.py"),
         (u"DotToPanelText", u"TextDot → текст у правому верхньому куті панелі (INK)", py("markup/DotToPanelText.py"))),
        (u"TextToCurves", u"Текст → криві для нестингу (як Explode, але дзеркальний / перевернутий текст лишається читабельним, як на екрані)", py("markup/TextToCurves.py"), None),
        (u"Legend", u"Легенда підписів (P, F, CZ, SA, Z, Can, RC, TP, A–A): тільки ті, що є в кресленні, текстом у точці кліку", py("markup/Legend.py"), None),
        (u"Panel Page", u"Лист A4 на виділене: один новий Layout P<n>, detail Top, як Zoom Selected на все виділене", py("markup/PanelPage.py"), None),
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
    # Перевірка: кожен .py/.gh з макросів існує на диску.
    import re
    missing = [p for p in re.findall(r'"([^"]+\.(?:py|gh))"', rui) if not os.path.isfile(p)]
    assert not missing, "Немає файлів: %s" % missing
    out = os.path.join(ROOT, "Scripts.rui")
    with open(out, "wb") as f:
        f.write(rui.encode("utf-8"))
    print("OK -> %s" % out)
