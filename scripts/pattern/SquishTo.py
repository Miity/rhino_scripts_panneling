# -*- coding: utf-8 -*-
"""Squish To — the opposite of SquishBack: new marks drawn on the 3D model (points, curves, TextDots: a button, a zip…)
onto the flat surface that Squish made from it, wherever that surface is now (moved, turned, mirrored).
Select the 3D marks together with the 3D surface they are on (a window over both is fine: of several surfaces the one
that was squished is used), then the squished 2D surface (the Squish result itself — a DupBorder curve does not know
the 3D).
The squished surface keeps the 3D ↔ 2D link (SquishBack uses it); Rhino only goes 2D → 3D, so the way back is built
from it: a fine mesh over the 2D surface is squished back to 3D, each mark is found on that 3D mesh and put at the same
spot of the 2D mesh, then corrected with SquishBack until it goes back onto the mark.
The 3D side of the link may come out shifted (seen after the 2D panel was moved: the command SquishBack follows the 3D
object by its id, a script cannot read it) — so the squished-back mesh is first fitted onto the selected 3D surface.
Only the 3D surface selected, no marks — every visible, unlocked point / curve / TextDot lying on it (within 1 mm; a curve
wholly) is taken.
A mark already on the 2D surface (same kind, within 1 mm: a point, a TextDot with the same text, a curve of the same
length along it) is not placed again. The new marks go onto the 2D surface with the layer of their 3D originals
(no groups) and are left selected. A selected mark farther than 5 mm from the 3D surface is skipped (not on this panel).
"""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System
from Rhino.Geometry import (Curve, GeometryBase, Mesh, MeshingParameters, Point, Point3d, PolylineCurve, Squisher,
                            TextDot, Vector3d)
from System.Collections.Generic import List

ON_MM = 5.0  # a selected mark farther than this from the squished 3D surface is skipped
SURF_MM = 1.0  # only the surface selected: the marks lying on it within this are taken
SAME_MM = 1.0  # a 2D object of the same kind this close to a new mark is that mark: not placed again
STEPS = 4  # SquishBack corrections
KEEP = 0.7  # the 3D fit uses the closest 70 % of the mesh points


def mm(doc):
    return Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)


def back(flat, pts):
    """SquishBack of 2D points on flat → 3D points, same order."""
    geos = List[GeometryBase]()
    for p in pts:
        geos.Add(Point(p))
    return [g.Location for g in Squisher.SquishBack2dMarks(flat, geos)]


