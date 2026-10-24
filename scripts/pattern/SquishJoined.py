# -*- coding: utf-8 -*-
"""Squish Joined — Squish of every surface on its own, the flat pieces laid out joined along their common sides.
Select several surfaces and / or polysurfaces (every face is a piece), then click where the layout goes (its centre).
Two pieces are neighbours where a side of one lies all along on a side of the other (within 1 mm — joined or not).
Each piece is squished alone (by default with a stiff edge: its sides keep their 3D length, ≈ 0.3 mm on 2.4 m); one
squish of all pieces together stretches them by centimetres where they meet at an angle. The options of the Squish
dialog are in the click prompt (checked against the dialog: Material Rigid = PhysicalStress, Split Seams = the mesh may
come apart along a seam, Preserve Boundary); Outside is this script's own: Up — like the model from Top, Down — mirrored. The biggest piece stays as Squish gives
it, the others are turned and moved (mirrored if they came on the same side of the seam) so that the ends of each
common side meet. A seam over a bend is a bit differently curved on its two sides: the gap between them is printed.
A seam that closes a ring of pieces, or pieces joined to no other, are not moved onto it (printed / placed apart).
The whole layout is turned (mirrored if needed) so that the biggest piece looks like the 3D model seen from Top.
Diff = Yes: a TextDot inside each side of the layout with its length 2D − 3D (mm), layer Labels::SquishJoined.
The pieces keep the layer of their 3D surface and the Squish link (SquishBack, SquishTo work on them), one group.
"""
import math
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import (AreaMassProperties, BoundingBox, Plane, Point3d, SquishDeformation,
                            SquishFlatteningAlgorithm, Squisher, SquishParameters, TextDot, Transform, Vector3d)

SIDE_MM = 1.0  # two sides this close all along are one common side
DEFORMATIONS = ("Free", "StretchMostly", "StretchOnly", "CompressMostly", "CompressOnly", "Custom")
CONSTANTS = ("BndStretch", "BndCompress", "IntStretch", "IntCompress")  # Custom: bigger — less of that deformation
# options; default — a stiff edge (Custom 100 100 1 1: the edge keeps its length), Split Seams off as usually set
DEFAULTS = {"SplitSeams": False, "PreserveBoundary": False, "Deformation": "Custom", "BndStretch": 100.0,
            "BndCompress": 100.0, "IntStretch": 1.0, "IntCompress": 1.0, "Rigid": False, "Down": False, "Diff": False}
SAMPLES = 40  # points along a side
APART_MM = 300.0  # gap before a group of pieces joined to no other
DOT_IN_MM = 60.0  # Diff dot: this far inside the piece from the middle of its side (a quarter of the way to the centre at most)
DOT_LAYER = u"Labels::SquishJoined"
STICKY = "SquishJoined"


def mm(doc):
    return Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)


def params(o):
    """SquishParameters of the options, the way the Squish dialog sets them"""
    p = SquishParameters()
    p.SetDeformation(getattr(SquishDeformation, o["Deformation"]), o["PreserveBoundary"],
                     *[o[c] for c in CONSTANTS])
    p.Algorithm = SquishFlatteningAlgorithm.PhysicalStress if o["Rigid"] else SquishFlatteningAlgorithm.Geometric
    p.PreserveTopology = not o["SplitSeams"]
    return p


def squish(face, p):
    """(flat brep, 3D point -> 2D point) of one face, None — Squish failed. No Squish marks: with marks Squish
    crashed Rhino on faces of a polysurface; the 3D / 2D meshes of the Squisher share faces, so a point found on the
    3D mesh is put at the same spot of the 2D one."""
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


