# -*- coding: utf-8 -*-
"""Text → curves for the nesting program (instead of Explode).

Rhino draws mirrored / upside-down text (after Mirror, rotation, another CPlane)
"Draw forward" — on screen it reads correctly. Explode ignores this and gives mirrored
letters; CreateCurves respects it — the curves lie exactly like the text on screen in the Top view.
The original is deleted, the curves take its attributes (layer, colour, groups);
text without a group → letters in a new group.
"""
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc


def text_curves(te):
    """Text curves as it is seen on screen (with Draw forward, unlike Explode)."""
    style = te.GetDimensionStyle(sc.doc.DimStyles.FindId(te.DimensionStyleId))
    return list(te.CreateCurves(style, True) or [])  # True — single-line (PAT) open curves


def main():
    ids = rs.GetObjects(u"Select text → curves", rs.filter.annotation, preselect=True)
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
    print(u"Texts → curves: {}".format(n_text))


if __name__ == "__main__":
    main()
