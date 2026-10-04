# -*- coding: utf-8 -*-
"""Позначає криву як блискавку (zip): короткі поперечні стопи на початку і в кінці.
Стопи центровані на кривій, лежать у площині CPlane, у шарі Parts::Zip і згруповані з кривою."""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

LAYER = "Parts::Zip"


def stop_lines(crv, size, normal):
    lines = []
    for t in (crv.Domain.T0, crv.Domain.T1):
        pt = crv.PointAt(t)
        side = Rhino.Geometry.Vector3d.CrossProduct(crv.TangentAt(t), normal)
        side.Unitize()
        side *= size / 2.0
        lines.append(Rhino.Geometry.Line(pt - side, pt + side))
    return lines


def main():
    ids = rs.GetObjects("Виберіть криві блискавок", rs.filter.curve, preselect=True)
    if not ids:
        return
    # 1 см у одиницях документа
    cm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Centimeters, sc.doc.ModelUnitSystem)
    size = rs.GetReal("Довжина стопа", sc.sticky.get("zip_stop_size", cm), 0.0)
    if not size:
        return
    sc.sticky["zip_stop_size"] = size
    normal = rs.ViewCPlane().ZAxis

    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Zip", parent="Parts")

    rs.EnableRedraw(False)
    for oid in ids:
        crv = rs.coercecurve(oid)
        if crv.IsClosed:
            continue  # у замкненої кривої немає кінців
        group = rs.AddGroup()
        rs.AddObjectToGroup(oid, group)
        for ln in stop_lines(crv, size, normal):
            lid = rs.AddLine(ln.From, ln.To)
            rs.ObjectLayer(lid, LAYER)
            rs.AddObjectToGroup(lid, group)
    rs.EnableRedraw(True)


if __name__ == "__main__":
    main()
