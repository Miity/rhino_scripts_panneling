# -*- coding: utf-8 -*-
"""Text → curves for the nesting program (instead of Explode).

Rhino draws mirrored / upside-down text (after Mirror, rotation, another CPlane)
"Draw forward" — on screen it reads correctly. Explode ignores this and gives mirrored
letters; CreateCurves respects it — the curves lie exactly like the text on screen in the Top view.
The original is deleted, the curves take its attributes (layer, colour, groups);
text without a group → letters in a new group.
Each curve carries UserText `TextCurve` = the text (cut/PreflightCut checks they are on INK).
"""
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc

TAG = "TextCurve"  # UserText on every letter curve: the text it was made from


def text_curves(te):
    """Text curves as it is seen on screen (with Draw forward, unlike Explode)."""
    style = te.GetDimensionStyle(sc.doc.DimStyles.FindId(te.DimensionStyleId))
    return list(te.CreateCurves(style, True) or [])  # True — single-line (PAT) open curves


def convert(oid):
    """One text → its curves in its place (attributes kept, tagged TAG); the text deleted. [] if not a text."""
    obj = sc.doc.Objects.FindId(oid)
    te = obj.Geometry if obj else None
    if not isinstance(te, rg.TextEntity):
        return []
    crvs = text_curves(te)
    if not crvs:
        return []
    attr = obj.Attributes.Duplicate()
    attr.SetUserString(TAG, te.PlainText)
    new = [sc.doc.Objects.AddCurve(c, attr) for c in crvs]
    if attr.GroupCount == 0 and len(new) > 1:
        sc.doc.Groups.Add(new)
    sc.doc.Objects.Delete(obj, True)
    return new


def main():
    ids = rs.GetObjects(u"Select text → curves", rs.filter.annotation, preselect=True)
    if not ids:
        return

    rs.EnableRedraw(False)
    out, n_text = [], 0
    for oid in ids:
        new = convert(oid)
        if new:
            out.extend(new)
            n_text += 1
    rs.EnableRedraw(True)

    if out:
        rs.SelectObjects(out)
    print(u"Texts → curves: {}".format(n_text))


if __name__ == "__main__":
    main()
