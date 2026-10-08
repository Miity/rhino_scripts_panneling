# -*- coding: utf-8 -*-
"""Lay out parts for cutting — the canvas.
Select parts together with their markup (a window over the panels and over the full parts above).
A part is a group (or a single object) on a Parts::… layer with a closed curve that is not a circle,
not the markup on a panel (PartMarkup / TP_Markup). Everything else in the selection is markup and
goes to the part that contains it (or the nearest one).
The canvas gets only what the cutting needs, the rest stays on the drawing (the schema):
  - closed curves of the part (contour, holes);
  - points (seam points, seam centres), crosses (buttons) and circles (seams) from markup/PointsToCrosses;
  - labels shortened to the code: "RC3  r=4" → "RC3", "P4", "Z15", "F5", "CZ3.5" (labels without a code — not copied);
  - a seam centre tick at the middle of every markup line (zip, reinforcement, pocket): on the contour — Tick
    long into the part, inside the part — across the line. Lines shorter than 4 × Tick (stops) — no tick.
Open lines, TextDots and long labels are not copied. Copies are placed in a row from the click point
(bottom-left corner of the first part; along CPlane, with a gap), in sublayer <layer>::Layout, each part in its own group.
Enter instead of a click — continue the row to the right of already laid out parts. Already laid out parts are skipped
(the copy remembers the original in UserText LayoutOf); to lay out again — delete the copy.
"""
import re

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Line, LineCurve, Plane, PointContainment, Transform, Vector3d

STICKY = "LayoutParts"
SUB = "Layout"
KEY = "LayoutOf"  # copy's UserText: original id
MARKUP = ("PartMarkup", "TP_Markup")  # markup on the panel, not a part
CODE = re.compile(r"\s*([A-Za-z]+\d+(?:\.\d+)?)\b")  # label → code: "RC3  r=4" → "RC3", "CZ3.5 R6" → "CZ3.5"


def parts(ids):
    """List of parts: each is a list of ids (the whole top-level group or one object). A group with the markup on the
    panel and the full part up (add_part, TubePockets) — two: the markup and the part."""
    seen, out = set(), []
    for i in ids:
        if str(i) in seen:
            continue
        g = rs.ObjectTopGroup(i)
        members = rs.ObjectsByGroup(g) if g else [i]
        seen.update(str(m) for m in members)
        mark = [m for m in members if any(rs.GetUserText(m, k) for k in MARKUP)]
        out.extend(p for p in (mark, [m for m in members if m not in mark]) if p)
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


def closed(g):
    return isinstance(g, Rhino.Geometry.Curve) and g.IsClosed


def is_part(doc, objs):
    """A group with a closed curve (not a circle) on a Parts:: layer, not panel markup."""
    if any(o.Attributes.GetUserString(k) for o in objs for k in MARKUP):
        return False
    return any(closed(o.Geometry) and not o.Geometry.IsCircle()
               and doc.Layers[o.Attributes.LayerIndex].FullPath.startswith("Parts::") for o in objs)


def is_cross(doc, o):
    """A line of a cross from PointsToCrosses: in a group of exactly two lines."""
    for gi in o.Attributes.GetGroupList() or []:
        m = doc.Objects.FindByGroup(gi)
        if len(m) == 2 and all(isinstance(x.Geometry, Rhino.Geometry.Curve) and x.Geometry.IsLinear() for x in m):
            return True
    return False


def short(o):
    """Copy of a text with the label code only, or None."""
    g = o.Geometry
    if not isinstance(g, Rhino.Geometry.TextEntity):
        return None
    m = CODE.match(g.PlainText)
    if not m:
        return None
    t = Rhino.Geometry.TextEntity.Create(m.group(1), g.Plane, sc.doc.DimStyles.FindId(g.DimensionStyleId) or
                                         sc.doc.DimStyles.Current, False, 0, 0)
    t.TextHeight = g.TextHeight
    t.TextHorizontalAlignment = g.TextHorizontalAlignment
    t.TextVerticalAlignment = g.TextVerticalAlignment
    return t


def mark(doc, o):
    """Geometry to copy to the canvas from a markup object, or None."""
    g = o.Geometry
    if isinstance(g, (Rhino.Geometry.Point, Rhino.Geometry.PointCloud)):
        return g.Duplicate()
    if isinstance(g, Rhino.Geometry.Curve) and (g.IsCircle() or is_cross(doc, o)):
        return g.Duplicate()
    return short(o)


def is_line(doc, o):
    """Markup line (zip, reinforcement, pocket): an open curve on a Parts:: layer or with Zip / markup data."""
    if not isinstance(o.Geometry, Rhino.Geometry.Curve) or o.Geometry.IsClosed:
        return False
    return (doc.Layers[o.Attributes.LayerIndex].FullPath.startswith("Parts::")
            or any(o.Attributes.GetUserString(k) for k in ("Zip",) + MARKUP))


