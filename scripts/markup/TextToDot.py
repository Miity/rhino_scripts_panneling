# -*- coding: utf-8 -*-
"""Converts selected text objects to TextDots.
The dot is placed at the text centre, attributes (layer, colour etc.) are copied, the original is deleted.
"""
import rhinoscriptsyntax as rs


def text_to_dot():
    ids = rs.GetObjects(u"Select text to convert to dots", rs.filter.annotation, preselect=True)
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
    print(u"Converted to dots: {}".format(len(dots)))


if __name__ == "__main__":
    text_to_dot()
