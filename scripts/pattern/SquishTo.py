# -*- coding: utf-8 -*-
"""Squish To — the opposite of SquishBack: new marks drawn on the 3D model (points, curves, TextDots: a button, a zip…)
onto the flat surface that Squish made from it, wherever that surface is now (moved, turned, mirrored).
Select the 3D marks, then the squished 2D surface (the Squish result itself — a DupBorder curve does not know the 3D).
The squished surface keeps the 3D ↔ 2D link (SquishBack uses it); Rhino only goes 2D → 3D, so the way back is built
from it: a fine mesh over the 2D surface is squished back to 3D, each mark is found on that 3D mesh and put at the same
spot of the 2D mesh, then corrected with SquishBack until it goes back onto the mark.
The marks go onto the 2D surface with the layer of their 3D originals (no groups) and are left selected. A mark farther
than 5 mm from the squished 3D surface is skipped (not on this panel, or the 3D model moved since Squish).
"""
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System
from Rhino.Geometry import (Curve, GeometryBase, Mesh, MeshingParameters, Point, Point3d, PolylineCurve, Squisher,
                            TextDot)
from System.Collections.Generic import List

ON_MM = 5.0  # a mark farther than this from the squished 3D surface is skipped
STEPS = 4  # SquishBack corrections


def mm(doc):
    return Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)


def back(flat, pts):
    """SquishBack of 2D points on flat → 3D points, same order."""
    geos = List[GeometryBase]()
    for p in pts:
        geos.Add(Point(p))
    return [g.Location for g in Squisher.SquishBack2dMarks(flat, geos)]


class Link(object):
    """3D → 2D through a squished surface: a mesh over it (m2) and the same mesh squished back to 3D (m3)."""

    def __init__(self, flat):
        self.flat = flat
        mp = MeshingParameters.Default
        mp.MaximumEdgeLength = flat.GetBoundingBox(True).Diagonal.Length / 60
        self.m2 = Mesh()
        for m in Mesh.CreateFromBrep(flat, mp):
            self.m2.Append(m)
        self.m3 = self.m2.DuplicateMesh()
        for i, p in enumerate(back(flat, [Point3d(v) for v in self.m2.Vertices])):
            self.m3.Vertices.SetVertex(i, p)

    def guess(self, p):
        """2D point at the same spot of the mesh as 3D point p, and how far p is from the 3D mesh."""
        mp = self.m3.ClosestMeshPoint(p, 0.0)
        return self.m2.PointAt(mp), mp.Point.DistanceTo(p)

    def to2d(self, pts):
        """2D points of 3D points pts (on the squished 3D surface) and the largest distance off it."""
        g = [self.guess(p) for p in pts]
        q, off = [a for a, _ in g], max(d for _, d in g)
        for _ in range(STEPS):  # q += where p is − where q goes back to, both read on the mesh
            q = [a + (self.guess(p)[0] - self.guess(b)[0]) for a, p, b in zip(q, pts, back(self.flat, q))]
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


def transfer(doc, mark_ids, flat_id, tol):
    """Marks onto the squished surface: (added ids, skipped) or why not (a message)."""
    flat = rs.coercebrep(flat_id)
    if flat is None or not Squisher.Is2dPatternSquished(flat):
        return u"Not a Squish result: select the squished surface itself (a DupBorder curve does not know the 3D)"
    link = Link(flat)
    near = ON_MM * mm(doc)
    added, skipped = [], 0
    for oid in mark_ids:
        o = doc.Objects.FindId(oid)
        if o is None or not isinstance(o.Geometry, (Point, Curve, TextDot)):
            continue
        g, off = flatten(link, o.Geometry, tol)
        if off > near:
            skipped += 1
            continue
        a = o.Attributes.Duplicate()
        a.RemoveFromAllGroups()  # 3D groups do not belong on the 2D panel
        added.append(doc.Objects.Add(g, a))
    doc.Objects.UnselectAll()
    doc.Objects.Select(List[System.Guid](added))  # what was placed stays selected
    doc.Views.Redraw()
    return added, skipped


def main():
    doc = sc.doc
    ids = rs.GetObjects(u"Select the new marks on the 3D model (points, curves, TextDots)",
                        rs.filter.point | rs.filter.curve | rs.filter.textdot, preselect=True)
    if not ids:
        return
    flat = rs.GetObject(u"Select the squished 2D surface (Squish result)", rs.filter.surface | rs.filter.polysurface)
    if not flat or flat in ids:
        return
    r = transfer(doc, ids, flat, doc.ModelAbsoluteTolerance)
    if not isinstance(r, tuple):
        print(r)
        return
    added, skipped = r
    print(u"Squish To: %d marks placed%s" % (len(added), u"; %d skipped — farther than %g mm from this panel in 3D "
                                             u"(another panel, or the 3D model moved since Squish)" % (skipped, ON_MM)
                                             if skipped else u""))


if __name__ == "__main__":
    main()
