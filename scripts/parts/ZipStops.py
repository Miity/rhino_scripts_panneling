# -*- coding: utf-8 -*-
"""Позначає блискавки (zip) і каналіну (canalina / guida).
Одна блискавка = усі її лінії на всіх панелях (обидві сторони тасьми, сторона може бути розбита на кілька панелей).
Каналіна — одна сторона, теж може бути розбита на кілька панелей. Тип — опція Type на виборі ліній
(Zip / Can, запам'ятовується): блискавки Z1, Z2… у шарі Parts::Zip, каналіна Can1, Can2… у Parts::Canalina.
Вибір ліній повторюється — Enter завершує.
Кожна лінія переноситься у свій шар і отримує номер: UserText Zip + текст над серединою,
уздовж лінії; стиль тексту — опція Style (запам'ятовується, за замовчуванням PAT 10 mm).
На кінцях кожної лінії — поперечні стопи (центровані, у площині CPlane). Якщо сторона розбита
(блискавка — ліній 3+, каналіна — 2+), клік біля кінця-стику (де вона переходить на іншу панель)
міняє стоп на риску вдвічі коротшу; ще клік — назад.
Лінія, її стопи і текст — одна група (на кожну лінію своя: лінії лежать на різних панелях).
Нумерація продовжується з найбільшого номера в шарі (окремо Z і Can); вже позначені лінії пропускаються.
Далі — етап переносу: клік по блискавці переносить її номер на інший бік кривої (зверху ↔ знизу),
якщо налазить на інший текст; Enter — готово. Enter на виборі кривих — одразу до переносу.
Таблиця довжин для замовлення — parts/ZipList.py."""
import os
import re
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.DocObjects import TextHorizontalAlignment, TextVerticalAlignment
from Rhino.Geometry import Plane, Vector3d

# вибір стилю і PAT-стилі — з scripts/markup/DotToPanelText.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
import DotToPanelText as D

# тип → (префікс, шар, у запиті, з якої кількості ліній питати про стики)
TYPES = {"Zip": ("Z", "Parts::Zip", u"блискавки (обидві сторони)", 3),
         "Can": ("Can", "Parts::Canalina", u"каналіни (canalina / guida)", 2)}
KEY = "Zip"  # ключ UserText з номером (Z<n> або Can<n>)
STYLE = "ZipStops.style"
KIND = "ZipStops.kind"


def stop_lines(crv, size, normal):
    lines = []
    for t in (crv.Domain.T0, crv.Domain.T1):
        pt = crv.PointAt(t)
        side = Vector3d.CrossProduct(crv.TangentAt(t), normal)
        side.Unitize()
        side *= size / 2.0
        lines.append(Rhino.Geometry.Line(pt - side, pt + side))
    return lines


def label_plane(crv, normal, gap):
    """Площина тексту: над серединою кривої на gap, вісь X уздовж кривої (читається зліва направо)."""
    ok, t = crv.LengthParameter(crv.GetLength() / 2.0)
    t = t if ok else crv.Domain.Mid
    u = crv.TangentAt(t)
    if u.X < -1e-9 or (abs(u.X) < 1e-9 and u.Y < 0):
        u = -u
    v = Vector3d.CrossProduct(normal, u)
    return Plane(crv.PointAt(t) + v * gap, u, v)


def is_zip(rhino_object, geometry, component_index):
    return bool(rhino_object.Attributes.GetUserString(KEY))


def flip_label(doc, oid):
    """Номер блискавки на інший бік кривої: дзеркало відносно кривої, вирівнювання Bottom ↔ Top."""
    name = rs.GetUserText(oid, KEY)
    crv = rs.coercecurve(oid)
    for g in rs.ObjectGroups(oid) or []:
        for t in rs.ObjectsByGroup(g) or []:
            if rs.IsText(t) and rs.TextObjectText(t) == name:
                te = rs.coercegeometry(t)
                mid = label_plane(crv, te.Plane.ZAxis, 0)
                y = mid.YAxis * ((te.Plane.Origin - mid.Origin) * mid.YAxis)
                pl = te.Plane
                pl.Origin = mid.Origin - y
                te.Plane = pl
                te.TextVerticalAlignment = (TextVerticalAlignment.Top if y * mid.YAxis > 0
                                            else TextVerticalAlignment.Bottom)
                doc.Objects.Replace(t, te)
                return True
    return False


