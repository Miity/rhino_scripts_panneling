# -*- coding: utf-8 -*-
"""Жорсткий офсет: копія кривої без зміни форми, зсунута на відстань D по нормалі
в точці кліку на кривій (у площині CPlane). Сторона — кліком, як в Offset.
На відміну від Offset радіус арки не змінюється; рівно D лише в точці кліку."""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

KEY = "OffsetRigid.dist"


def shift(crv, t, z, pick, dist):
    """Вектор зсуву: нормаль до кривої в t (z × дотична), у бік pick, довжиною dist."""
    p = crv.PointAt(t)
    n = Rhino.Geometry.Vector3d.CrossProduct(z, crv.TangentAt(t))
    if not n.Unitize():
        return None
    d = pick - p
    if d.X * n.X + d.Y * n.Y + d.Z * n.Z < 0:
        n.Reverse()
    return n * dist


def main():
    res = rs.GetCurveObject(u"Клікніть криву в точці, по нормалі в якій зсувати")
    if not res:
        return
    cid, t = res[0], res[4]
    crv = rs.coercecurve(cid)
    z = sc.doc.Views.ActiveView.ActiveViewport.ConstructionPlane().ZAxis
    base = crv.PointAt(t)
    if shift(crv, t, z, base + z, 1.0) is None:
        print(u"Дотична в цій точці перпендикулярна до CPlane — нормаль не визначена")
        return

    dist = Rhino.Input.Custom.OptionDouble(sc.sticky.get(KEY, 10.0), 0.0, 1e9)
    color = sc.doc.Layers[rs.coercerhinoobject(cid).Attributes.LayerIndex].Color

    def draw(sender, e):
        v = shift(crv, t, z, e.CurrentPoint, dist.CurrentValue)
        if v is None:
            return
        c = crv.DuplicateCurve()
        c.Translate(v)
        e.Display.DrawCurve(c, color, 2)
        e.Display.DrawLine(Rhino.Geometry.Line(base, base + v), color)

    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Клікніть сторону зсуву")
        gp.AddOptionDouble("Distance", dist)
        gp.SetBasePoint(base, True)
        gp.DynamicDraw += draw
        try:
            r = gp.Get()
            pick = gp.Point() if r == Rhino.Input.GetResult.Point else None
        finally:
            gp.DynamicDraw -= draw
            gp.Dispose()
        if r == Rhino.Input.GetResult.Option:
            continue
        if pick is None:
            return
        break

    sc.sticky[KEY] = dist.CurrentValue
    v = shift(crv, t, z, pick, dist.CurrentValue)
    copy = rs.CopyObject(cid, v)  # той самий шар і атрибути
    rs.RemoveObjectFromAllGroups(copy)  # як Offset: копія не входить у групи оригіналу
    rs.UnselectAllObjects()
    rs.SelectObject(copy)
    print(u"Зсув {:.2f} по нормалі".format(dist.CurrentValue))
    sc.doc.Views.Redraw()


if __name__ == "__main__":
    main()
