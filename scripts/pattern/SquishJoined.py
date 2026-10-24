# -*- coding: utf-8 -*-
"""Squish Joined — Squish of every surface on its own, the flat pieces laid out joined along their common sides.
Select several surfaces and / or polysurfaces (every face is a piece), then click where the layout goes (its centre).
Two pieces are neighbours where a side of one lies all along on a side of the other (within 1 mm — joined or not).
Each piece is squished alone with a stiff edge (its sides keep their 3D length, ≈ 0.3 mm on 2.4 m); one squish of all
pieces together stretches them by centimetres where they meet at an angle. The biggest piece stays as Squish gives
it, the others are turned and moved (mirrored if they came on the same side of the seam) so that the ends of each
common side meet. A seam over a bend is a bit differently curved on its two sides: the gap between them is printed.
A seam that closes a ring of pieces, or pieces joined to no other, are not moved onto it (printed / placed apart).
The pieces keep the layer of their 3D surface and the Squish link (SquishBack, SquishTo work on them), one group.
"""
import math
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import (AreaMassProperties, BoundingBox, Plane, Point3d, Squisher, SquishParameters, Transform,
                            Vector3d)

SIDE_MM = 1.0  # two sides this close all along are one common side
STIFF = 100.0  # Squish stretch / compress constants of the edge (interior 1): the edge keeps its length
SAMPLES = 40  # points along a side
APART_MM = 300.0  # gap before a group of pieces joined to no other


def mm(doc):
    return Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)


def squish(face):
    """(flat brep, 3D point -> 2D point) of one face, None — Squish failed. No Squish marks: with marks Squish
    crashed Rhino on faces of a polysurface; the 3D / 2D meshes of the Squisher share faces, so a point found on the
    3D mesh is put at the same spot of the 2D one."""
    p = SquishParameters()
    p.BoundaryStretchConstant = STIFF
    p.BoundaryCompressConstant = STIFF
    sq = Squisher()
    flat = sq.SquishSurface(p, face)
    m3, m2 = sq.Get3dMesh(), sq.Get2dMesh()
    if flat is None or m3 is None or m2 is None or m3.Faces.Count != m2.Faces.Count:
        return None

    def to2d(pt):
        mp = m3.ClosestMeshPoint(pt, 0.0)
        return m2.PointAt(mp.FaceIndex, mp.T[0], mp.T[1], mp.T[2], mp.T[3])
    return flat, to2d


def along(crv, n=SAMPLES):
    return [crv.PointAt(t) for t in crv.DivideByCount(n, True)]


def on(crv, pts, d):
    return all(crv.PointAt(crv.ClosestPoint(p)[1]).DistanceTo(p) <= d for p in pts)


def common_sides(sides, d):
    """[(i, j, 3D points along the side they share)]: the shorter side lying all along on the longer one"""
    out = []
    boxes = [[c.GetBoundingBox(True) for c in cs] for cs in sides]
    for i in range(len(sides)):
        for j in range(i + 1, len(sides)):
            for a, ba in zip(sides[i], boxes[i]):
                for b, bb in zip(sides[j], boxes[j]):
                    ba2 = BoundingBox(ba.Min, ba.Max)
                    ba2.Inflate(d)
                    if not BoundingBox.Intersection(ba2, bb).IsValid:
                        continue
                    short, longer = sorted((a, b), key=lambda c: c.GetLength())
                    pts = along(short)
                    if on(longer, pts, d):
                        out.append((i, j, pts))
    return out


def side(p, a, b):
    """which side of the line a → b point p is on (+1 / -1)"""
    v, w = b - a, p - a
    return 1 if v.X * w.Y - v.Y * w.X > 0 else -1


def onto(a0, a1, b0, b1):
    """turn + move taking the chord a0 a1 onto b0 b1 (middles together, along it)"""
    va, vb = a1 - a0, b1 - b0
    ang = math.atan2(va.X * vb.Y - va.Y * vb.X, va.X * vb.X + va.Y * vb.Y)
    ma = Point3d((a0.X + a1.X) / 2, (a0.Y + a1.Y) / 2, 0)
    mb = Point3d((b0.X + b1.X) / 2, (b0.Y + b1.Y) / 2, 0)
    return Transform.Translation(mb - ma) * Transform.Rotation(ang, Vector3d.ZAxis, ma)


