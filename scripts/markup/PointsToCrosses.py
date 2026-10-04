# -*- coding: utf-8 -*-
# Перетворює всі виділені точки на хрестики або кружечки (позначки центрів).
# Приймає: точкові об'єкти, хмари точок, текстові маркери (TextDot).
# Кожна позиція замінюється хрестиком (дві лінії, згруповані) або колом.
# Сумісність: IronPython 2.7 / CPython 3 (Rhino 8).
import rhinoscriptsyntax as rs


def collect_positions(objs):
    """Повертає список (координата, шар, id_оригіналу) з різних типів об'єктів."""
    items = []
    for obj in objs:
        if rs.IsPoint(obj):
            items.append((rs.PointCoordinates(obj), rs.ObjectLayer(obj), obj))
        elif rs.IsPointCloud(obj):
            layer = rs.ObjectLayer(obj)
            for pt in rs.PointCloudPoints(obj):
                items.append((pt, layer, obj))
        elif rs.IsTextDot(obj):
            items.append((rs.TextDotPoint(obj), rs.ObjectLayer(obj), obj))
    return items


def points_to_crosses():
    objs = rs.SelectedObjects()
    if not objs:
        objs = rs.GetObjects("Виберіть точки", preselect=True)
    if not objs:
        print("Нічого не вибрано.")
        return

    items = collect_positions(objs)
    if not items:
        rs.MessageBox("Серед вибраного немає точок / хмар точок / текстових маркерів.\n"
                      "Вибрано об'єктів: %d" % len(objs))
        return

    shape = rs.GetString("Форма позначки", "Cross", ["Cross", "Circle"])
    if shape not in ("Cross", "Circle"):
        return
    arm = rs.GetReal("Половина розміру (для кружечка — радіус), одиниці документа", 1.0, 0.001)
    if arm is None:
        return
    delete_originals = rs.GetBoolean(
        "Видалити оригінали?", [("Оригінали", "Лишити", "Видалити")], [True])
    if delete_originals is None:
        return
    delete_originals = delete_originals[0]

    made = 0
    originals = set()
    created = []
    prev_layer = rs.CurrentLayer()
    rs.EnableRedraw(False)
    try:
        for c, layer, src in items:
            if layer and rs.IsLayer(layer):
                rs.CurrentLayer(layer)
            if shape == "Circle":
                new = [rs.AddCircle(c, arm)]
            else:
                new = [rs.AddLine([c[0] - arm, c[1], c[2]], [c[0] + arm, c[1], c[2]]),
                       rs.AddLine([c[0], c[1] - arm, c[2]], [c[0], c[1] + arm, c[2]])]
                rs.AddObjectsToGroup(new, rs.AddGroup())
            if layer and rs.IsLayer(layer):
                rs.ObjectLayer(new, layer)  # шар оригіналу
            for g in rs.ObjectGroups(src) or []:  # лишаються в групах оригіналу
                rs.AddObjectsToGroup(new, g)
            created.extend(new)
            originals.add(src)
            made += 1
        if delete_originals:
            rs.DeleteObjects(list(originals))
        rs.UnselectAllObjects()
        rs.SelectObjects(created)
    finally:
        rs.CurrentLayer(prev_layer)
        rs.EnableRedraw(True)
    print("Готово: %d позначок (%s)." % (made, shape))


if __name__ == "__main__":
    points_to_crosses()
