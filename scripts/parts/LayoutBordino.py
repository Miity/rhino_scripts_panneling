# -*- coding: utf-8 -*-
"""Bordini on the canvas, turned along the grain: before nesting with a fixed fabric direction.
Select objects (a window over the panels / parts up is fine) — only the bordini are taken (Parts::Bordino parts, the
copy up; the markup on the panel is skipped). Each one is copied as LayoutParts does (contour + label code "B3.5 P4",
sublayer Parts::Bordino::Layout, UserText LayoutOf), turned so its long side runs along CPlane X (label reading left to
right), and stacked touching, one under another, from the click point (top-left corner) — as the fascia strips,
longest first. Already laid out bordini (a copy with LayoutOf exists) are skipped; to lay out again — delete the copy.
Layout then skips them too.
"""
import math
import os
import sys

import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Plane, TextEntity, Transform

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("LayoutParts", None)  # Rhino keeps modules from the first run for the session
from LayoutParts import KEY, is_part, outer, own, parts, place

LAYERS = ("Parts::Bordino",)  # parts that may be turned along the grain


def bordini(doc, ids):
    """Bordino parts in the selection not laid out yet: ([[objects]], number already laid out)."""
    copied = set(o.Attributes.GetUserString(KEY) for o in doc.Objects)
    units = [[doc.Objects.FindId(i) for i in p] for p in parts(ids)]
    found = [u for u in units if is_part(doc, u)
             and any(doc.Layers[o.Attributes.LayerIndex].FullPath in LAYERS for o in u)]
    todo = [u for u in found if not any(str(o.Id) in copied for o in u)]
    return todo, len(found) - len(todo)


def stack(doc, units, plane, start):
    """Copies of the parts turned along plane X, stacked down from start (top-left corner), touching, longest first."""
    ok, x, y = plane.ClosestParameter(start)
    to_plane = Transform.PlaneToPlane(plane, Plane.WorldXY)  # bbox in CPlane coordinates
    rows = []
    for u in units:
        c = outer(u)
        s = max(c.DuplicateSegments() or [c], key=lambda s: s.GetLength())
        d = s.PointAtEnd - s.PointAtStart
        rot = Transform.Rotation(-math.atan2(d * plane.YAxis, d * plane.XAxis), plane.ZAxis, plane.Origin)
        rows.append((c.GetBoundingBox(to_plane * rot), rot, u))
    rows.sort(key=lambda r: r[0].Min.X - r[0].Max.X)
    new = []
    for bb, rot, u in rows:
        xf = Transform.Translation(plane.XAxis * (x - bb.Min.X) + plane.YAxis * (y - bb.Max.Y)) * rot
        geo = own(doc, u)
        for _, g in geo:
            g.Transform(xf)
            if isinstance(g, TextEntity) and g.Plane.XAxis * plane.XAxis < 0:  # reads right to left — turn it over
                g.Transform(Transform.Rotation(math.pi, plane.ZAxis, g.Plane.Origin))
        new += place(doc, geo)
        y -= bb.Max.Y - bb.Min.Y
    return new


def main():
    doc = sc.doc
    ids = rs.GetObjects(u"Select objects with bordini (window over the panels / parts up)", preselect=True)
    if not ids:
        return
    todo, skipped = bordini(doc, ids)
    if not todo:
        print(u"No bordini to lay out in the selection (already laid out: %d)" % skipped)
        return
    start = rs.GetPoint(u"Point to stack the bordini from (top-left corner)")
    if not start:
        return
    stack(doc, todo, rs.ViewCPlane(), start)
    doc.Views.Redraw()
    print(u"Bordini stacked: %d; skipped (already laid out): %d" % (len(todo), skipped))


if __name__ == "__main__":
    main()
