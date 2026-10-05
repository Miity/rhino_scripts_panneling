# -*- coding: utf-8 -*-
"""Текст → криві для програми нестингу (замість Explode).

Explode бере справжню площину тексту. Rhino ж малює текст «Draw forward»: якщо площина
дивиться від камери (після Mirror, поворот на 180°, інша CPlane), він на екрані дзеркалить
його навколо центру — і текст читається. Тут робиться те саме віддзеркалення, тож криві
лежать точно як текст на екрані активного вікна. Оригінал видаляється, криві беруть
його атрибути (шар, колір, групи); текст без групи → літери в новій групі.
"""
import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc


def forward_xform(plane, bbox, view_x, view_y):
    """Дзеркало навколо центру тексту по осях, що дивляться від камери (як Draw forward)."""
    c = plane.PointAt((bbox.Min.X + bbox.Max.X) / 2.0, (bbox.Min.Y + bbox.Max.Y) / 2.0)
    xf = rg.Transform.Identity
    if plane.XAxis * view_x < 0:
        xf = rg.Transform.Mirror(c, plane.XAxis) * xf
    if plane.YAxis * view_y < 0:
        xf = rg.Transform.Mirror(c, plane.YAxis) * xf
    return xf


def text_curves(te, view_x, view_y):
    style = te.GetDimensionStyle(sc.doc.DimStyles.FindId(te.DimensionStyleId))
    crvs = list(te.CreateCurves(style, True) or [])  # True — однолінійні шрифти (PAT) відкриті
    if not crvs or not style.DrawForward:
        return crvs
    bb = rg.BoundingBox.Empty
    for c in crvs:
        bb.Union(c.GetBoundingBox(te.Plane))  # у координатах площини тексту
    xf = forward_xform(te.Plane, bb, view_x, view_y)
    for c in crvs:
        c.Transform(xf)
    return crvs


def main():
    ids = rs.GetObjects(u"Виберіть текст → криві", rs.filter.annotation, preselect=True)
    if not ids:
        return
    vp = sc.doc.Views.ActiveView.ActiveViewport
    view_x, view_y = vp.CameraX, vp.CameraY

    rs.EnableRedraw(False)
    out, n_text, n_flip = [], 0, 0
    for oid in ids:
        obj = sc.doc.Objects.FindId(oid)
        te = obj.Geometry if obj else None
        if not isinstance(te, rg.TextEntity):
            continue
        crvs = text_curves(te, view_x, view_y)
        if not crvs:
            continue
        if te.Plane.XAxis * view_x < 0 or te.Plane.YAxis * view_y < 0:
            n_flip += 1
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
    print(u"Текстів → криві: {}, з них віддзеркалено як на екрані: {}".format(n_text, n_flip))


if __name__ == "__main__":
    main()