def like_3d(pairs):
    """Turn (+ mirror if that fits better) of the layout that makes it look like the 3D seen from Top: least squares
    over (3D point, its layout point) pairs of the biggest piece, the 3D flattened onto world XY; (Transform, mirrored)"""
    best = None
    for flip in (False, True):
        q = [Point3d(b.X, -b.Y, 0) if flip else Point3d(b.X, b.Y, 0) for _, b in pairs]
        p = [Point3d(a.X, a.Y, 0) for a, _ in pairs]
        cq = Point3d(sum(v.X for v in q) / len(q), sum(v.Y for v in q) / len(q), 0)
        cp = Point3d(sum(v.X for v in p) / len(p), sum(v.Y for v in p) / len(p), 0)
        sn = sum((a.X - cq.X) * (b.Y - cp.Y) - (a.Y - cq.Y) * (b.X - cp.X) for a, b in zip(q, p))
        cs = sum((a.X - cq.X) * (b.X - cp.X) + (a.Y - cq.Y) * (b.Y - cp.Y) for a, b in zip(q, p))
        t = Transform.Rotation(math.atan2(sn, cs), Vector3d.ZAxis, cq)
        if flip:
            t = t * Transform.Mirror(Plane.WorldZX)
        moved = [t * Point3d(b.X, b.Y, 0) for _, b in pairs]
        off = Vector3d(cp - Point3d(sum(v.X for v in moved) / len(moved), sum(v.Y for v in moved) / len(moved), 0))
        err = sum((m + off).DistanceTo(a) ** 2 for m, a in zip(moved, p))
        if best is None or err < best[0]:
            best = (err, t, flip)
    return best[1], best[2]


def side_diffs(sides, to2d):
    """[(2D − 3D length, 2D middle)] of the sides of a piece (Squish coordinates)"""
    out = []
    for c in sides:
        p3 = along(c)
        p2 = [to2d(p) for p in p3]
        l3 = sum(p.DistanceTo(q) for p, q in zip(p3, p3[1:]))
        l2 = sum(p.DistanceTo(q) for p, q in zip(p2, p2[1:]))
        out.append((l2 - l3, to2d(c.PointAt(c.Domain.Mid))))
    return out


def dot_attrs(doc, group):
    """attributes of the Diff TextDots: layer Labels::SquishJoined (hidden with all labels), the layout group"""
    for path in (u"Labels", DOT_LAYER):
        if doc.Layers.FindByFullPath(path, -1) < 0:
            lay = Rhino.DocObjects.Layer()
            lay.Name = path.split(u"::")[-1]
            if u"::" in path:
                lay.ParentLayerId = doc.Layers.FindIndex(doc.Layers.FindByFullPath(u"Labels", -1)).Id
            doc.Layers.Add(lay)
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = doc.Layers.FindByFullPath(DOT_LAYER, -1)
    a.AddToGroup(group)
    return a


def run(doc, ids, centre, diff=False, opts=None):
    """Lays the pieces out, centre of the layout at centre, options opts (DEFAULTS for the missing ones);
    (piece ids, report lines) or a message"""
    o = dict(DEFAULTS)
    o.update(opts or {})
    diff = diff or o["Diff"]
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
        r = squish(f.Faces[0], params(o))
        if r is None:
            return u"Squish failed on piece %d%s" % (n + 1, u"" if o["SplitSeams"] else u" (a closed surface: SplitSeams=Yes)")
        flats.append(r[0])
        maps.append(r[1])
    sides = [[e.DuplicateCurve() for e in f.Edges if e.GetLength() > 10 * tol] for f in faces]
    areas = [AreaMassProperties.Compute(f).Area for f in faces]
    seams = common_sides(sides, SIDE_MM * k)
    xf, gaps = layout(flats, maps, areas, seams)
    big = max(range(len(faces)), key=lambda n: areas[n])  # the steep ones (seen from Top as a line) would skew it
    turn, mirrored = like_3d([(p, xf[big] * maps[big](p)) for c in sides[big] for p in along(c)])
    if o["Down"]:
        turn = Transform.Mirror(Plane.WorldYZ) * turn
    xf = [turn * t for t in xf]
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
    diffs = [side_diffs(sides[n], maps[n]) for n in range(len(faces))]
    if diff:
        da = dot_attrs(doc, group)
        for n, ds in enumerate(diffs):
            t = move * xf[n]
            c = AreaMassProperties.Compute(flats[n]).Centroid  # flats are already moved
            for d, mid in ds:
                m = t * mid
                v = c - m
                step = min(DOT_IN_MM * k, v.Length / 4)  # inside the piece: a seam's two dots apart; a narrow
                if step > 0:                               # strip keeps each dot by its own side
                    v.Unitize()
                    m = m + v * step
                out.append(doc.Objects.AddTextDot(TextDot(u"%+.1f" % (d / k), m), da))
    joined = [g for g, j in gaps if j]
    ring = [g for g, j in gaps if not j]
    alone = len(set(range(len(faces))) - set(s[0] for s in seams) - set(s[1] for s in seams))
    lines = [u"Squish Joined: %d pieces, %d joined along a common side; sides 2D − 3D up to %.1f mm" % (
        len(faces), len(joined), max(abs(d) for ds in diffs for d, _ in ds) / k)]
    if joined:
        lines.append(u"  joined sides: gap along them up to %.1f mm (a seam over a bend is curved a bit differently "
                     u"on its two sides)" % (max(joined) / k))
    if ring:
        lines.append(u"  %d common sides close a ring — not joined, off up to %.1f mm" % (len(ring), max(ring) / k))
    if alone:
        lines.append(u"  %d pieces have no common side — placed apart" % alone)
    if mirrored and not o["Down"]:
        lines.append(u"  mirrored: Squish laid it out as seen from below — now it looks like the model from Top")
    custom = u"(%s)" % u" ".join(u"%g" % o[c] for c in CONSTANTS) if o["Deformation"] == "Custom" else u""
    lines.append(u"  Squish: SplitSeams=%s PreserveBoundary=%s Deformation=%s%s Material=%s Outside=%s" % (
        u"Yes" if o["SplitSeams"] else u"No", u"Yes" if o["PreserveBoundary"] else u"No", o["Deformation"], custom,
        u"Rigid" if o["Rigid"] else u"Floppy", u"Down" if o["Down"] else u"Up"))
    return out, lines


