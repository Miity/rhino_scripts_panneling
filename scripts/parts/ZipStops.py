# -*- coding: utf-8 -*-
"""Позначає криву як блискавку (zip): короткі поперечні стопи на початку і в кінці.
Крива переноситься в шар Parts::Zip і отримує номер Z<n> (UserText Zip + TextDot посередині);
стопи центровані на кривій, лежать у площині CPlane. Крива, стопи і TextDot — одна група.
Нумерація продовжується з найбільшого Z<n> у шарі; вже позначені криві пропускаються.
Таблиця довжин для замовлення — parts/ZipList.py."""
import re

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

LAYER = "Parts::Zip"
PREFIX = "Z"
KEY = "Zip"  # ключ UserText з номером блискавки


def stop_lines(crv, size, normal):
    lines = []
    for t in (crv.Domain.T0, crv.Domain.T1):
        pt = crv.PointAt(t)
        side = Rhino.Geometry.Vector3d.CrossProduct(crv.TangentAt(t), normal)
        side.Unitize()
        side *= size / 2.0
        lines.append(Rhino.Geometry.Line(pt - side, pt + side))
    return lines


def next_number():
    """Наступний номер після найбільшого Z<n> у шарі (UserText кривої або TextDot)."""
    nums = [0]
    for o in rs.ObjectsByLayer(LAYER) or []:
        m = re.match(PREFIX + r"(\d+)$", rs.GetUserText(o, KEY) or (rs.TextDotText(o) if rs.IsTextDot(o) else "") or "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


def main():
    ids = rs.GetObjects("Виберіть криві блискавок", rs.filter.curve, preselect=True)
    if not ids:
        return
    # 1 см у одиницях документа
    cm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Centimeters, sc.doc.ModelUnitSystem)
    size = rs.GetReal("Довжина стопа", sc.sticky.get("zip_stop_size", cm), 0.0)
    if not size:
        return
    sc.sticky["zip_stop_size"] = size
    normal = rs.ViewCPlane().ZAxis

    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Zip", parent="Parts")
    layer_index = sc.doc.Layers.FindByFullPath(LAYER, -1)

    rs.EnableRedraw(False)
    n = next_number()
    skipped = 0
    for oid in ids:
        crv = rs.coercecurve(oid)
        if crv.IsClosed:
            continue  # у замкненої кривої немає кінців
        if rs.GetUserText(oid, KEY) and rs.ObjectLayer(oid) == LAYER:
            skipped += 1  # вже блискавка — не дублюємо стопи
            continue
        name = PREFIX + str(n)
        n += 1
        # ModifyAttributes, а не rs.ObjectLayer + rs.SetUserText: так шар і мітку відкочує Undo
        attrs = rs.coercerhinoobject(oid).Attributes.Duplicate()
        attrs.LayerIndex = layer_index
        attrs.SetUserString(KEY, name)
        sc.doc.Objects.ModifyAttributes(oid, attrs, True)
        group = rs.AddGroup()
        rs.AddObjectToGroup(oid, group)
        for ln in stop_lines(crv, size, normal):
            lid = rs.AddLine(ln.From, ln.To)
            rs.ObjectLayer(lid, LAYER)
            rs.AddObjectToGroup(lid, group)
        ok, t = crv.LengthParameter(crv.GetLength() / 2.0)
        did = rs.AddTextDot(name, crv.PointAt(t) if ok else crv.PointAtStart)
        rs.ObjectLayer(did, LAYER)
        rs.AddObjectToGroup(did, group)
    rs.EnableRedraw(True)
    if skipped:
        print("Вже позначені, пропущено: %d" % skipped)


if __name__ == "__main__":
    main()
