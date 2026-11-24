# -*- coding: utf-8 -*-
"""Panels — GhPython component, stage 2 of the workflow: flat pieces -> numbered panels P1, P2, P3…

A thin wrapper (scripts/parts/Panels.py stays as it is): the numbering order and the text placement are those of the
button (`Panels.classify` — rows top to bottom, left to right; `DotToPanelText.place_text` — the text inside the panel
in the top right corner, style PAT 14 mm unless another one was picked with the button's Style option).
The result is virtual — nothing stays in the Rhino document (the text is added by place_text, its geometry
is taken and the object removed again).

Inputs:
    Pieces : the flat pieces (Breps) from stage 1 (its `Out`; other geometry is ignored), List access, No Type Hint
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
    from Rhino.Geometry import Brep, Plane, BrepLoopType

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

    Panels, Labels, Names, Report = DataTree[object](), [], [], []
    if pieces:
        tol = rdoc.ModelAbsoluteTolerance
        outer, inner = [], []
        for b in pieces:
            loops = list(b.Faces[0].Loops)
            outer.append([l.To3dCurve() for l in loops if l.LoopType == BrepLoopType.Outer][0])
            inner.append([l.To3dCurve() for l in loops if l.LoopType == BrepLoopType.Inner])
        style = P.D.pts.label_style(rdoc, P.STYLE)
        attrs = rdoc.CreateDefaultAttributes()
        made = 0
        for n, (i, _) in enumerate(P.classify(outer, Plane.WorldXY, tol)):
            name = u"%s%d" % (P.PREFIX, n + 1)
            panel = GH_Path(n)
            Panels.Add(outer[i], panel)
            for h in inner[i]:
                Panels.Add(h, panel)
            tid = P.D.place_text(rdoc, name, outer[i], outer[i].GetBoundingBox(True).Max, style, attrs, tol)
            if tid:
                Labels.append(rdoc.Objects.FindId(tid).Geometry.Duplicate())
                rdoc.Objects.Delete(tid, True)
            else:
                Labels.append(None)
                warn(u"%s: text does not fit in the panel" % name)
            Names.append(name)
            made += 1
        Report.append(u"Panels: %d (%s)" % (made, u", ".join(u"%s holes %d" % (nm, len(inner[i])) for nm, (i, _) in zip(
            Names, P.classify(outer, Plane.WorldXY, tol)) if inner[i]) or u"no holes"))
    else:
        warn(u"No pieces: connect the Out of the SquishJoined component")
