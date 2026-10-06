# -*- coding: utf-8 -*-
"""Lay out parts for cutting.
Select finished parts (Parts::…). A part is a whole group (even if only part of it is selected),
an object without a group is a separate part. A copy of each part with its labels is placed in a row from the click point
(bottom-left corner of the first part; along CPlane, with a gap), in sublayer <part layer>::Layout, in its own new
group. The originals stay in place as markup of where to sew. Enter instead of a click — continue the row
to the right of already laid out parts. Already laid out parts are skipped
(the copy remembers the original in UserText LayoutOf); to lay out again — delete the copy.
"""
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Transform

STICKY = "LayoutParts"
SUB = "Layout"
KEY = "LayoutOf"  # copy's UserText: original id


def parts(ids):
    """List of parts: each is a list of ids (the whole top-level group or one object)."""
    seen, out = set(), []
    for i in ids:
        if str(i) in seen:
            continue
        g = rs.ObjectTopGroup(i)
        members = rs.ObjectsByGroup(g) if g else [i]
        seen.update(str(m) for m in members)
        out.append(members)
    return out


def box(ids, plane):
    """(x0, y0, x1, y1) in plane coordinates."""
    p = rs.BoundingBox(ids, plane, False)
    return min(q.X for q in p), min(q.Y for q in p), max(q.X for q in p), max(q.Y for q in p)


def layout_layer(doc, index):
    """Sublayer Layout under the original's layer (same colour)."""
    lay = doc.Layers[index]
    full = lay.FullPath + "::" + SUB
    if not rs.IsLayer(full):
        rs.AddLayer(SUB, lay.Color, parent=lay.FullPath)
    return doc.Layers.FindByFullPath(full, -1)


def layout(doc, ids, gap, plane, start=None):
    """Copies the parts in a row from point start (None — continue the row of laid out parts). Returns (copy ids, number of parts skipped)."""
    copied = {}  # original id → copy id
    for o in doc.Objects:
        src = o.Attributes.GetUserString(KEY)
        if src:
            copied[src] = o.Id
    all_parts = parts(ids)
    # copies are not laid out again, nor an original that already has a copy
    todo = [p for p in all_parts if not any(str(i) in copied or rs.GetUserText(i, KEY) for i in p)]
    if not todo:
        return [], len(all_parts)
    if start is not None:
        ok, x, y = plane.ClosestParameter(start)
    elif copied:  # continue the row to the right of already laid out parts
        x0, y0, x1, y1 = box(list(copied.values()), plane)
        x, y = x1 + gap, y0
    else:
        return [], 0
    # ponytail: one endless row; if it gets too long — wrap to a new row by the work area width.
    new = []
    for p in todo:
        bx = box(p, plane)
        xf = Transform.Translation(plane.XAxis * (x - bx[0]) + plane.YAxis * (y - bx[1]))
        gi = doc.Groups.Add() if len(p) > 1 else -1
        for i in p:
            o = doc.Objects.FindId(i)
            geo = o.Geometry.Duplicate()
            geo.Transform(xf)
            a = o.Attributes.Duplicate()
            a.RemoveFromAllGroups()
            if gi >= 0:
                a.AddToGroup(gi)
            a.LayerIndex = layout_layer(doc, o.Attributes.LayerIndex)
            a.SetUserString(KEY, str(i))
            new.append(doc.Objects.Add(geo, a))
        x += bx[2] - bx[0] + gap
    return new, len(all_parts) - len(todo)


def main():
    ids = rs.GetObjects(u"Select parts to lay out (groups are taken whole)", preselect=True)
    if not ids:
        return
    gap = rs.GetReal(u"Gap between parts", sc.sticky.get(STICKY, 10.0), 0)
    if gap is None:
        return
    sc.sticky[STICKY] = gap
    start = rs.GetPoint(u"Click where to start the row (Enter — continue the row of laid out parts)")
    new, skipped = layout(sc.doc, ids, gap, rs.ViewCPlane(), start)
    if start is None and not new and not skipped:
        print(u"Nothing laid out yet — click a point")
        return
    sc.doc.Views.Redraw()
    print(u"Objects laid out: %d; parts skipped (already laid out or copies): %d" % (len(new), skipped))


if __name__ == "__main__":
    main()
