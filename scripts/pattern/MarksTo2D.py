# -*- coding: utf-8 -*-
"""Marks To 2D — new marks drawn on the 3D panel (points, curves, TextDots: a button, a zip…) onto its 2D panel
that was already squished and worked on (moved, turned, mirrored, edges changed).
Select the 3D panel surface together with the new marks on it, then the 2D panel (closed curve or flat surface).
The surface is squished again in memory (Squish, default settings — the same as the command) with the marks along;
Squish gives the same result every time, so the fresh outline is the old one, only moved. It is fitted onto the 2D
panel (turned, moved, mirrored if needed; the fit counts only the best 70 % of the outline — edges changed since
do not spoil it) and only the marks are added there, with the layer of their 3D originals.
A symmetric panel fits several ways — option Next shows the next fit, Enter keeps the one shown.
"""
import math

import Rhino
import rhinoscriptsyntax as rs
import System
import scriptcontext as sc
from Rhino.Geometry import (AreaMassProperties, Brep, Curve, Plane, Point, Point3d, SquishParameters, Squisher,
                            TextDot, Transform, Vector3d)
from System.Collections.Generic import List

ON_MM = 5.0  # a mark farther than this from the 3D surface is skipped
FIT_MM = 2.0  # fits within this of the best (median distance) are equally good: Next cycles them
KEEP = 0.7  # the fit uses the closest 70 % of the outline points


def mm(doc):
    return Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)


def outline(geo):
    """Outer contour of a closed curve or of a (one-face) flat surface, else None."""
    if isinstance(geo, Curve):
        return geo if geo.IsClosed else None
    if isinstance(geo, Brep) and geo.Faces.Count == 1:
        return geo.Faces[0].OuterLoop.To3dCurve()
    return None


def samples(crv, n):
    return [crv.PointAt(t) for t in crv.DivideByCount(n, True)]


def gap(crv, p):
    return crv.PointAt(crv.ClosestPoint(p)[1]).DistanceTo(p)


