# -*- coding: utf-8 -*-
"""Linetype '400,2' (dash 400 mm, gap 2 mm) on the selected curves, set by object (not by layer).
A document without it (opened straight from DXF, no template) gets the linetype made first."""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

NAME = "400,2"
PATTERN = ((400.0, True), (2.0, False))  # mm: (length, dash or gap)


def ensure(doc):
    """Index of the linetype NAME in the document, made if missing (-1 if it could not be made)."""
    for lt in doc.Linetypes:
        if not lt.IsDeleted and lt.Name == NAME:
            return lt.LinetypeIndex
    lt = Rhino.DocObjects.Linetype()
    lt.Name = NAME
    for length, dash in PATTERN:
        lt.AppendSegment(length, dash)
    return doc.Linetypes.Add(lt)


def main():
    ids = rs.GetObjects("Select curves for linetype '{0}'".format(NAME), rs.filter.curve, preselect=True)
    if not ids:
        return
    index = ensure(sc.doc)
    if index < 0:
        print("Could not make linetype '{0}'.".format(NAME))
        return
    rs.EnableRedraw(False)
    for object_id in ids:
        obj = sc.doc.Objects.FindId(object_id)
        obj.Attributes.LinetypeIndex = index
        obj.Attributes.LinetypeSource = Rhino.DocObjects.ObjectLinetypeSource.LinetypeFromObject
        obj.CommitChanges()
    rs.EnableRedraw(True)
    sc.doc.Views.Redraw()
    print("Linetype '{0}' set on {1} curves.".format(NAME, len(ids)))


if __name__ == "__main__":
    main()
