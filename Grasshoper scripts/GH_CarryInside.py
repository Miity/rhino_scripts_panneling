# -*- coding: utf-8 -*-
"""CarryInside — GhPython component for autonest_v2.gh.

Everything that lies inside each Cut (INK, INT, texts, points, holes — any
visible object of the Rhino document, any layer) goes with the Cut to its
nested place: the Cut's own OpenNest transform is applied to a copy.

An object belongs to a Cut when its start, middle or end (point / text:
its centre) is inside the Cut or on its line; inside several Cuts — the
smallest one. Objects inside no Cut stay where they are.

A Cut that doesn't fit OpenNest puts on an extra copy of the sheet (IDS ≥
number of sheets): it is left out with a warning, the message counts the
placed ones ("11/12 placed").

Inputs:
    Cut  : the Cut curves referenced from Rhino — the same list OpenNest
           nests (Tree access)
    X    : Transform output of OpenNest (Tree access)
    Bake : Button — copies (Cut + everything inside) added to the Rhino
           document with their own layer / colour / linetype, one group per
           part, one undo
Outputs (one per layer, to bake each into its layer; branch {i} = Cut i):
    CUT   : moved Cut copies
    INK   : moved copies from layer INK
    INT   : moved copies from layer INT
    Other : moved copies from any other layer
    N     : "<cut>: <objects inside>" per Cut
"""


def find_nest(param):
    """OpenNest that feeds param, through relays."""
    for s in param.Sources:
        o = s.Attributes.GetTopLevel.DocObject
        if o.GetType().FullName.endswith("component_nest1"):
            return o
        if hasattr(o, "Sources"):
            o = find_nest(o)
            if o:
                return o
    return None


def owner(hits, areas):
    """Index of the Cut an object belongs to: the smallest Cut holding one of its points."""
    return min(hits, key=lambda i: areas[i]) if hits else None


if "ghenv" in globals():
    import Rhino
    import Rhino.Geometry as rg
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path

    LAYERS = ["CUT", "INK", "INT", "Other"]
    comp = ghenv.Component
    rdoc = Rhino.RhinoDoc.ActiveDoc
    tol = rdoc.ModelAbsoluteTolerance
    cuts = [rdoc.Objects.FindId(g.ReferenceID) for g in comp.Params.Input[0].VolatileData.AllData(True)]
    xdata = comp.Params.Input[1].VolatileData
    xforms = [list(xdata.Branches[i]) if i < xdata.PathCount else [] for i in range(len(cuts))]
    nest = find_nest(comp.Params.Input[1])
    off = set()
    if nest:
        sheet_of = nest.Params.Output[4].VolatileData
        sheets = nest.Params.Input[0].VolatileDataCount
        off = set(i for i in range(min(len(cuts), sheet_of.PathCount))
                  if sheet_of.Branches[i].Count and sheet_of.Branches[i][0].Value >= sheets)

    if not cuts or None in cuts:
        comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Error, "Cut must be curves referenced from Rhino")
    elif any(xforms):
        curves = [c.Geometry for c in cuts]
        boxes = [c.GetBoundingBox(True) for c in curves]
        for b in boxes:
            b.Inflate(tol)
        areas = [b.Area for b in boxes]

        def samples(geo):
            if isinstance(geo, rg.Curve):
                return [geo.PointAtStart, geo.PointAt(geo.NormalizedLengthParameter(0.5)[1]), geo.PointAtEnd]
            if isinstance(geo, rg.Point):
                return [geo.Location]
            return [geo.GetBoundingBox(True).Center]

        def holds(i, p):
            return boxes[i].Contains(p) and curves[i].Contains(p, rg.Plane.WorldXY, tol) != rg.PointContainment.Outside

        parts = [[c] for c in cuts]
        skip = set(c.Id for c in cuts)
        settings = Rhino.DocObjects.ObjectEnumeratorSettings()
        settings.HiddenObjects = False
        settings.LockedObjects = True
        settings.VisibleFilter = True
        for obj in rdoc.Objects.GetObjectList(settings):
            if obj.Id not in skip and obj.Attributes.Space == Rhino.DocObjects.ActiveSpace.ModelSpace:
                i = owner(set(i for p in samples(obj.Geometry) for i in range(len(cuts)) if holds(i, p)), areas)
                if i is not None:
                    parts[i].append(obj)

        out = dict((k, DataTree[object]()) for k in LAYERS)
        N = ["%d: %d" % (i, len(part) - 1) for i, part in enumerate(parts)]
        placed = inside = 0
        if Bake:
            rec = rdoc.BeginUndoRecord("CarryInside bake")
        for i, part in enumerate(parts):
            if len(xforms[i]) != 1 or i in off:
                comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning,
                                       "Cut %d didn't fit the sheet — left out" % i)
                continue
            placed += 1
            inside += len(part) - 1
            group = rdoc.Groups.Add() if Bake else None
            for obj in part:
                g = obj.Geometry.Duplicate()
                g.Transform(xforms[i][0].Value)
                top = rdoc.Layers[obj.Attributes.LayerIndex].FullPath.split("::")[0].upper()
                out[top if top in LAYERS else "Other"].Add(g, GH_Path(i))
                if Bake:
                    a = obj.Attributes.Duplicate()
                    a.RemoveFromAllGroups()
                    a.AddToGroup(group)
                    rdoc.Objects.Add(g, a)
        if Bake:
            rdoc.EndUndoRecord(rec)
            rdoc.Views.Redraw()
        CUT, INK, INT, Other = [out[k] for k in LAYERS]
        comp.Message = "%d/%d placed, %d inside" % (placed, len(cuts), inside)


if __name__ == "__main__" and "ghenv" not in globals():
    assert owner(set(), [1.0]) is None
    assert owner({0, 2}, [5.0, 1.0, 2.0]) == 2      # nested: the smaller Cut wins
    assert owner({1}, [5.0, 1.0]) == 1

    class P(object):                         # find_nest through a relay
        def __init__(self, name, sources=()):
            self.Sources = list(sources)
            self.Attributes = self
            self.GetTopLevel = self
            self.DocObject = self
            self.name = name
        def GetType(self):
            return self
        @property
        def FullName(self):
            return self.name
    nest = P("opennest_2.component_nest1")
    assert find_nest(P("x", [P("Relay", [nest])])) is nest
    assert find_nest(P("x", [P("Relay")])) is None
    print("ok")
