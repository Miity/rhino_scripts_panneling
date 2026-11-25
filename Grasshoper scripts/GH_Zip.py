# -*- coding: utf-8 -*-
"""Zip — GhPython component, stage 6 of the workflow: zips between neighbouring panels (stops and number Z<n>).

A thin wrapper (scripts/parts/ZipStops.py stays as it is): the stops are its `zip_marks` (a leg across the edge, then
90° along it towards the middle), the number is placed by its `place_text` inside the panel. Virtual: nothing is added
to the Rhino document.

Panels are numbered from the top down, so a zip joins the bottom edge of P<k> (S<k>.3) and the top edge of P<k+1>
(S<k+1>.1). Both sides are the same length and centred on their edges (by length): the shorter edge minus Trim at
each end; on the longer edge the stops stand as far apart, around its middle.

Press Build — one toggle per pair of neighbouring panels is made below the component (`Zip 1-2`, `Zip 2-3`…, all off,
group `Zip pairs`) and wired to On in that order; an old set is replaced. Switched on pairs are numbered Z1, Z2… from
the top. ponytail: only a panel and the next one down — panels side by side in one row are not paired.

Inputs:
    Edges  : the `Edges` output of the Edges component, Tree access
    Trim   : cm, the stops this far in from the ends of the shorter edge (default 4)
    Size   : cm, length of the stop legs (optional, default 1)
    Build  : button, makes the toggles
    On     : bool, one per pair in the order 1-2, 2-3… (the toggles), List access
Outputs:
    Marks  : tree, branch {k} = the stops of zip Z<k+1>
    Labels : the numbers Z<n>, one on each side (text geometry)
    Report : lengths per zip, problems
"""
import os
import sys

ROOT = u"/Users/dmytro/Documents/Projects/Rhino"  # used when the .gh is not saved next to the project


