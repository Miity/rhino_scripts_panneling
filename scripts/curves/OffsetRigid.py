# -*- coding: utf-8 -*-
"""Rigid offset: a copy of the curve without changing its shape, moved by distance D along the normal
at the clicked point on the curve (in the CPlane). Side — by click, as in Offset.
Unlike Offset, the arc radius does not change; exactly D only at the clicked point."""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

KEY = "OffsetRigid.dist"


def shift(crv, t, z, pick, dist):
    """Move vector: normal to the curve at t (z × tangent), towards pick, of length dist."""
    p = crv.PointAt(t)
    n = Rhino.Geometry.Vector3d.CrossProduct(z, crv.TangentAt(t))
    if not n.Unitize():
        return None
    d = pick - p
    if d.X * n.X + d.Y * n.Y + d.Z * n.Z < 0:
        n.Reverse()
    return n * dist


HELP = u"""Options:
  Distance — move distance along the normal at the clicked point"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    res = rs.GetCurveObject(u"Click the curve at the point whose normal to move along")
    if not res:
        return
    cid, t = res[0], res[4]
    crv = rs.coercecurve(cid)
    z = sc.doc.Views.ActiveView.ActiveViewport.ConstructionPlane().ZAxis
    base = crv.PointAt(t)
    if shift(crv, t, z, base + z, 1.0) is None:
        print(u"The tangent at this point is perpendicular to the CPlane — normal undefined")
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
        gp.SetCommandPrompt(u"Click the side to move to")
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
    copy = rs.CopyObject(cid, v)  # same layer and attributes
    rs.RemoveObjectFromAllGroups(copy)  # as Offset: the copy is not in the original's groups
    rs.UnselectAllObjects()
    rs.SelectObject(copy)
    print(u"Moved {:.2f} along the normal".format(dist.CurrentValue))
    sc.doc.Views.Redraw()


if __name__ == "__main__":
    main()
