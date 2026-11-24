# -*- coding: utf-8 -*-
"""SquishJoined — GhPython component, stage 1 of the workflow: 3D surfaces -> flat pieces laid out joined.

A thin wrapper: scripts/pattern/SquishJoined.py is imported and its run() is called, nothing is copied
(the button script stays exactly as it is). The result is virtual: run() adds the pieces to the document,
the wrapper takes their geometry and deletes them again, so nothing is baked.

Inputs (all but Surfaces and Centre are optional — the defaults are those of the button):
    Surfaces        : surfaces / polysurfaces referenced from Rhino (Set Multiple), List access, No Type Hint
    Centre          : Point3d, centre of the layout (default 0,0,0)
    Run             : bool, True — squish
    Gap             : float, mm, free space kept between the pieces (default 100 = 10 cm; 0 — as the button lays them out)
    SplitSeams, PreserveBoundary, Rigid, Down, Diff : bool
    Deformation     : Free / StretchMostly / StretchOnly / CompressMostly / CompressOnly / Custom
    BndStretch, BndCompress, IntStretch, IntCompress : float (Custom)
Outputs:
    Out    : the pieces (and Diff dots) as geometry — nothing stays in the Rhino document (not baked)
    Report : the lines the button prints
"""
import os
import sys

ROOT = u"/Users/dmytro/Documents/Projects/Rhino"  # used when the .gh is not saved next to the project


def option_names():
    return ("SplitSeams", "PreserveBoundary", "Deformation", "BndStretch", "BndCompress", "IntStretch",
            "IntCompress", "Rigid", "Down", "Diff")


def outline(brep):
    """outer closed curve of a flat piece"""
    from Rhino.Geometry import Curve
    c = Curve.JoinCurves(brep.Faces[0].OuterLoop.To3dCurve().DuplicateSegments() or [brep.Faces[0].OuterLoop.To3dCurve()])
    return c[0] if c else brep.Faces[0].OuterLoop.To3dCurve()


def clearance(a, b, tol):
    """distance between two closed planar curves, -1 if they cross or one lies inside the other"""
    import Rhino
    from Rhino.Geometry import Plane, Curve
    from Rhino.Geometry.Intersect import Intersection
    if Intersection.CurveCurve(a, b, tol, tol).Count > 0:
        return -1.0
    rel = Curve.PlanarClosedCurveRelationship(a, b, Plane.WorldXY, tol)
    if rel != Rhino.Geometry.RegionContainment.Disjoint:
        return -1.0
    ok, pa, pb = a.ClosestPoints(b)
    return pa.DistanceTo(pb) if ok else 0.0


def spread(pieces, gap, tol, step=50.0, rounds=400):
    """moves the flat pieces (Breps, list order) apart until every two are `gap` clear of each other: the biggest stays,
    the others in the order of their area are pushed away from the pieces already placed (from their centres).
    Returns (translation vectors per piece, number of pairs still too close)"""
    from Rhino.Geometry import AreaMassProperties, Vector3d
    n = len(pieces)
    area = [AreaMassProperties.Compute(b).Area for b in pieces]
    curves = [outline(b) for b in pieces]
    centre = [AreaMassProperties.Compute(b).Centroid for b in pieces]
    move = [Vector3d(0, 0, 0) for _ in pieces]
    order = sorted(range(n), key=lambda i: -area[i])
    placed = order[:1]
    for i in order[1:]:
        for _ in range(rounds):
            push = Vector3d(0, 0, 0)
            worst = 0.0
            for q in placed:
                c = clearance(curves[i], curves[q], tol)
                if c < 0 or c < gap:
                    away = (centre[i] + move[i]) - (centre[q] + move[q])
                    away.Z = 0
                    if away.Length < tol:
                        away = Vector3d(1, 0, 0)
                    away.Unitize()
                    push += away
                    worst = max(worst, step if c < 0 else gap - c + tol)
            if worst == 0.0:
                break
            if push.Length < tol:
                push = Vector3d(1, 0, 0)
            push.Unitize()
            v = push * worst
            curves[i].Translate(v)
            move[i] += v
        placed.append(i)
    left = sum(1 for a in range(n) for b in range(a + 1, n)
               if not clearance(curves[a], curves[b], tol) >= gap - tol)  # -1 (overlap) counts too
    return move, left


