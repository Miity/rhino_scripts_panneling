# -*- coding: utf-8 -*-
"""SquishTo — GhPython component: the marks drawn on the 3D surfaces onto the flat pieces of the squish stage.

The job of scripts/pattern/SquishTo.py for the virtual pieces. The button needs the squished surface in the document;
here each face is squished again the way `SquishJoined.squish` does it (same options — Squish gives the same result
every time) and a mark is mapped with that squish (3D mesh -> the same spot of the 2D mesh), then moved the way the
finished piece was moved (joined layout, Gap, centre): the move is read off the piece itself, nothing is guessed.

Which face: a mark lying wholly within Reach of a face goes to that face — to both if it lies on both (a seam);
a curve that runs from face to face is cut where the nearest face changes. Curves come as polylines (a point every
10 mm or less), like Squish's own.

Inputs:
    Surfaces : the same surfaces as the SquishJoined component (referenced from Rhino), List access
    Pieces   : the `Out` of the SquishJoined component, List access
    Marks    : points / curves / TextDots referenced from Rhino (optional; empty — every visible, unlocked point,
               curve and TextDot of the document lying on the surfaces, as the button takes them), List access
    Reach    : mm, how far a mark may be from a surface (default 5)
    SplitSeams, PreserveBoundary, Deformation, BndStretch, BndCompress, IntStretch, IntCompress, Rigid :
               wire the same controls as the SquishJoined component
Outputs:
    Marks2D : tree, branch {i} = the marks on panel P<i+1>
    Report  : what was placed, what was left out
"""
import os
import sys

ROOT = u"/Users/dmytro/Documents/Projects/Rhino"  # used when the .gh is not saved next to the project
STEP_MM = 10.0  # a point of a flat curve at least this often
SEAM_MM = 1.0  # a mark this close to a second face too lies on the seam: it goes to both


