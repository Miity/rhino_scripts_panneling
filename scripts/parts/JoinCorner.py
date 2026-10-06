# -*- coding: utf-8 -*-
"""Join two parts at a panel corner (ZipCover / Seam / any with different width W) into one.
Two parts on neighbouring edges meet at the panel corner in a single point only, leaving a notch
between them. Select the parts (labels and groups may be included, window selection), click in the notch near the corner
(several corners in a row, Enter — done); the click must be in the notch — it tells which segments are the ends. The ends of both parts at this corner are removed, the outer
edges are extended along the tangent to their intersection (like _Connect), giving one closed curve.
Last corner of a frame around the panel (both ends belong to one part) → only the outer contour is kept.
Parts inside the panel (ReinfBord) overlap at the corner instead of leaving a notch → simple union
(inner edges to their intersection); click near the corner.
The new curve takes the layer and group of the first part, the group of the second (label, seam points) merges into it.
Parts with Layout=Yes (markup on the panel + full part above, UserText PartLink): you may select the markup
or the part above and click the corner in either — the parts above are joined, the markup on the panel is rebuilt
(lines of the joined part that do not lie on panel edges).
"""
import math
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import AreaMassProperties, Curve, Line, LineCurve, PolylineCurve, Transform, Vector3d
from Rhino.Geometry.Intersect import Intersection


def at(segs, p, tol):
    """[(segment, direction from p)] for segments that have an end at p."""
    res = []
    for s in segs:
        if s.PointAtStart.DistanceTo(p) <= tol:
            res.append((s, s.TangentAtStart))
        elif s.PointAtEnd.DistanceTo(p) <= tol:
            res.append((s, -s.TangentAtEnd))
    return res


def other_end(s, p):
    return s.PointAtEnd if s.PointAtStart.DistanceTo(p) < s.PointAtEnd.DistanceTo(p) else s.PointAtStart


def in_sector(v, u, w):
    """v between directions u and w (angle between them < 180°)."""
    n = Vector3d.CrossProduct(u, w)
    return n.Length > 1e-9 and Vector3d.CrossProduct(u, v) * n > 0 and Vector3d.CrossProduct(v, w) * n > 0


def shared_corner(sa, sb, click, tol):
    """Common vertex of segments sa and sb closest to click, or None.
    sb is sa — a corner where the part touches itself (last corner of a frame around the panel)."""
    common = [s.PointAtStart for s in sa
              if (len(at(sa, s.PointAtStart, tol)) >= 4 if sb is sa else at(sb, s.PointAtStart, tol))]
    return min(common, key=click.DistanceTo) if common else None


def fill(sa, sb, ea, eb, c, tol):
    """(notch area, ea, eb, xa, xb, o) if ea, eb are ends whose outer edges meet at o."""
    xa, xb = other_end(ea, c), other_end(eb, c)
    ends = []
    for segs, e, x in ((sa, ea, xa), (sb, eb, xb)):
        nxt = [t for t in at(segs, x, tol) if t[0] is not e]
        if len(nxt) != 1:
            return None
        ends.append(-nxt[0][1])  # tangent of the outer edge, extension past x
    ok, ta, tb = Intersection.LineLine(Line(xa, xa + ends[0]), Line(xb, xb + ends[1]), tol, False)
    if not ok or ta < -tol or tb < -tol:
        return None
    o = xa + ends[0] * ta
    area = (Vector3d.CrossProduct(xa - c, o - c).Length + Vector3d.CrossProduct(o - c, xb - c).Length) / 2
    return area, ea, eb, xa, xb, o