def median(ds):
    return sorted(ds)[len(ds) // 2]


def refine(xf, pts, crv, tol, steps=100):
    """Trimmed ICP: turn + move xf so that pts (moved by xf) sit on crv; the farthest 30 % are left out."""
    for _ in range(steps):
        a = [xf * p for p in pts]
        b = [crv.PointAt(crv.ClosestPoint(q)[1]) for q in a]
        d = [q.DistanceTo(r) for q, r in zip(a, b)]
        cut = sorted(d)[int(len(d) * KEEP)]
        pairs = [(q, r) for q, r, e in zip(a, b, d) if e <= cut]
        ca = Point3d(sum(q.X for q, _ in pairs) / len(pairs), sum(q.Y for q, _ in pairs) / len(pairs), 0)
        cb = Point3d(sum(r.X for _, r in pairs) / len(pairs), sum(r.Y for _, r in pairs) / len(pairs), 0)
        s = sum((q.X - ca.X) * (r.Y - cb.Y) - (q.Y - ca.Y) * (r.X - cb.X) for q, r in pairs)
        c = sum((q.X - ca.X) * (r.X - cb.X) + (q.Y - ca.Y) * (r.Y - cb.Y) for q, r in pairs)
        ang = math.atan2(s, c)
        xf = Transform.Translation(cb - ca) * Transform.Rotation(ang, Vector3d.ZAxis, ca) * xf
        if abs(ang) < 1e-9 and ca.DistanceTo(cb) < tol * 1e-3:
            break
    return xf


def fits(src, dst, tol, good):
    """Rigid fits (turn, move, mirror) of closed curve src onto closed curve dst, both flat in world XY:
    [(median distance, Transform)], best first, only those within good of the best, one per distinct fit."""
    ca, cd = AreaMassProperties.Compute(src).Centroid, AreaMassProperties.Compute(dst).Centroid
    coarse, fine = samples(src, 48), samples(src, 240)
    cands = []
    for flip in (False, True):
        m = Transform.Mirror(Plane(ca, Vector3d.XAxis)) if flip else Transform.Identity
        for k in range(0, 360, 3):  # ponytail: brute sweep 120 turns × 2; fine for panels (≈ 12k closest points)
            xf = Transform.Translation(cd - ca) * Transform.Rotation(math.radians(k), Vector3d.ZAxis, ca) * m
            cands.append((median([gap(dst, xf * p) for p in coarse]), xf))
    cands.sort(key=lambda c: c[0])
    out = []
    for _, xf in cands[:8]:
        xf = refine(xf, fine, dst, tol)
        q = [xf * p for p in fine[::40]]
        if any(all(a.DistanceTo(b) < good for a, b in zip(q, [f * p for p in fine[::40]])) for _, f in out):
            continue  # the same fit found from another start
        out.append((median([gap(dst, xf * p) for p in fine]), xf))
    out.sort(key=lambda f: f[0])
    return [f for f in out if f[0] <= out[0][0] + good]


def squish(face, marks):
    """Squished face (Brep in world XY) and the marks squished along it, same order (None — one failed)."""
    sq = Squisher()
    geos = List[Rhino.Geometry.GeometryBase]()
    for g in marks:
        geos.Add(g)
    res = List[Rhino.Geometry.GeometryBase]()
    flat = sq.SquishSurface(SquishParameters.Default, face, geos, res)
    out = list(res)
    return flat, out if len(out) == len(marks) else None


def on_surface(brep, geo, near):
    if isinstance(geo, Point):
        pts = [geo.Location]
    elif isinstance(geo, TextDot):
        pts = [geo.Point]
    else:
        pts = [geo.PointAtStart, geo.PointAtEnd, geo.PointAt(geo.Domain.Mid)]
    return all(brep.ClosestPoint(p).DistanceTo(p) <= near for p in pts)


def transfer(doc, srf_id, mark_ids, panel_id, tol):
    """(place, medians, skipped) or why not (a message). place(i) puts the marks by fit i (taking back the ones
    placed before) and returns their ids; medians — outline distance of each fit, best first; skipped — off the surface."""
    brep = rs.coercebrep(srf_id)
    if brep is None or brep.Faces.Count != 1:
        return u"The 3D panel must be one surface (polysurface: ExtractSrf first)"
    near = ON_MM * mm(doc)
    objs = [doc.Objects.FindId(i) for i in mark_ids]
    objs = [o for o in objs if o and isinstance(o.Geometry, (Point, Curve, TextDot))]
    on = [o for o in objs if on_surface(brep, o.Geometry, near)]
    if not on:
        return u"No marks on the surface (within %g mm): Pull them onto it first" % ON_MM
    flat, res = squish(brep.Faces[0], [o.Geometry for o in on])
    if flat is None or res is None:
        return u"Squish failed on this surface"
    src = flat.Faces[0].OuterLoop.To3dCurve()
    dst = outline(doc.Objects.FindId(panel_id).Geometry).DuplicateCurve()
    ok, plane = dst.TryGetPlane(tol)
    if not ok:
        return u"The 2D panel is not flat"
    dst.Transform(Transform.PlaneToPlane(plane, Plane.WorldXY))
    back = Transform.PlaneToPlane(Plane.WorldXY, plane)
    found = fits(src, dst, tol, FIT_MM * mm(doc))
    added = []

    def place(i):
        for oid in added:
            doc.Objects.Delete(oid, True)
        del added[:]
        xf = back * found[i][1]
        for o, g in zip(on, res):
            g = g.Duplicate()
            g.Transform(xf)
            a = o.Attributes.Duplicate()
            a.RemoveFromAllGroups()  # 3D groups do not belong on the 2D panel
            added.append(doc.Objects.Add(g, a))
        doc.Objects.UnselectAll()
        doc.Objects.Select(List[System.Guid](added))  # what was placed stays selected
        doc.Views.Redraw()
        return list(added)

    return place, [f[0] for f in found], len(objs) - len(on)


HELP = u"""Select the 3D surface with the new marks on it, then the 2D panel → the marks squished and placed on the panel
  Next — the panel fits several ways (symmetric): show the next fit; Enter — keep the one shown"""  # printed at start


def main():
    print(HELP)
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    ids = rs.GetObjects(u"Select the 3D panel surface and the new marks on it (points, curves, TextDots)",
                        rs.filter.surface | rs.filter.point | rs.filter.curve | rs.filter.textdot, preselect=True)
    if not ids:
        return
    srfs = [i for i in ids if rs.IsSurface(i)]
    if len(srfs) != 1:
        print(u"Select exactly one 3D surface (got %d)" % len(srfs))
        return
    panel = rs.GetObject(u"Select the 2D panel (closed curve or flat surface)", rs.filter.curve | rs.filter.surface)
    if not panel or outline(rs.coercegeometry(panel)) is None:
        return
    r = transfer(doc, srfs[0], [i for i in ids if i != srfs[0]], panel, tol)
    if not isinstance(r, tuple):
        print(r)
        return
    place, meds, skipped = r
    k = mm(doc)
    if skipped:
        print(u"Skipped %d marks: farther than %g mm from the surface (Pull them onto it)" % (skipped, ON_MM))
    i = 0
    while True:
        n = len(place(i))
        print(u"Fit %d of %d: outline off by %.1f mm (median); %d marks placed" % (i + 1, len(meds), meds[i] / k, n))
        if len(meds) == 1:
            break
        gs = Rhino.Input.Custom.GetOption()
        gs.SetCommandPrompt(u"Fit %d of %d (symmetric panel) — Enter keeps it" % (i + 1, len(meds)))
        gs.AcceptNothing(True)
        gs.AddOption("Next")
        if gs.Get() != Rhino.Input.GetResult.Option:
            break
        i = (i + 1) % len(meds)


if __name__ == "__main__":
    main()
