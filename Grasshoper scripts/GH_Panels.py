# -*- coding: utf-8 -*-
"""Panels — GhPython component, stage 2 of the workflow: flat pieces -> numbered panels P1, P2, P3…

A thin wrapper (scripts/parts/Panels.py stays as it is): the numbering order is the button's (`Panels.classify` —
rows top to bottom, left to right), the text style too (PAT 14 mm unless another one was picked with the button's Style
option). The text stands in the middle of the panel (centre of its area), moved by LabelDX to the left — the middle
itself stays free for drawing. The result is virtual — nothing is added to the Rhino document.

Inputs:
    Pieces  : the flat pieces (Breps) from stage 1 (its `Out`; other geometry is ignored), List access, No Type Hint
    LabelDX : float, mm — the text is moved this far along X from the panel centre (default -100 = 10 cm to the left)
Outputs:
    Panels : tree, branch {i} = panel P<i+1>: its outer curve, then its holes (inner loops)
    Labels : the text P<n> of each panel (text geometry), in the same order
    Names  : P1, P2…
    Report : what was done
"""
import os
import sys

ROOT = u"/Users/dmytro/Documents/Projects/Rhino"  # used when the .gh is not saved next to the project


if "ghenv" in globals():
    import Rhino
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path
    from Rhino.Geometry import AreaMassProperties, Brep, BrepLoopType, Plane, PointContainment, TextEntity, Vector3d
    from Rhino.DocObjects import TextHorizontalAlignment, TextVerticalAlignment

    comp = ghenv.Component
    rdoc = Rhino.RhinoDoc.ActiveDoc
    warn = lambda text: comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning, text)

    path = comp.OnPingDocument().FilePath
    root = os.path.dirname(os.path.dirname(path)) if path and os.path.isdir(
        os.path.join(os.path.dirname(os.path.dirname(path)), "scripts")) else ROOT
    for p in (os.path.join(root, "scripts", "parts"), os.path.join(root, "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import Panels as P

    pieces = []
    for prm in comp.Params.Input:
        if prm.NickName == "Pieces":
            for d in prm.VolatileData.AllData(True):
                g = d.ScriptVariable()
                if isinstance(g, Brep) and g.Faces.Count == 1:
                    pieces.append(g)

    dx = -100.0
    for prm in comp.Params.Input:
        if prm.NickName == "LabelDX":
            for d in prm.VolatileData.AllData(True):
                dx = float(d.ScriptVariable())
    k = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, rdoc.ModelUnitSystem)
    Panels, Labels, Names, Report = DataTree[object](), [], [], []
    if pieces:
        tol = rdoc.ModelAbsoluteTolerance
        outer, inner = [], []
        for b in pieces:
            loops = list(b.Faces[0].Loops)
            outer.append([l.To3dCurve() for l in loops if l.LoopType == BrepLoopType.Outer][0])
            inner.append([l.To3dCurve() for l in loops if l.LoopType == BrepLoopType.Inner])
        style = P.D.pts.label_style(rdoc, P.STYLE)
        made = 0
        for n, (i, _) in enumerate(P.classify(outer, Plane.WorldXY, tol)):
            name = u"%s%d" % (P.PREFIX, n + 1)
            panel = GH_Path(n)
            Panels.Add(outer[i], panel)
            for h in inner[i]:
                Panels.Add(h, panel)
            c = AreaMassProperties.Compute(pieces[i]).Centroid + Vector3d(dx * k, 0, 0)
            if outer[i].Contains(c, Plane.WorldXY, tol) != PointContainment.Inside:
                warn(u"%s: the label spot is outside the panel (LabelDX too big, or a curved panel)" % name)
            te = TextEntity()
            te.PlainText = name
            te.Plane = Plane(c, Vector3d.ZAxis)
            te.DimensionStyleId = style.Id
            te.TextHorizontalAlignment = TextHorizontalAlignment.Center
            te.TextVerticalAlignment = TextVerticalAlignment.Middle
            Labels.append(te)
            Names.append(name)
            made += 1
        Report.append(u"Panels: %d (%s)" % (made, u", ".join(u"%s holes %d" % (nm, len(inner[i])) for nm, (i, _) in zip(
            Names, P.classify(outer, Plane.WorldXY, tol)) if inner[i]) or u"no holes"))
    else:
        warn(u"No pieces: connect the Out of the SquishJoined component")