if "ghenv" in globals():
    import Rhino
    import Grasshopper
    from Rhino.Geometry import Point3d

    comp = ghenv.Component
    rdoc = Rhino.RhinoDoc.ActiveDoc
    warn = lambda text: comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning, text)

    path = comp.OnPingDocument().FilePath
    root = os.path.dirname(os.path.dirname(path)) if path and os.path.isdir(
        os.path.join(os.path.dirname(os.path.dirname(path)), "scripts")) else ROOT
    pattern = os.path.join(root, "scripts", "pattern")
    for p in (pattern, os.path.join(root, "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import SquishJoined as SJ

    def value(name):
        """first value wired to the input `name` (read from the data itself — no type hint needed), None if empty"""
        for prm in comp.Params.Input:
            if prm.NickName == name:
                for d in prm.VolatileData.AllData(True):
                    return d.ScriptVariable()
        return None

    ids = []
    for prm in comp.Params.Input:
        if prm.NickName == "Surfaces":
            for d in prm.VolatileData.AllData(True):
                if d.IsReferencedGeometry and d.ReferenceID not in ids:
                    ids.append(d.ReferenceID)
    opts = {}
    for n in option_names():
        if value(n) is not None:
            opts[n] = value(n)
    centre = value("Centre") or Point3d(0, 0, 0)

    Out, Report = [], []
    if value("Run"):
        if not ids:
            warn(u"No surfaces: set Surfaces from Rhino")
        else:
            r = SJ.run(rdoc, ids, centre, opts=opts)
            if isinstance(r, tuple):
                Report = list(r[1])
                groups = set()
                for i in r[0]:  # virtual: the geometry is taken from the pieces run() added, then they are removed
                    o = rdoc.Objects.FindId(i)
                    Out.append(o.Geometry.Duplicate())
                    groups.update(o.Attributes.GetGroupList())
                    rdoc.Objects.Delete(i, True)
                for gi in groups:
                    rdoc.Groups.Delete(gi)
                gap = value("Gap")
                gap = 100.0 if gap is None else float(gap)
                k = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, rdoc.ModelUnitSystem)
                if gap > 0:
                    tol = rdoc.ModelAbsoluteTolerance
                    pieces = [g for g in Out if isinstance(g, Rhino.Geometry.Brep)]
                    dots = [g for g in Out if isinstance(g, Rhino.Geometry.TextDot)]
                    # run() makes the Diff dots piece by piece, one per side longer than 10 tolerances
                    owner = []
                    for i in ids:
                        for f in rdoc.Objects.FindId(i).Geometry.Faces:
                            owner.append(sum(1 for e in f.DuplicateFace(False).Edges if e.GetLength() > 10 * tol))
                    mine = []
                    matched = len(dots) == sum(owner) and len(owner) == len(pieces)
                    if matched:
                        for n, cnt in enumerate(owner):
                            mine.extend([n] * cnt)
                    elif dots:
                        warn(u"Diff dots could not be matched to the pieces: they stay where they are")
                    move, left = spread(pieces, gap * k, tol)
                    for n, v in enumerate(move):
                        pieces[n].Translate(v)
                    for d, n in zip(dots, mine):  # empty when not matched
                        d.Translate(move[n])
                    bb = Rhino.Geometry.BoundingBox.Empty
                    for g in pieces:
                        bb.Union(g.GetBoundingBox(True))
                    back = centre - bb.Center
                    back.Z = 0
                    for g in Out:
                        g.Translate(back)
                    Report.append(u"  Gap %g mm: %d pieces moved apart%s" % (gap, sum(1 for v in move if v.Length > 0),
                                  u"" if not left else u" — %d pairs still closer than the gap" % left))
                    if left:
                        warn(u"%d pairs of pieces are still closer than Gap" % left)
            else:
                warn(r)
                Report = [r]
            rdoc.Views.Redraw()