def join(a, b, click, tol):
    """[closed curves] — a and b joined at the corner near click; or an error string.
    b None — both ends at the corner belong to a: the frame closes → only the outer contour."""
    sa = list(a.DuplicateSegments())  # list: stable wrappers for `is`
    sb = sa if b is None else list(b.DuplicateSegments())
    c = shared_corner(sa, sb, click, tol)
    if c is None:
        return u"parts have no common corner"
    joined = overlap(a, b, tol)
    if joined is None:
        joined = gap(sa, sb, c, click, tol)
        if isinstance(joined, str):
            return joined
    out = []
    for crv in joined:
        ok, pl = crv.TryGetPolyline()  # as in ZipCover: a clean polyline for PreparePanelCut
        if ok:
            pl.DeleteShortSegments(tol)
            if hasattr(pl, "MergeColinearSegments"):
                pl.MergeColinearSegments(1e-6, True)
            crv = PolylineCurve(pl)
        out.append(crv)
    return out


def overlap(a, b, tol):
    """[union of a and b] if they overlap (strips inside the panel, ReinfBord); otherwise None."""
    # ponytail: a frame of inward strips (last corner — part with itself) is not handled
    if b is None:
        return None
    u = Curve.CreateBooleanUnion([a, b], tol)
    if not u or len(u) != 1:
        return None
    area = lambda c: AreaMassProperties.Compute(c).Area
    ua, aa, ab = area(u[0]), area(a), area(b)
    return [u[0]] if max(aa, ab) * 1.001 < ua < 0.999 * (aa + ab) else None  # a real overlap, not a touch and not the same part


def gap(sa, sb, c, click, tol):
    """[closed curves] — parts with a notch at corner c, ends removed, outer edges to their intersection; or an error string."""
    # Ends — the two segments at the corner with the click between them (in the notch). Without the panel the parts are symmetric:
    # the pair "edge + edge" also closes (fills the panel), so only the click can tell them apart.
    v = click - c
    best = None
    for ea, da in at(sa, c, tol):
        for eb, db in at(sb, c, tol):
            if ea is eb or Vector3d.VectorAngle(da, db) > math.radians(175):  # end of one along the edge of the other
                continue
            if in_sector(v, da, db):
                best = fill(sa, sb, ea, eb, c, tol)
    if best is None:
        return u"click in the notch between the parts near the corner (or the outer edges do not meet — concave corner)"
    _, ea, eb, xa, xb, o = best
    rest = [s for s in sa if s is not ea and s is not eb]
    if sb is not sa:
        rest += [s for s in sb if s is not eb]
    rest += [LineCurve(p, o) for p in (xa, xb) if p.DistanceTo(o) > tol]
    joined = Curve.JoinCurves(rest, tol)
    if len(joined) != (2 if sb is sa else 1) or not all(c.IsClosed for c in joined):
        return u"part did not close"
    if sb is sa:  # frame closed: the inner contour (= panel edge) is not needed, the outer one stays
        joined = [max(joined, key=lambda c: c.GetBoundingBox(True).Diagonal.Length)]
    return joined


def link_of(i):
    """(PartLink, LayoutUp vector) of the full part or (None, None)."""
    up = rs.GetUserText(i, "LayoutUp")
    return (rs.GetUserText(i, "PartLink"), Vector3d(*[float(x) for x in up.split(",")])) if up else (None, None)


def linked(link, markup):
    """Objects with UserText PartLink == link: markup or the full part."""
    return [o.Id for o in sc.doc.Objects.FindByUserString("PartLink", link, True)
            if bool(o.Attributes.GetUserString("PartMarkup")) == markup]


def to_full(ids):
    """Replaces markup (open curve with PartMarkup) with its full part (closed contour above)."""
    out = []
    for i in ids:
        if rs.GetUserText(i, "PartMarkup"):
            i = next((k for k in linked(rs.GetUserText(i, "PartLink"), False)
                      if rs.IsCurve(k) and rs.IsCurveClosed(k)), None)
        if i is not None and rs.IsCurveClosed(i) and i not in out:
            out.append(i)
    return out


def moved(crv, v):
    c = crv.DuplicateCurve()
    c.Transform(Transform.Translation(v))
    return c