def tick(crv, contour, size, plane, tol):
    """Seam centre tick at the middle of crv: on the contour — into the part, inside — across. None — too short / outside."""
    if crv.GetLength() < 4 * size:
        return None
    ok, t = crv.LengthParameter(crv.GetLength() / 2.0)
    p = crv.PointAt(t)
    n = Vector3d.CrossProduct(crv.TangentAt(t), plane.ZAxis)
    n.Unitize()
    side = [contour.Contains(p + n * s * size / 2.0, plane, tol) == PointContainment.Inside for s in (1, -1)]
    if all(side):
        return LineCurve(Line(p - n * size / 2.0, p + n * size / 2.0))
    if any(side):
        return LineCurve(Line(p, p + n * size * (1 if side[0] else -1)))
    return None


def outer(objs):
    """Largest closed curve of the part (by bbox diagonal) — its contour."""
    cs = [o.Geometry for o in objs if closed(o.Geometry)]
    return max(cs, key=lambda c: c.GetBoundingBox(True).Diagonal.Length)


def canvas(doc, ids, plane, size, tol):
    """Parts with what goes to the canvas: [(source ids, [(original object, geometry)])], number of skipped parts."""
    copied = set()
    for o in doc.Objects:
        src = o.Attributes.GetUserString(KEY)
        if src:
            copied.add(src)
    units = [[doc.Objects.FindId(i) for i in p] for p in parts(ids)]
    found = [u for u in units if is_part(doc, u)]
    done = [u for u in found if any(str(o.Id) in copied or o.Attributes.GetUserString(KEY) for o in u)]
    todo = [u for u in found if u not in done]
    out = []
    for u in todo:
        geo = [(o, o.Geometry.Duplicate()) for o in u if closed(o.Geometry)]
        geo += [(o, g) for o in u if not closed(o.Geometry) for g in [mark(doc, o)] if g]
        out.append(([o.Id for o in u], outer(u), geo))
    if out:
        for u in units:
            if u in found:
                continue
            for o in u:
                g = mark(doc, o)
                crv = o.Geometry if g is None and is_line(doc, o) else None
                if g is None and crv is None:
                    continue
                c = (g or crv).GetBoundingBox(True).Center
                inside = [p for p in out if p[1].Contains(c, plane, tol) != PointContainment.Outside]
                if inside:  # the smallest part around (a reinforcement on a panel — the reinforcement)
                    p = min(inside, key=lambda p: p[1].GetBoundingBox(True).Diagonal.Length)
                else:
                    p = min(out, key=lambda p: p[1].PointAt(p[1].ClosestPoint(c)[1]).DistanceTo(c))
                if crv is not None:
                    g = tick(crv, p[1], size, plane, tol)
                if g:
                    p[2].append((o, g))
    return [(p[0], p[2]) for p in out], len(done)


def layout(doc, ids, gap, plane, start=None, size=20.0):
    """Copies the parts for the canvas in a row from point start (None — continue the row of laid out parts).
    Returns (copy ids, number of parts skipped)."""
    tol = doc.ModelAbsoluteTolerance
    todo, skipped = canvas(doc, ids, plane, size, tol)
    if not todo:
        return [], skipped
    if start is not None:
        ok, x, y = plane.ClosestParameter(start)
    else:  # continue the row to the right of already laid out parts
        prev = [o.Id for o in doc.Objects if o.Attributes.GetUserString(KEY)]
        if not prev:
            return [], skipped
        x0, y0, x1, y1 = box(prev, plane)
        x, y = x1 + gap, y0
    # ponytail: one endless row; if it gets too long — wrap to a new row by the work area width.
    new = []
    to_plane = Transform.PlaneToPlane(plane, Plane.WorldXY)  # bbox in CPlane coordinates
    for src, geo in todo:
        bb = Rhino.Geometry.BoundingBox.Empty
        for _, g in geo:
            bb.Union(g.GetBoundingBox(to_plane))
        xf = Transform.Translation(plane.XAxis * (x - bb.Min.X) + plane.YAxis * (y - bb.Min.Y))
        gi = doc.Groups.Add() if len(geo) > 1 else -1
        for o, g in geo:
            g.Transform(xf)
            a = o.Attributes.Duplicate()
            a.RemoveFromAllGroups()
            if gi >= 0:
                a.AddToGroup(gi)
            a.LayerIndex = layout_layer(doc, o.Attributes.LayerIndex)
            a.SetUserString(KEY, str(o.Id))
            new.append(doc.Objects.Add(g, a))
        x += bb.Max.X - bb.Min.X + gap
    return new, skipped


def main():
    ids = rs.GetObjects(u"Select parts with their markup (window over the panels / parts above)", preselect=True)
    if not ids:
        return
    unit = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    gap = rs.GetReal(u"Gap between parts", sc.sticky.get(STICKY, 10.0), 0)
    if gap is None:
        return
    sc.sticky[STICKY] = gap
    size = rs.GetReal(u"Tick — seam centre tick length", sc.sticky.get(STICKY + "_tick", 20.0 * unit), 0.001)
    if size is None:
        return
    sc.sticky[STICKY + "_tick"] = size
    start = rs.GetPoint(u"Click where to start the row (Enter — continue the row of laid out parts)")
    new, skipped = layout(sc.doc, ids, gap, rs.ViewCPlane(), start, size)
    if start is None and not new and not skipped:
        print(u"Nothing laid out yet — click a point")
        return
    sc.doc.Views.Redraw()
    print(u"Objects laid out: %d; parts skipped (already laid out): %d" % (len(new), skipped))


if __name__ == "__main__":
    main()