def shift_onto(pts, brep, tol, steps=60):
    """Move (no turn) that puts pts (the squished-back outline) onto the edge of brep, starting from the bounding box
    centres; (vector, median distance). The edge, not the surface: on a gentle surface points could slide along it."""
    edge = Curve.JoinCurves(brep.DuplicateNakedEdgeCurves(True, False))

    def near(q):
        return min((c.PointAt(c.ClosestPoint(q)[1]) for c in edge), key=q.DistanceTo)

    t = brep.GetBoundingBox(True).Center - Rhino.Geometry.BoundingBox(pts).Center
    med = 0.0
    for _ in range(steps):
        d = [near(p + t) - (p + t) for p in pts]
        ds = sorted(d, key=lambda v: v.Length)
        med = ds[len(ds) // 2].Length
        kept = ds[:max(1, int(len(ds) * KEEP))]
        step = sum(kept, Vector3d.Zero) / len(kept)
        t += step
        if step.Length < tol * 1e-3:
            break
    return t, med


class Link(object):
    """3D → 2D through a squished surface: a mesh over it (m2) and the same mesh squished back to 3D (m3),
    moved by shift onto where the 3D surface really is."""

    def __init__(self, flat):
        self.flat = flat
        self.shift = Vector3d.Zero
        self.brep = None  # the 3D surface (fit)
        mp = MeshingParameters.Default
        mp.MaximumEdgeLength = flat.GetBoundingBox(True).Diagonal.Length / 60
        self.m2 = Mesh()
        for m in Mesh.CreateFromBrep(flat, mp):
            self.m2.Append(m)
        self.m3 = self.m2.DuplicateMesh()
        for i, p in enumerate(back(flat, [Point3d(v) for v in self.m2.Vertices])):
            self.m3.Vertices.SetVertex(i, p)

    def fit(self, breps, tol):
        """Move m3 onto the brep (of breps) it fits best; the median distance after (None — no breps)."""
        out = Curve.JoinCurves(self.flat.DuplicateNakedEdgeCurves(True, False))
        pts = back(self.flat, [c.PointAt(t) for c in out for t in c.DivideByCount(200, True)])
        if not breps:
            return None
        (self.shift, med), self.brep = min(((shift_onto(pts, b, tol), b) for b in breps), key=lambda f: f[0][1])
        self.m3.Translate(self.shift)
        return med

    def back(self, pts):
        return [p + self.shift for p in back(self.flat, pts)]

    def guess(self, p):
        """2D point at the same spot of the mesh as 3D point p."""
        return self.m2.PointAt(self.m3.ClosestMeshPoint(p, 0.0))

    def to2d(self, pts):
        """2D points of 3D points pts (on the squished 3D surface) and the largest distance off that surface
        (Squish's own mesh may be a few mm off the surface where it bends hard: measured to the surface itself)."""
        q = [self.guess(p) for p in pts]
        off = max((self.brep.ClosestPoint(p) if self.brep else self.m3.ClosestPoint(p)).DistanceTo(p) for p in pts)
        for _ in range(STEPS):  # q += where p is − where q goes back to, both read on the mesh
            q = [a + (self.guess(p) - self.guess(b)) for a, p, b in zip(q, pts, self.back(q))]
        return q, off


def flatten(link, geo, tol):
    """2D copy of a 3D mark and its largest distance off the squished 3D surface."""
    if isinstance(geo, Point):
        q, off = link.to2d([geo.Location])
        return Point(q[0]), off
    if isinstance(geo, TextDot):
        q, off = link.to2d([geo.Point])
        d = geo.Duplicate()
        d.Point = q[0]
        return d, off
    pl = geo.ToPolyline(0, 0, 0.05, 0, 0, tol, 0, 10 * mm(sc.doc), True).ToPolyline()  # every ≤ 10 mm
    q, off = link.to2d(list(pl))
    return PolylineCurve(q), off


def probe(geo):
    """Points a mark is checked by."""
    if isinstance(geo, Point):
        return [geo.Location]
    if isinstance(geo, TextDot):
        return [geo.Point]
    return [geo.PointAt(t) for t in geo.DivideByCount(8, True)]


def objects(doc, bb):
    """Visible, unlocked points / curves / TextDots inside bounding box bb."""
    s = Rhino.DocObjects.ObjectEnumeratorSettings()
    s.LockedObjects = False
    s.VisibleFilter = True
    s.ObjectTypeFilter = (Rhino.DocObjects.ObjectType.Point | Rhino.DocObjects.ObjectType.Curve |
                          Rhino.DocObjects.ObjectType.TextDot)
    return [o for o in doc.Objects.GetObjectList(s) if bb.Contains(o.Geometry.GetBoundingBox(True))]


def marks_on(doc, brep, near):
    """Ids of the marks lying on brep within near (a curve wholly)."""
    bb = brep.GetBoundingBox(True)
    bb.Inflate(near)
    return [o.Id for o in objects(doc, bb)
            if all(brep.ClosestPoint(p).DistanceTo(p) <= near for p in probe(o.Geometry))]


def same(a, b, near):
    """New 2D mark a is already there as b: same kind, within near (a curve — of the same length, all along b)."""
    if isinstance(a, Point):
        return isinstance(b, Point) and a.Location.DistanceTo(b.Location) <= near
    if isinstance(a, TextDot):
        return isinstance(b, TextDot) and a.Text == b.Text and a.Point.DistanceTo(b.Point) <= near
    return (isinstance(b, Curve) and abs(a.GetLength() - b.GetLength()) <= max(near, 0.01 * a.GetLength()) and
            all(b.PointAt(b.ClosestPoint(p)[1]).DistanceTo(p) <= near for p in probe(a)))


def transfer(doc, mark_ids, flat_id, tol, srf_ids):
    """Marks onto the squished surface, the link fitted onto the 3D surface it fits best of srf_ids; no mark_ids —
    every mark lying on that surface: (added ids, skipped — off the surface, already there) or why not (a message)."""
    flat = rs.coercebrep(flat_id)
    if flat is None or not Squisher.Is2dPatternSquished(flat):
        return u"Not a Squish result: select the squished surface itself (a DupBorder curve does not know the 3D)"
    link = Link(flat)
    near = ON_MM * mm(doc)
    med = link.fit([b for b in (rs.coercebrep(i) for i in srf_ids) if b], tol)
    if med is None:
        return u"Select the 3D surface together with the marks"
    if med > near:
        return u"None of the selected 3D surfaces is the one this panel was squished from (off by %.0f mm)" % (
            med / mm(doc))
    if not mark_ids:
        mark_ids = marks_on(doc, link.brep, SURF_MM * mm(doc))
    same_mm = SAME_MM * mm(doc)
    bb = flat.GetBoundingBox(True)
    bb.Inflate(same_mm)
    there = [o.Geometry for o in objects(doc, bb)]  # what the 2D panel already has
    added, skipped, dups = [], 0, 0
    for oid in mark_ids:
        o = doc.Objects.FindId(oid)
        if o is None or not isinstance(o.Geometry, (Point, Curve, TextDot)):
            continue
        g, off = flatten(link, o.Geometry, tol)
        if off > near:
            skipped += 1
            continue
        if any(same(g, b, same_mm) for b in there):
            dups += 1
            continue
        there.append(g)
        a = o.Attributes.Duplicate()
        a.RemoveFromAllGroups()  # 3D groups do not belong on the 2D panel
        added.append(doc.Objects.Add(g, a))
    doc.Objects.UnselectAll()
    doc.Objects.Select(List[System.Guid](added))  # what was placed stays selected
    doc.Views.Redraw()
    return added, skipped, dups


def main():
    doc = sc.doc
    ids = rs.GetObjects(u"Select the new marks on the 3D model (points, curves, TextDots) and the 3D surface they are on "
                        u"(only the surface — every mark on it)",
                        rs.filter.point | rs.filter.curve | rs.filter.textdot | rs.filter.surface, preselect=True)
    if not ids:
        return
    flat = rs.GetObject(u"Select the squished 2D surface (Squish result)", rs.filter.surface | rs.filter.polysurface)
    if not flat or flat in ids:
        return
    srfs = [i for i in ids if rs.IsSurface(i)]
    r = transfer(doc, [i for i in ids if i not in srfs], flat, doc.ModelAbsoluteTolerance, srfs)
    if not isinstance(r, tuple):
        print(r)
        return
    added, skipped, dups = r
    print(u"Squish To: %d marks placed%s%s" % (
        len(added), u"; %d already there" % dups if dups else u"",
        u"; %d skipped — farther than %g mm from this panel in 3D" % (skipped, ON_MM) if skipped else u""))


if __name__ == "__main__":
    main()