def get_options():
    """(centre of the layout, options) or None; the options remembered in sc.sticky"""
    o = dict(DEFAULTS)
    o.update(sc.sticky.get(STICKY, {}))
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Centre of the layout")
        toggles, nums = {}, {}
        for key in ("SplitSeams", "PreserveBoundary"):
            toggles[key] = Rhino.Input.Custom.OptionToggle(o[key], "No", "Yes")
            gp.AddOptionToggle(key, toggles[key])
        i_def = gp.AddOptionList("Deformation", DEFORMATIONS, DEFORMATIONS.index(o["Deformation"]))
        if o["Deformation"] == "Custom":
            for key in CONSTANTS:
                nums[key] = Rhino.Input.Custom.OptionDouble(o[key], 0.001, 1e6)
                gp.AddOptionDouble(key, nums[key])
        for key, name, off, on in (("Rigid", "Material", "Floppy", "Rigid"), ("Down", "Outside", "Up", "Down"),
                                   ("Diff", "Diff", "No", "Yes")):
            toggles[key] = Rhino.Input.Custom.OptionToggle(o[key], off, on)
            gp.AddOptionToggle(name, toggles[key])
        r = gp.Get()
        if r == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_def:
                o["Deformation"] = DEFORMATIONS[gp.Option().CurrentListOptionIndex]
            for key, t in toggles.items():
                o[key] = t.CurrentValue
            for key, n in nums.items():
                o[key] = n.CurrentValue
            sc.sticky[STICKY] = dict(o)
            continue
        if r != Rhino.Input.GetResult.Point:
            return None
        return gp.Point(), o


HELP = (u"Squish Joined (options as in the Squish dialog) — SplitSeams: Yes — the surface may come apart along its seam "
        u"(a closed one needs it); PreserveBoundary: keep the side lengths; Deformation: Free / StretchMostly / "
        u"StretchOnly / CompressMostly / CompressOnly / Custom — BndStretch, BndCompress, IntStretch, IntCompress "
        u"(bigger — less of that deformation; 100 100 1 1 — stiff edge, the default); Material: Floppy / Rigid; "
        u"Outside: Up — like the model from Top, Down — mirrored; Diff: Yes — a TextDot inside each side of the layout, "
        u"its length 2D − 3D in mm (layer Labels::SquishJoined)")


def main():
    print(HELP)
    ids = rs.GetObjects(u"Select the surfaces / polysurfaces to squish (pieces with common sides are joined)",
                        rs.filter.surface | rs.filter.polysurface, preselect=True)
    if not ids:
        return
    got = get_options()
    if got is None:
        return
    r = run(sc.doc, ids, got[0], opts=got[1])
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