def rebuild_markup(doc, res, parts, up, tol):
    """Markup of the joined part: res (above) moved by -up, without panel edges. parts — [(contour id, PartLink)]
    of the source parts (still in the document). Old markup curves are deleted, labels go to the markup group of the first."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.modules.pop("ReinfCircle", None)  # Rhino caches modules per session
    from ReinfCircle import off_panel
    edges, old = [], []
    for i, link in parts:
        marks = linked(link, True)
        curves = [rs.coercecurve(m) for m in marks if rs.IsCurve(m)]
        # panel edges = segments of the source part (in place) that do not lie on its markup
        edges += [g for g in moved(rs.coercecurve(i), -up).DuplicateSegments()
                  if not curves or off_panel(g, curves, tol)]
        old.append(marks)
    first = [m for m in old[0] if rs.IsCurve(m)]
    if not first:
        return
    attrs = doc.Objects.FindId(first[0]).Attributes.Duplicate()
    groups = rs.ObjectGroups(first[0])
    new = [doc.Objects.AddCurve(c, attrs) for r in res for c in off_panel(moved(r, -up), edges, tol)]
    rest = [m for marks in old[1:] for m in marks if not rs.IsCurve(m)]  # markup labels of the second part
    for m in rest:
        rs.RemoveObjectFromAllGroups(m)
        rs.SetUserText(m, "PartLink", parts[0][1])
    rs.DeleteObjects([m for marks in old for m in marks if rs.IsCurve(m)])
    if groups:
        rs.AddObjectsToGroup(new + rest, groups[0])


def main():
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    ids = rs.GetObjects(u"Select parts to join at corners", rs.filter.curve, preselect=True) or []
    ids = to_full(ids)
    if not ids:
        print(u"No closed part selected (or markup with a part above).")
        return
    rs.UnselectAllObjects()
    made = []
    while True:
        click = rs.GetPoint(u"Click in the notch between the parts near the corner (Enter — done)")
        if click is None:
            break
        # pair of parts (or a part with itself, j == i) with a common vertex closest to the click;
        # click on the markup on the panel → the same corner above (+LayoutUp)
        best = None
        segs = [list(rs.coercecurve(k).DuplicateSegments()) for k in ids]
        for i in range(len(ids)):
            up = link_of(ids[i])[1]
            for p in [click] + ([click + up] if up else []):
                for j in range(i, len(ids)):
                    c = shared_corner(segs[i], segs[j], p, tol)
                    if c is not None and (best is None or c.DistanceTo(p) < best[0]):
                        best = (c.DistanceTo(p), i, j, p)
        if best is None:
            print(u"No corner near the click where part ends meet.")
            continue
        _, i, j, p = best
        res = join(rs.coercecurve(ids[i]), None if i == j else rs.coercecurve(ids[j]), p, tol)
        if isinstance(res, str):
            print(u"Skipped: %s" % res)
            continue
        ia, ib = ids[i], ids[j]
        (la, up), lb = link_of(ia), link_of(ib)[0]
        if la:
            rebuild_markup(doc, res, [(ia, la)] + ([(ib, lb)] if lb and ib != ia else []), up, tol)
        attrs = doc.Objects.FindId(ia).Attributes.Duplicate()  # layer and groups of the first part (and PartLink)
        new = [doc.Objects.AddCurve(crv, attrs) for crv in res]
        ga, gb = rs.ObjectGroups(ia), rs.ObjectGroups(ib) if ib != ia else None
        rs.DeleteObjects(list(set([ia, ib])))
        if gb:
            members = rs.ObjectsByGroup(gb[0]) or []
            if ga:
                for m in members:
                    rs.RemoveObjectFromGroup(m, gb[0])
                rs.AddObjectsToGroup(members, ga[0])
            else:
                rs.AddObjectsToGroup(new, gb[0])
            if la:
                for m in members:
                    rs.SetUserText(m, "PartLink", la)
        ids = [k for k in ids if k not in (ia, ib)] + new
        made = [k for k in made if k not in (ia, ib)] + new
        doc.Views.Redraw()
    if made:
        rs.SelectObjects(made)
    print(u"Joined: %d parts (selected)" % len(made))


if __name__ == "__main__":
    main()
