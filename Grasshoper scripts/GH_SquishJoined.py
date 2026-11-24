# -*- coding: utf-8 -*-
"""SquishJoined — GhPython component, stage 1 of the workflow: 3D surfaces -> flat pieces laid out joined.

A thin wrapper: scripts/pattern/SquishJoined.py is imported and its run() is called, nothing is copied
(the button script stays exactly as it is). The result is virtual: run() adds the pieces to the document,
the wrapper takes their geometry and deletes them again, so nothing is baked.

Inputs (all but Surfaces and Centre are optional — the defaults are those of the button):
    Surfaces        : surfaces / polysurfaces referenced from Rhino (Set Multiple), List access, No Type Hint
    Centre          : Point3d, centre of the layout (default 0,0,0)
    Run             : bool, True — squish
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
                Report = r[1]
                groups = set()
                for i in r[0]:  # virtual: the geometry is taken from the pieces run() added, then they are removed
                    o = rdoc.Objects.FindId(i)
                    Out.append(o.Geometry.Duplicate())
                    groups.update(o.Attributes.GetGroupList())
                    rdoc.Objects.Delete(i, True)
                for gi in groups:
                    rdoc.Groups.Delete(gi)
            else:
                warn(r)
                Report = [r]
            rdoc.Views.Redraw()
