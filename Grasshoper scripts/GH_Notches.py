# -*- coding: utf-8 -*-
"""Notches — GhPython component, stage 4 of the workflow: panel edges -> notch points on the sew line.

A thin wrapper (scripts/pattern/Notches.py stays as it is): the places are counted by its `positions`, mode Repeat —
one notch at the middle of the edge, then every Every both ways to the corners. Virtual: the notches are points in the
preview, nothing is added to the Rhino document (Convert Notches into pen / knife notches is a later stage).

The edges come from the Seams component, already numbered (1 top, 2 right, 3 bottom, 4 left). Default: notches on the
top and bottom edges, none on the sides (a panel with another number of edges: none on the edges facing more along X
than along Y). To change single edges press Build — one toggle per edge is made below the component (a column per
panel, N1.1, N1.2… = notches of panel 1, edge 1…), set to the default, grouped (`Notch edges`) and wired to On in that
order; an old set is replaced. Press Build again after the panels change.

Inputs:
    Edges : the `Edges` output of the Seams component (tree, branch {i} = panel P<i+1>), Tree access
    Every : cm, the step from the middle of the edge (default 30)
    Build : button, makes the toggles
    On    : bool, one per edge in the order N1.1, N1.2… N2.1… (the toggles), List access
Outputs:
    Points : tree, branch {i} = the notch points of panel P<i+1>
    Report : notches per edge, problems
"""
import os
import sys

ROOT = u"/Users/dmytro/Documents/Projects/Rhino"  # used when the .gh is not saved next to the project


if "ghenv" in globals():
    import Rhino
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path
    from Rhino.Geometry import Point

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
    import Notches as N

    def data(name):
        for prm in comp.Params.Input:
            if prm.NickName == name:
                return prm.VolatileData
        return None

    def values(name):
        d = data(name)
        return [g.ScriptVariable() for g in (d.AllData(True) if d else [])]

    every_cm = float((values("Every") or [30.0])[0])
    on = [bool(v) for v in values("On")]
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, rdoc.ModelUnitSystem)
    opts = dict(N.DEFAULTS)
    opts["every"] = every_cm * 10.0 * mm

    Points, Report = DataTree[object](), []
    found = []  # (name, panel, edge index, default) of every edge — for the Build button
    taken = 0
    tree = data("Edges")
    if tree is None or tree.PathCount == 0:
        warn(u"No edges: connect the Edges output of the Seams component")
    else:
        if every_cm <= 0:
            warn(u"Every must be above 0")
        for b in range(tree.PathCount):
            index = tree.Paths[b].Indices[tree.Paths[b].Length - 1]
            n = index + 1  # P<n>
            edges = [g.ScriptVariable() for g in tree.Branches[b]]
            counts = []
            for j, e in enumerate(edges):
                dx, dy = e.PointAtEnd.X - e.PointAtStart.X, e.PointAtEnd.Y - e.PointAtStart.Y
                is_side = j in (1, 3) if len(edges) == 4 else abs(dy) > abs(dx)  # as in the Seams component
                default = not is_side
                use = on[taken] if taken < len(on) else default
                taken += 1
                found.append((u"N%d.%d" % (n, j + 1), n, j, default))
                made = 0
                if use and every_cm > 0:
                    length = e.GetLength()
                    for s in N.positions(length, "Repeat", 0.0, opts):
                        ok, t = e.LengthParameter(s)
                        if ok:
                            Points.Add(Point(e.PointAt(t)), GH_Path(index))
                            made += 1
                counts.append(made)
            Report.append(u"P%d: notches per edge %s" % (n, u" ".join(u"%d" % c for c in counts)))

        if (values("Build") or [False])[0] is True:
            from System.Drawing import PointF, Color
            from Grasshopper.Kernel import GH_Document
            from Grasshopper.Kernel.Special import GH_BooleanToggle, GH_Group
            doc = comp.OnPingDocument()
            onparam = [q for q in comp.Params.Input if q.NickName == "On"][0]
            TAG = u"NotchEdge"

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
                x0, y0 = comp.Attributes.Pivot.X - 350, comp.Attributes.Pivot.Y + 180  # below, a column per panel
                group = GH_Group()
                group.NickName = u"Notch edges"
                group.Description = TAG
                group.Colour = Color.FromArgb(120, 140, 200, 240)
                for name, n, j, default in found:
                    t = GH_BooleanToggle()
                    t.CreateAttributes()
                    t.Attributes.Pivot = PointF(x0 + (n - 1) * 230, y0 + j * 26)
                    t.Value = default
                    t.NickName = name
                    t.Description = u"%s %s: notches on edge %d of panel P%d" % (TAG, name, j + 1, n)
                    d.AddObject(t, False)
                    onparam.AddSource(t)
                    group.AddObject(t.InstanceGuid)
                d.AddObject(group, False)
                group.ExpireCaches()
                comp.ExpireSolution(False)

            doc.ScheduleSolution(5, GH_Document.GH_ScheduleDelegate(make))
        if on and len(on) != taken:
            warn(u"On has %d values, the panels have %d edges (press Build)" % (len(on), taken))
