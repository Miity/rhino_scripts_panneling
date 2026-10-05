# -*- coding: utf-8 -*-
"""Середня лінія: дві криві → лінія від середини (за довжиною) першої до середини другої."""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc


def mid_point(crv):
    ok, t = crv.NormalizedLengthParameter(0.5)
    return crv.PointAt(t) if ok else None


def main():
    ids = rs.GetObjects("Виберіть дві криві", rs.filter.curve, preselect=True, minimum_count=2, maximum_count=2)
    if not ids:
        return
    p0, p1 = [mid_point(rs.coercecurve(i)) for i in ids]
    if p0 is None or p1 is None or p0.DistanceTo(p1) <= sc.doc.ModelAbsoluteTolerance:
        print("Не вдалося побудувати лінію (середини збігаються або крива некоректна)")
        return
    line_id = sc.doc.Objects.AddLine(Rhino.Geometry.Line(p0, p1))
    rs.UnselectAllObjects()
    rs.SelectObject(line_id)
    print("Середня лінія: {:.2f}".format(p0.DistanceTo(p1)))
    sc.doc.Views.Redraw()


if __name__ == "__main__":
    main()