if "ghenv" in globals():
    import Rhino
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path
    from Rhino.Geometry import Curve, Polyline, PolylineCurve, Vector3d

    comp = ghenv.Component
    rdoc = Rhino.RhinoDoc.ActiveDoc
    warn = lambda text: comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning, text)

    path = comp.OnPingDocument().FilePath
    root = os.path.dirname(os.path.dirname(path)) if path and os.path.isdir(
        os.path.join(os.path.dirname(os.path.dirname(path)), "scripts")) else ROOT
    for p in (os.path.join(root, "scripts", "parts"), os.path.join(root, "scripts", "markup"),
              os.path.join(root, "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import ZipStops as Z
    for m in ("GH_Edges",):  # the shared numbering rules; fresh after an edit
        sys.modules.pop(m, None)
    sys.path.insert(0, os.path.join(root, u"Grasshoper scripts"))
    import GH_Edges as E

    def data(name):
        for prm in comp.Params.Input:
            if prm.NickName == name:
                return prm.VolatileData
        return None

    def values(name):
        d = data(name)
        return [g.ScriptVariable() for g in (d.AllData(True) if d else [])]

    def branches(name):
        """{panel index: [geometry]} of a tree input; the panel is the last index of the path"""
        d, out = data(name), {}
        if d is not None:
            for b in range(d.PathCount):
                out[d.Paths[b].Indices[d.Paths[b].Length - 1]] = [g.ScriptVariable() for g in d.Branches[b]]
        return out

    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, rdoc.ModelUnitSystem)
    cm = 10.0 * mm
    tol = rdoc.ModelAbsoluteTolerance
    trim = float((values("Trim") or [4.0])[0]) * cm
    size = float((values("Size") or [1.0])[0]) * cm
    on = [bool(v) for v in values("On")]
    edges = branches("Edges")
    outlines = {}  # the panel is its edges joined back — what the number must stay inside
    for index, es in edges.items():
        joined = Curve.JoinCurves(es, 10 * tol)
        if len(joined) == 1 and joined[0].IsClosed:
            outlines[index] = joined[0]
        else:
            warn(u"P%d: the edges do not close into one outline" % (index + 1))

    Marks, Labels, Report = DataTree[object](), [], []
    if not edges:
        warn(u"Connect Edges (Edges component)")
    else:
        order = sorted(edges)
        pairs = [(a, b) for a, b in zip(order, order[1:]) if b == a + 1]
        style = Z.D.pts.label_style(rdoc, Z.STYLE)
        gap = 0.5 * style.TextHeight * style.DimensionScale
        up = Vector3d.ZAxis
        obstacles = []  # numbers and stops placed so far
        number = 0
        for index, (a, b) in enumerate(pairs):
            if not (index < len(on) and on[index]) or a not in outlines or b not in outlines:
                continue
            number += 1
            name = u"Z%d" % number
            k = E.bottom(edges[a])
            sides = [(a, k, edges[a][k]), (b, 0, edges[b][0])]  # (panel, edge, curve)
            shorter = min(e.GetLength() for _, _, e in sides)
            span = shorter - 2 * trim
            if span <= tol:
                warn(u"%s: an edge is shorter than 2 × Trim" % name)
                continue
            for panel, _, e in sides:
                end = (e.GetLength() - span) / 2.0  # centred on the edge
                s_c = e.GetLength() / 2.0
                te, corners, free, side = Z.place_text(name, e, outlines[panel], s_c, style, gap, up, tol, obstacles)
                if not free:
                    warn(u"%s on P%d: no free spot for the number" % (name, panel + 1))
                Labels.append(te)
                obstacles.append((PolylineCurve(Polyline(list(corners) + [corners[0]])).GetBoundingBox(True), None))
                for mark in Z.zip_marks(e, [end, end], [False, False], side, size, up):
                    Marks.Add(mark, GH_Path(number - 1))
                    obstacles.append((mark.GetBoundingBox(True), mark))
            Report.append(u"%s: S%d.%d + S%d.%d, zip %.1f cm (edges %.1f / %.1f cm)" % (
                name, a + 1, k + 1, b + 1, 1, span / cm, sides[0][2].GetLength() / cm, sides[1][2].GetLength() / cm))
        if not number:
            Report.append(u"No zips: switch a pair on (Build makes the toggles)")

        if (values("Build") or [False])[0] is True:
            from System.Drawing import PointF, Color
            from Grasshopper.Kernel import GH_Document
            from Grasshopper.Kernel.Special import GH_BooleanToggle, GH_Group
            doc = comp.OnPingDocument()
            onparam = [q for q in comp.Params.Input if q.NickName == "On"][0]
            TAG = u"ZipPair"
            names = [u"Zip %d-%d" % (a + 1, b + 1) for a, b in pairs]

            def make(d):
                gone = set()
                for o in list(d.Objects):
                    if isinstance(o, GH_BooleanToggle) and (o.Description or u"").startswith(TAG):
                        gone.add(o.InstanceGuid)
                        d.RemoveObject(o, False)
                for o in list(d.Objects):  # the groups of the old toggles go with them
                    if isinstance(o, GH_Group) and (o.Description == TAG or gone.intersection(o.ObjectIDs)):
                        d.RemoveObject(o, False)
                onparam.RemoveAllSources()
                x0, y0 = comp.Attributes.Pivot.X - 200, comp.Attributes.Pivot.Y + 180
                group = GH_Group()
                group.NickName = u"Zip pairs"
                group.Description = TAG
                group.Colour = Color.FromArgb(120, 170, 220, 140)
                for row, name in enumerate(names):
                    t = GH_BooleanToggle()
                    t.CreateAttributes()
                    t.Attributes.Pivot = PointF(x0, y0 + row * 26)
                    t.Value = False
                    t.NickName = name
                    t.Description = u"%s %s: bottom edge of the upper panel + top edge of the lower one" % (TAG, name)
                    d.AddObject(t, False)
                    onparam.AddSource(t)
                    group.AddObject(t.InstanceGuid)
                d.AddObject(group, False)
                group.ExpireCaches()
                comp.ExpireSolution(False)

            doc.ScheduleSolution(5, GH_Document.GH_ScheduleDelegate(make))
        if on and len(on) != len(pairs):
            warn(u"On has %d values, there are %d pairs of panels (press Build)" % (len(on), len(pairs)))