def layout(flats, maps, areas, seams):
    """Transform of every piece and [(gap along the side, joined — False: it closes a ring)] of every seam; the
    biggest piece of each group of joined pieces first, groups apart along X"""
    xf = [None] * len(flats)
    used = []
    left = set(range(len(flats)))
    x_end = None
    while left:
        start = max(left, key=lambda k: areas[k])
        xf[start] = Transform.Identity
        group, todo = [start], [start]
        while todo:
            i = todo.pop(0)
            for s, (a, b, pts) in enumerate(seams):
                if i not in (a, b) or s in used:
                    continue
                j = b if a == i else a
                if xf[j] is not None:
                    continue
                pi = [xf[i] * maps[i](p) for p in (pts[0], pts[-1])]
                pj = [maps[j](p) for p in (pts[0], pts[-1])]
                t = onto(pj[0], pj[1], pi[0], pi[1])
                ci = xf[i] * AreaMassProperties.Compute(flats[i]).Centroid
                cj = t * AreaMassProperties.Compute(flats[j]).Centroid
                if side(ci, pi[0], pi[1]) == side(cj, pi[0], pi[1]):
                    t = Transform.Mirror(Plane(pi[0], pi[1] - pi[0], Vector3d.ZAxis)) * t
                xf[j] = t
                used.append(s)
                group.append(j)
                todo.append(j)
        left -= set(group)
        bb = BoundingBox.Empty
        for k in group:
            g = flats[k].DuplicateBrep()
            g.Transform(xf[k])
            bb.Union(g.GetBoundingBox(True))
        if x_end is not None:
            move = Transform.Translation(Vector3d(x_end - bb.Min.X, 0, 0))
            for k in group:
                xf[k] = move * xf[k]
            bb.Transform(move)
        x_end = bb.Max.X + APART_MM
    out = []
    for s, (a, b, pts) in enumerate(seams):
        out.append((max((xf[a] * maps[a](p)).DistanceTo(xf[b] * maps[b](p)) for p in pts), s in used))
    return xf, out


def edge_error(sides, to2d):
    """largest |2D − 3D| length of the sides of a piece"""
    worst = 0.0
    for c in sides:
        p3 = along(c)
        p2 = [to2d(p) for p in p3]
        l3 = sum(p.DistanceTo(q) for p, q in zip(p3, p3[1:]))
        l2 = sum(p.DistanceTo(q) for p, q in zip(p2, p2[1:]))
        worst = max(worst, abs(l2 - l3))
    return worst


def run(doc, ids, centre):
    """Lays the pieces out, centre of the layout at centre; (piece ids, report lines) or a message"""
    k = mm(doc)
    tol = doc.ModelAbsoluteTolerance
    faces, attrs = [], []
    for i in ids:
        obj = doc.Objects.FindId(i)
        for f in obj.Geometry.Faces:
            faces.append(f.DuplicateFace(False))
            attrs.append(obj.Attributes)
    if not faces:
        return u"No surfaces selected"
    flats, maps = [], []
    for n, f in enumerate(faces):
        r = squish(f.Faces[0])
        if r is None:
            return u"Squish failed on piece %d" % (n + 1)
        flats.append(r[0])
        maps.append(r[1])
    sides = [[e.DuplicateCurve() for e in f.Edges if e.GetLength() > 10 * tol] for f in faces]
    areas = [AreaMassProperties.Compute(f).Area for f in faces]
    seams = common_sides(sides, SIDE_MM * k)
    xf, gaps = layout(flats, maps, areas, seams)
    bb = BoundingBox.Empty
    for f, t in zip(flats, xf):
        f.Transform(t)
        bb.Union(f.GetBoundingBox(True))
    move = Transform.Translation(centre - bb.Center)
    group = doc.Groups.Add()
    out = []
    for f, a in zip(flats, attrs):
        f.Transform(move)
        at = a.Duplicate()
        at.RemoveFromAllGroups()
        at.AddToGroup(group)
        out.append(doc.Objects.AddBrep(f, at))
    joined = [g for g, j in gaps if j]
    ring = [g for g, j in gaps if not j]
    alone = len(set(range(len(faces))) - set(s[0] for s in seams) - set(s[1] for s in seams))
    lines = [u"Squish Joined: %d pieces, %d joined along a common side; sides 2D − 3D up to %.1f mm" % (
        len(faces), len(joined), max(edge_error(sides[n], maps[n]) for n in range(len(faces))) / k)]
    if joined:
        lines.append(u"  joined sides: gap along them up to %.1f mm (a seam over a bend is curved a bit differently "
                     u"on its two sides)" % (max(joined) / k))
    if ring:
        lines.append(u"  %d common sides close a ring — not joined, off up to %.1f mm" % (len(ring), max(ring) / k))
    if alone:
        lines.append(u"  %d pieces have no common side — placed apart" % alone)
    return out, lines


def main():
    ids = rs.GetObjects(u"Select the surfaces / polysurfaces to squish (pieces with common sides are joined)",
                        rs.filter.surface | rs.filter.polysurface, preselect=True)
    if not ids:
        return
    centre = rs.GetPoint(u"Centre of the layout")
    if centre is None:
        return
    r = run(sc.doc, ids, centre)
    if not isinstance(r, tuple):
        print(r)
        return
    rs.UnselectAllObjects()
    rs.SelectObjects(r[0])
    for line in r[1]:
        print(line)
    sc.doc.Views.Redraw()


if __name__ == "__main__":
    main()