def flip_stage(doc):
    while True:
        oid = rs.GetObject(u"Клікни блискавку, щоб перенести її номер на інший бік (Enter — готово)",
                           rs.filter.curve, custom_filter=is_zip)
        if not oid:
            return
        if not flip_label(doc, oid):
            print(u"%s: текст номера не знайдено в групі кривої" % rs.GetUserText(oid, KEY))
        doc.Views.Redraw()


def next_number(kind):
    """Наступний номер після найбільшого <префікс><n> у шарі типу (UserText кривої, текст або TextDot старих позначок)."""
    prefix, layer = TYPES[kind][:2]
    nums = [0]
    for o in (rs.ObjectsByLayer(layer) or []) if rs.IsLayer(layer) else []:
        s = rs.GetUserText(o, KEY) or (rs.TextObjectText(o) if rs.IsText(o) else
                                       rs.TextDotText(o) if rs.IsTextDot(o) else "")
        m = re.match(prefix + r"(\d+)$", s or "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


def get_lines(kind, nums, last):
    """Вибір ліній однієї блискавки / каналіни з опцією Type. Повертає (id або None, тип)."""
    go = Rhino.Input.Custom.GetObject()
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Curve
    go.EnablePreSelect(not nums, True)  # передвибір — лише для першої
    while True:
        prefix, _, what, _ = TYPES[kind]
        n = nums.get(kind) or next_number(kind)
        go.SetCommandPrompt(u"%s%d: виберіть усі лінії %s (Enter — %s)" % (prefix, n, what, last))
        go.ClearCommandOptions()
        go.AddOption("Type", kind)
        res = go.GetMultiple(1, 0)
        if res == Rhino.Input.GetResult.Option:
            kind = "Can" if kind == "Zip" else "Zip"
            sc.sticky[KIND] = kind
            go.EnablePreSelect(False, True)
            continue
        if res == Rhino.Input.GetResult.Object:
            return [go.Object(k).ObjectId for k in range(go.ObjectCount)], kind
        return None, kind


def ask_size(doc, size, style):
    """Довжина стопа з опцією Style. Повертає (довжина або None, стиль)."""
    while True:
        gn = Rhino.Input.Custom.GetNumber()
        gn.SetCommandPrompt(u"Довжина стопа (стиль тексту: %s)" % style)
        gn.SetDefaultNumber(size)
        gn.SetLowerLimit(0.0, True)
        opt = gn.AddOption("Style")
        res = gn.Get()
        if res == Rhino.Input.GetResult.Option and gn.OptionIndex() == opt:
            style = D.pick_style(doc, style)
            continue
        if res == Rhino.Input.GetResult.Number:
            return gn.Number(), style
        return None, style


def mark_line(doc, oid, crv, name, size, normal, ds, gap, attrs):
    """Лінія → шар attrs з номером, стопи на кінцях, текст; одна група. Повертає id стопів [початок, кінець]."""
    # ModifyAttributes, а не rs.ObjectLayer + rs.SetUserText: так шар і мітку відкочує Undo
    a = rs.coercerhinoobject(oid).Attributes.Duplicate()
    a.LayerIndex = attrs.LayerIndex
    a.SetUserString(KEY, name)
    doc.Objects.ModifyAttributes(oid, a, True)
    stops = [doc.Objects.AddLine(ln, attrs) for ln in stop_lines(crv, size, normal)]
    te = Rhino.Geometry.TextEntity.Create(name, label_plane(crv, normal, gap), ds, False, 0, 0)
    te.TextHorizontalAlignment = TextHorizontalAlignment.Center
    te.TextVerticalAlignment = TextVerticalAlignment.Bottom
    rs.AddObjectsToGroup([oid] + stops + [doc.Objects.AddText(te, attrs)], rs.AddGroup())
    return stops


def junction_stage(doc, name, lines, size, normal):
    """lines = [(крива, [id стопа на початку, на кінці])]. Клік біля кінця: стоп ↔ риска на стику."""
    notch = set()
    while True:
        pt = rs.GetPoint(u"%s: клікни біля стику — кінця, де вона переходить на іншу панель (Enter — готово)" % name)
        if pt is None:
            return
        d, i, e = min((pt.DistanceTo(c.PointAt((c.Domain.T0, c.Domain.T1)[e])), i, e)
                      for i, (c, _) in enumerate(lines) for e in (0, 1))
        crv, stops = lines[i]
        notch ^= set([(i, e)])
        ln = stop_lines(crv, size / 2.0 if (i, e) in notch else size, normal)[e]
        doc.Objects.Replace(stops[e], ln)
        doc.Views.Redraw()


HELP = u"""Опції:
  Type — Zip: блискавка (обидві сторони, Z<n>); Can: каналіна (одна сторона, Can<n>)
  Style — стиль тексту номера"""  # друкується на старті — видно під полями опцій


def main():
    print(HELP)
    doc = sc.doc
    nums = {}  # тип → наступний номер у цьому запуску
    kind = sc.sticky.get(KIND, "Zip")
    ids, kind = get_lines(kind, nums, u"лише перенести номери")
    if not ids:
        flip_stage(doc)
        return
    D.pts.ensure_styles(doc)
    style = sc.sticky.get(STYLE)
    if not style or doc.DimStyles.FindName(style) is None:
        style = D.pts.style_name(10)
    # 1 см у одиницях документа
    cm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Centimeters, doc.ModelUnitSystem)
    size, style = ask_size(doc, sc.sticky.get("zip_stop_size", cm), style)
    sc.sticky[STYLE] = style
    if not size:
        return
    sc.sticky["zip_stop_size"] = size
    ds = doc.DimStyles.FindName(style)
    gap = 0.5 * ds.TextHeight * ds.DimensionScale
    normal = rs.ViewCPlane().ZAxis
    layers = [t[1] for t in TYPES.values()]

    while ids:
        prefix, layer, _, junctions = TYPES[kind]
        todo = [i for i in ids if not rs.IsCurveClosed(i)  # у замкненої кривої немає кінців
                and not (rs.GetUserText(i, KEY) and rs.ObjectLayer(i) in layers)]  # вже позначена
        if len(todo) < len(ids):
            print(u"Замкнені або вже позначені, пропущено: %d" % (len(ids) - len(todo)))
        if todo:
            if not rs.IsLayer("Parts"):
                rs.AddLayer("Parts")
            if not rs.IsLayer(layer):
                rs.AddLayer(layer.split("::")[1], parent="Parts")
            attrs = doc.CreateDefaultAttributes()
            attrs.LayerIndex = doc.Layers.FindByFullPath(layer, -1)
            n = nums.get(kind) or next_number(kind)
            nums[kind] = n + 1
            name = prefix + str(n)
            lines = []
            for oid in todo:
                crv = rs.coercecurve(oid)
                lines.append((crv, mark_line(doc, oid, crv, name, size, normal, ds, gap, attrs)))
            rs.UnselectAllObjects()
            doc.Views.Redraw()
            if len(lines) >= junctions:  # сторона розбита на кілька панелей
                junction_stage(doc, name, lines, size, normal)
            print(u"%s: ліній %d" % (name, len(lines)))
        rs.UnselectAllObjects()
        ids, kind = get_lines(kind, nums, u"готово")
    flip_stage(doc)


if __name__ == "__main__":
    main()
