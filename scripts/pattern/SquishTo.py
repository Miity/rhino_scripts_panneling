# -*- coding: utf-8 -*-
"""Squish To — the opposite of SquishBack: new marks drawn on the 3D model (points, curves, TextDots: a button, a zip…)
onto the flat surface that Squish made from it, wherever that surface is now (moved, turned, mirrored).
Select the 3D marks together with the 3D surface (or polysurface — as a whole or one face of it) they are on (a window over both is fine: of several surfaces the one
that was squished is used), then the squished 2D surfaces — one or the whole group at once (the Squish results themselves — a DupBorder curve does not know
the 3D).
The squished surface keeps the 3D ↔ 2D link (SquishBack uses it); Rhino only goes 2D → 3D, so the way back is built
from it: a fine mesh over the 2D surface is squished back to 3D, each mark is found on that 3D mesh and put at the same
spot of the 2D mesh, then corrected with SquishBack until it goes back onto the mark.
The 3D side of the link may come out shifted (seen after the 2D panel was moved: the command SquishBack follows the 3D
object by its id, a script cannot read it) — so the squished-back mesh is first fitted onto the selected 3D surface.
Only the 3D surface selected, no marks — every visible, unlocked point / curve / TextDot lying on it (within 5 mm; a curve
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
SURF_MM = 5.0  # only the surface selected: the marks lying on it within this are taken
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
        cands = []  # a polysurface: as a whole (squished in one piece) or any one face of it (squished alone)
        for b in breps:
            cands.append(b)
            if b.Faces.Count > 1:
                cands.extend(f.DuplicateFace(False) for f in b.Faces)  # ponytail: every face tried — slow on 100+ faces
        (self.shift, med), self.brep = min(((shift_onto(pts, b, tol), b) for b in cands), key=lambda f: f[0][1])
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


def flatten(links, geo, tol):
    """2D copies of a 3D mark on the squished pieces it lies on (one link per piece) and the largest distance off them:
    [(2D geometry, off)]. A point / TextDot goes to the closest piece; a curve is cut where it passes from one piece to
    the next (a run stays on its piece while it lies on it within SAME_MM; the seam gap is one sample step)."""
    def dist(l, p):
        return l.brep.ClosestPoint(p).DistanceTo(p)

    def closest(p):
        return min(links, key=lambda l: dist(l, p))

    if isinstance(geo, (Point, TextDot)):
        p = geo.Location if isinstance(geo, Point) else geo.Point
        l = closest(p)
        q, off = l.to2d([p])
        if isinstance(geo, Point):
            return [(Point(q[0]), off)]
        d = geo.Duplicate()
        d.Point = q[0]
        return [(d, off)]
    pl = list(geo.ToPolyline(0, 0, 0.05, 0, 0, tol, 0, 2 * mm(sc.doc), True).ToPolyline())  # every ≤ 2 mm
    runs, cur = [], None
    for p in pl:
        if cur is None or dist(cur[0], p) > SAME_MM * mm(sc.doc):
            l = closest(p)
            if cur is not None and l is cur[0]:
                cur[1].append(p)
                continue
            cur = (l, [])
            runs.append(cur)
        cur[1].append(p)
    out = []
    for l, pts in runs:
        if len(pts) > 1:
            q, off = l.to2d(pts)
            out.append((PolylineCurve(q), off))
    return out


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


def transfer(doc, mark_ids, flat_ids, tol, srf_ids):
    """Marks onto the squished pieces (flat_ids: one id or several — a whole group at once), each piece's link fitted onto
    the face / surface of srf_ids it fits best; no mark_ids — every mark lying on those faces: (added ids, skipped — off
    the surface, already there) or why not (a message). A curve over several pieces is cut at the seams."""
    if not isinstance(flat_ids, (list, tuple)):
        flat_ids = [flat_ids]
    flats = [rs.coercebrep(i) for i in flat_ids]
    if not flats or any(f is None or not Squisher.Is2dPatternSquished(f) for f in flats):
        return u"Not a Squish result: select the squished surfaces themselves (a DupBorder curve does not know the 3D)"
    near = ON_MM * mm(doc)
    breps = [b for b in (rs.coercebrep(i) for i in srf_ids) if b]
    if not breps:
        return u"Select the 3D surface together with the marks"
    links, worst = [], 0.0
    for f in flats:
        link = Link(f)
        med = link.fit(breps, tol)
        if med > near:
            worst = max(worst, med)  # this piece is not from the selected 3D: left out
        else:
            links.append(link)
    if not links:
        return u"None of the selected 3D surfaces is the one these panels were squished from (off by %.0f mm)" % (
            worst / mm(doc))
    if not mark_ids:
        mark_ids = list(set(i for b in breps for i in marks_on(doc, b, SURF_MM * mm(doc))))
    same_mm = SAME_MM * mm(doc)
    bb = Rhino.Geometry.BoundingBox.Empty
    for f in flats:
        bb.Union(f.GetBoundingBox(True))
    bb.Inflate(same_mm)
    there = [o.Geometry for o in objects(doc, bb)]  # what the 2D panels already have
    added, skipped, dups = [], 0, 0
    for oid in mark_ids:
        o = doc.Objects.FindId(oid)
        if o is None or not isinstance(o.Geometry, (Point, Curve, TextDot)):
            continue
        for g, off in flatten(links, o.Geometry, tol):
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
                        u"(only the surface or polysurface — every mark on it)",
                        rs.filter.point | rs.filter.curve | rs.filter.textdot | rs.filter.surface | rs.filter.polysurface,
                        preselect=True)
    if not ids:
        return
    flat = rs.GetObjects(u"Select the squished 2D surfaces (Squish result — the whole group at once)",
                         rs.filter.surface | rs.filter.polysurface)
    flat = [i for i in flat or [] if i not in ids]
    if not flat:
        return
    srfs = [i for i in ids if rs.coercebrep(i)]  # a surface or a polysurface
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
