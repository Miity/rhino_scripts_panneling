# -*- coding: utf-8 -*-
"""Плаский bounding box у площині CPlane + дві центральні лінії.
Після побудови вибираєте лінії, які залишити; решта видаляється."""
import rhinoscriptsyntax as rs


def main():
    ids = rs.GetObjects("Виберіть об'єкти для bounding box", preselect=True)
    if not ids:
        return
    plane = rs.ViewCPlane()
    box = rs.BoundingBox(ids, plane)
    if not box:
        return
    p0, p1, p2, p3 = box[:4]  # нижній прямокутник у площині CPlane
    mid = lambda a, b: (a + b) / 2

    rs.EnableRedraw(False)
    lines = [rs.AddLine(p0, p1), rs.AddLine(p1, p2), rs.AddLine(p2, p3), rs.AddLine(p3, p0),
             rs.AddLine(mid(p0, p1), mid(p3, p2)),   # центральна поперек X
             rs.AddLine(mid(p1, p2), mid(p0, p3))]   # центральна поперек Y
    lines = [l for l in lines if l]  # вироджені (нульової довжини) лінії не створюються
    rs.UnselectAllObjects()
    rs.EnableRedraw(True)

    allowed = set(lines)
    keep = rs.GetObjects("Виберіть лінії, які залишити (Enter — підтвердити)", rs.filter.curve,
                         custom_filter=lambda obj, geo, idx: obj.Id in allowed)
    keep = set(keep or [])  # нічого не вибрано / Esc — видаляються всі
    rs.DeleteObjects([l for l in lines if l not in keep])
    rs.SelectObjects(list(keep))


if __name__ == "__main__":
    main()