if "ghenv" in globals():
    import Rhino
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path
    from Rhino.Geometry import (Brep, BrepLoopType, Curve, Plane, Point, Point3d, PolylineCurve, TextDot,
                                Transform)

    comp = ghenv.Component
    rdoc = Rhino.RhinoDoc.ActiveDoc
    warn = lambda text: comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning, text)

    path = comp.OnPingDocument().FilePath
    root = os.path.dirname(os.path.dirname(path)) if path and os.path.isdir(
        os.path.join(os.path.dirname(os.path.dirname(path)), "scripts")) else ROOT
    for p in (os.path.join(root, "scripts", "pattern"), os.path.join(root, "scripts", "parts"),
              os.path.join(root, "scripts", "markup"), os.path.join(root, "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import SquishJoined as SJ
    import Panels as P

    def params_of(name):
        return [prm for prm in comp.Params.Input if prm.NickName == name]

    def goos(name):
        return [g for prm in params_of(name) for g in prm.VolatileData.AllData(True)]

    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, rdoc.ModelUnitSystem)
    tol = rdoc.ModelAbsoluteTolerance
    reach_in = goos("Reach")
    reach = (float(reach_in[0].ScriptVariable()) if reach_in else 5.0) * mm

    ids = []
    for g in goos("Surfaces"):
        if g.IsReferencedGeometry and g.ReferenceID not in ids:
            ids.append(g.ReferenceID)
    faces = []  # in the order SquishJoined.run lays them out
    for i in ids:
        for f in rdoc.Objects.FindId(i).Geometry.Faces:
            faces.append(f.DuplicateFace(False))
    pieces = [x for x in (g.ScriptVariable() for g in goos("Pieces")) if isinstance(x, Brep)]

    opts = dict(SJ.DEFAULTS)
    for key in ("SplitSeams", "PreserveBoundary", "Deformation", "BndStretch", "BndCompress", "IntStretch",
                "IntCompress", "Rigid"):
        v = goos(key)
        if v:
            opts[key] = v[0].ScriptVariable()

    Marks2D, Report = DataTree[object](), []

    def distance(n, p):
        return faces[n].ClosestPoint(p).DistanceTo(p)

    def samples(geo):
        """3D points of a mark: one, or along a curve every STEP_MM at most"""
        if isinstance(geo, Point):
            return [geo.Location]
        if isinstance(geo, TextDot):
            return [geo.Point]
        count = max(2, int(geo.GetLength() / (STEP_MM * mm)) + 1)
        pts = [geo.PointAt(t) for t in geo.DivideByCount(count, True)]
        ok, poly = geo.TryGetPolyline()  # its corners stay exactly
        if ok:
            ts = list(geo.DivideByCount(count, True))
            for corner in poly:
                ts.append(geo.ClosestPoint(corner)[1])
            pts = [geo.PointAt(t) for t in sorted(set(ts))]
        return pts

    def wanted():
        """[(geometry)] — the wired marks, or every visible mark of the document that is wholly on the surfaces"""
        wired = [g.ScriptVariable() for g in goos("Marks")]
        wired = [Point(g) if isinstance(g, Point3d) else g for g in wired]
        if params_of("Marks") and params_of("Marks")[0].SourceCount + len(wired):
            return [g for g in wired if isinstance(g, (Point, Curve, TextDot))], True
        s = Rhino.DocObjects.ObjectEnumeratorSettings()
        s.HiddenObjects = False
        s.LockedObjects = False
        found = []
        for o in rdoc.Objects.GetObjectList(s):
            layer = rdoc.Layers[o.Attributes.LayerIndex]
            g = o.Geometry
            if o.Id in ids or not layer.IsVisible or layer.IsLocked or not isinstance(g, (Point, Curve, TextDot)):
                continue
            if all(min(distance(n, p) for n in range(len(faces))) <= reach for p in samples(g)):
                found.append(g)
        return found, False

    if not faces or len(pieces) != len(faces):
        warn(u"Connect Surfaces (as the SquishJoined component) and Pieces (its Out, with Run on)")
    else:
        flats = []  # (to2d, move from the fresh squish to the finished piece)
        for n, f in enumerate(faces):
            r = SJ.squish(f.Faces[0], SJ.params(opts))
            if r is None:
                warn(u"Squish failed on face %d" % (n + 1))
                break
            flat, to2d = r
            a, b = flat.Faces[0], pieces[n].Faces[0]
            u, v = a.Domain(0), a.Domain(1)
            uv = [(u.T0, v.T0), (u.T1, v.T0), (u.T0, v.T1), (u.T1, v.T1)]
            src = [a.PointAt(*q) for q in uv]
            dst = [b.PointAt(*q) for q in uv]  # the finished piece is the same surface, only moved
            move = Transform.PlaneToPlane(Plane(src[0], src[1], src[2]), Plane(dst[0], dst[1], dst[2]))
            if (move * src[3]).DistanceTo(dst[3]) > 1.0 * mm:
                warn(u"Piece %d is not this squish: wire the same options as the SquishJoined component" % (n + 1))
                break
            flats.append((to2d, move))
        if len(flats) == len(faces):
            outer = [[l.To3dCurve() for l in b.Faces[0].Loops if l.LoopType == BrepLoopType.Outer][0] for b in pieces]
            panel_of = {}  # face index -> panel index, numbered as the Panels component does
            for k, (i, _) in enumerate(P.classify(outer, Plane.WorldXY, tol)):
                panel_of[i] = k

            def put(n, geo, pts):
                to2d, move = flats[n]
                flat_pts = [move * to2d(p) for p in pts]
                if isinstance(geo, Point):
                    out = Point(flat_pts[0])
                elif isinstance(geo, TextDot):
                    out = TextDot(geo.Text, flat_pts[0])
                else:
                    out = PolylineCurve(flat_pts)
                Marks2D.Add(out, GH_Path(panel_of.get(n, n)))
                placed.append(panel_of.get(n, n))

            marks, wired = wanted()
            placed, skipped = [], 0
            for geo in marks:
                pts = samples(geo)
                far = [max(distance(n, p) for p in pts) for n in range(len(faces))]
                best = min(range(len(faces)), key=lambda n: far[n])
                if far[best] <= reach:  # wholly on one face — and on a second one if it lies on the seam with it
                    for n in range(len(faces)):
                        if n == best or far[n] <= SEAM_MM * mm:
                            put(n, geo, pts)
                    continue
                near = [min(range(len(faces)), key=lambda n: distance(n, p)) for p in pts]
                if isinstance(geo, Curve) and all(distance(n, p) <= reach for n, p in zip(near, pts)):
                    start = 0
                    for k in range(1, len(pts) + 1):  # cut where the nearest face changes
                        if k == len(pts) or near[k] != near[start]:
                            if k - start > 1:
                                put(near[start], geo, pts[start:k])
                            start = k
                else:
                    skipped += 1
            Report.append(u"Marks: %d %s -> %d on the panels%s" % (
                len(marks), u"wired" if wired else u"found on the surfaces", len(placed),
                u"; %d skipped (farther than %g mm from the surfaces)" % (skipped, reach / mm) if skipped else u""))
            for k in sorted(set(placed)):
                Report.append(u"P%d: %d" % (k + 1, placed.count(k)))
