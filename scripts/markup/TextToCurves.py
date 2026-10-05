# -*- coding: utf-8 -*-
"""Текст → криві для програми нестингу (замість Explode).

Rhino малює дзеркальний / перевернутий текст (після Mirror, поворот, інша CPlane)
«Draw forward» — на екрані він читається. Explode цього не враховує й дає дзеркальні
літери; CreateCurves враховує — криві лежать точно як текст на екрані у виді Top.
Оригінал видаляється, криві беруть його атрибути (шар, колір, групи);
текст без групи → літери в новій групі.
"""
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc


def text_curves(te):
    """Криві тексту так, як він видний на екрані (з Draw forward, на відміну від Explode)."""
    style = te.GetDimensionStyle(sc.doc.DimStyles.FindId(te.DimensionStyleId))
    return list(te.CreateCurves(style, True) or [])  # True — однолінійні (PAT) відкриті


def main():
    ids = rs.GetObjects(u"Виберіть текст → криві", rs.filter.annotation, preselect=True)
    if not ids:
        return

    rs.EnableRedraw(False)
    out, n_text = [], 0
    for oid in ids:
        obj = sc.doc.Objects.FindId(oid)
        te = obj.Geometry if obj else None
        if not isinstance(te, rg.TextEntity):
            continue
        crvs = text_curves(te)
        if not crvs:
            continue
        attr = obj.Attributes.Duplicate()
        new = [sc.doc.Objects.AddCurve(c, attr) for c in crvs]
        if attr.GroupCount == 0 and len(new) > 1:
            sc.doc.Groups.Add(new)
        sc.doc.Objects.Delete(obj, True)
        out.extend(new)
        n_text += 1
    rs.EnableRedraw(True)

    if out:
        rs.SelectObjects(out)
    print(u"Текстів → криві: {}".format(n_text))


if __name__ == "__main__":
    main()
