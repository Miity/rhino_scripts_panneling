# -*- coding: utf-8 -*-
"""Конвертує виділені текстові об'єкти в TextDot.
Dot ставиться в центр тексту, атрибути (шар, колір тощо) копіюються, оригінал видаляється.
"""
import rhinoscriptsyntax as rs


def text_to_dot():
    ids = rs.GetObjects(u"Виберіть текст для конвертації в dot", rs.filter.annotation, preselect=True)
    if not ids:
        return

    rs.EnableRedraw(False)
    dots = []
    for obj_id in ids:
        if not rs.IsText(obj_id):
            continue
        bbox = rs.BoundingBox(obj_id)
        center = (bbox[0] + bbox[6]) / 2
        dot = rs.AddTextDot(rs.TextObjectText(obj_id), center)
        if dot:
            rs.MatchObjectAttributes(dot, obj_id)
            rs.DeleteObject(obj_id)
            dots.append(dot)
    rs.EnableRedraw(True)

    if dots:
        rs.SelectObjects(dots)
    print(u"Конвертовано в dot: {}".format(len(dots)))


if __name__ == "__main__":
    text_to_dot()
