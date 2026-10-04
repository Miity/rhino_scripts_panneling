# -*- coding: utf-8 -*-
"""Розкласти деталі для розкрою.
Вибираєш готові деталі (Parts::…). Деталь — це група цілком (навіть якщо вибрано лише її частину),
об'єкт без групи — окрема деталь. Копія кожної деталі з підписами лягає в ряд від точки кліку
(лівий нижній кут першої деталі; по CPlane, з відступом), у підшар <шар деталі>::Layout, у свою нову
групу. Оригінали лишаються на місці як розмітка, де нашивати. Enter замість кліку — продовжити ряд
праворуч від уже розкладених. Уже розкладені деталі пропускаються
(копія пам'ятає оригінал в UserText LayoutOf); щоб розкласти наново — видали копію.
"""
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Transform

STICKY = "LayoutParts"
SUB = "Layout"
KEY = "LayoutOf"  # UserText копії: id оригіналу


def parts(ids):
    """Список деталей: кожна — список id (уся верхня група або один об'єкт)."""
    seen, out = set(), []
    for i in ids:
        if str(i) in seen:
            continue
        g = rs.ObjectTopGroup(i)
        members = rs.ObjectsByGroup(g) if g else [i]
        seen.update(str(m) for m in members)
        out.append(members)
    return out


def box(ids, plane):
    """(x0, y0, x1, y1) у координатах plane."""
    p = rs.BoundingBox(ids, plane, False)
    return min(q.X for q in p), min(q.Y for q in p), max(q.X for q in p), max(q.Y for q in p)


def layout_layer(doc, index):
    """Підшар Layout під шаром оригіналу (той самий колір)."""
    lay = doc.Layers[index]
    full = lay.FullPath + "::" + SUB
    if not rs.IsLayer(full):
        rs.AddLayer(SUB, lay.Color, parent=lay.FullPath)
    return doc.Layers.FindByFullPath(full, -1)


def layout(doc, ids, gap, plane, start=None):
    """Копіює деталі в ряд від точки start (None — продовжити ряд розкладених). Повертає (id копій, скільки деталей пропущено)."""
    copied = {}  # id оригіналу → id копії
    for o in doc.Objects:
        src = o.Attributes.GetUserString(KEY)
        if src:
            copied[src] = o.Id
    all_parts = parts(ids)
    # копії не розкладаємо вдруге, і оригінал, що вже має копію, теж
    todo = [p for p in all_parts if not any(str(i) in copied or rs.GetUserText(i, KEY) for i in p)]
    if not todo:
        return [], len(all_parts)
    if start is not None:
        ok, x, y = plane.ClosestParameter(start)
    elif copied:  # продовжити ряд праворуч від уже розкладених
        x0, y0, x1, y1 = box(list(copied.values()), plane)
        x, y = x1 + gap, y0
    else:
        return [], 0
    # ponytail: один нескінченний ряд; якщо стане задовгим — переносити на новий ряд за шириною робочої зони.
    new = []
    for p in todo:
        bx = box(p, plane)
        xf = Transform.Translation(plane.XAxis * (x - bx[0]) + plane.YAxis * (y - bx[1]))
        gi = doc.Groups.Add() if len(p) > 1 else -1
        for i in p:
            o = doc.Objects.FindId(i)
            geo = o.Geometry.Duplicate()
            geo.Transform(xf)
            a = o.Attributes.Duplicate()
            a.RemoveFromAllGroups()
            if gi >= 0:
                a.AddToGroup(gi)
            a.LayerIndex = layout_layer(doc, o.Attributes.LayerIndex)
            a.SetUserString(KEY, str(i))
            new.append(doc.Objects.Add(geo, a))
        x += bx[2] - bx[0] + gap
    return new, len(all_parts) - len(todo)


def main():
    ids = rs.GetObjects(u"Виберіть деталі для розкладки (групи беруться цілком)", preselect=True)
    if not ids:
        return
    gap = rs.GetReal(u"Відступ між деталями", sc.sticky.get(STICKY, 10.0), 0)
    if gap is None:
        return
    sc.sticky[STICKY] = gap
    start = rs.GetPoint(u"Клікни, звідки класти ряд (Enter — продовжити ряд розкладених)")
    new, skipped = layout(sc.doc, ids, gap, rs.ViewCPlane(), start)
    if start is None and not new and not skipped:
        print(u"Ще нічого не розкладено — клікни точку")
        return
    sc.doc.Views.Redraw()
    print(u"Розкладено об'єктів: %d; пропущено деталей (уже розкладені або копії): %d" % (len(new), skipped))


if __name__ == "__main__":
    main()
