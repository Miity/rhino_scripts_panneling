# -*- coding: utf-8 -*-
"""CarryInside — GhPython component for autonest_v2.gh.

Everything that lies inside each Cut (INK, INT, texts, points, holes — any
visible object of the Rhino document, any layer) goes with the Cut to its
nested place: the Cut's own OpenNest transform is applied to a copy.

An object belongs to a Cut when its start, middle or end (point / text:
its centre) is inside the Cut or on its line; inside several Cuts — the
smallest one. Objects inside no Cut stay where they are.

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


def owner(hits, areas):
    """Index of the Cut an object belongs to: the smallest Cut holding one of its points."""
    return min(hits, key=lambda i: areas[i]) if hits else None


if "ghenv" in globals():
    import Rhino
    import Rhino.Geometry as rg
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path

    LAYERS = ["CUT", "INK", "INT"]
    comp = ghenv.Component
    rdoc = Rhino.RhinoDoc.ActiveDoc
    tol = rdoc.ModelAbsoluteTolerance
    ids = [g.ReferenceID for g in comp.Params.Input[0].VolatileData.AllData(True)]
    cuts = [rdoc.Objects.FindId(i) for i in ids]
    xdata = comp.Params.Input[1].VolatileData
    xforms = [[g.Value for g in xdata.Branches[i]] if i < xdata.PathCount else [] for i in range(len(ids))]

    if not ids or None in cuts:
        comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Error, "Cut must be curves referenced from Rhino")
    elif any(xforms):
        curves = [c.Geometry for c in cuts]
        boxes = [c.GetBoundingBox(True) for c in curves]
        for b in boxes:
            b.Inflate(tol)
        areas = []
        for c, b in zip(curves, boxes):
            mp = rg.AreaMassProperties.Compute(c) if c.IsClosed else None
            areas.append(mp.Area if mp else b.Area)

        def samples(geo):
            if isinstance(geo, rg.Curve):
                t = geo.NormalizedLengthParameter(0.5)[1]
                return [geo.PointAtStart, geo.PointAt(t), geo.PointAtEnd]
            if isinstance(geo, rg.Point):
                return [geo.Location]
            return [geo.GetBoundingBox(True).Center]

        inside = [[] for _ in ids]
        skip = set(ids)
        settings = Rhino.DocObjects.ObjectEnumeratorSettings()
        settings.HiddenObjects = False
        settings.LockedObjects = True
        settings.VisibleFilter = True
        for obj in rdoc.Objects.GetObjectList(settings):
            if obj.Id in skip or obj.Attributes.Space != Rhino.DocObjects.ActiveSpace.ModelSpace:
                continue
            hits = set()
            for p in samples(obj.Geometry):
                for i, (c, b) in enumerate(zip(curves, boxes)):
                    if b.Contains(p) and c.Contains(p, rg.Plane.WorldXY, tol) != rg.PointContainment.Outside:
                        hits.add(i)
            i = owner(hits, areas)
            if i is not None:
                inside[i].append(obj)

        out = dict((k, DataTree[object]()) for k in LAYERS + ["Other"])
        N = []
        parts = []
        for i, cut in enumerate(cuts):
            N.append("%d: %d" % (i, len(inside[i])))
            if len(xforms[i]) != 1:
                comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning, "Cut %d not placed — left out" % i)
                continue
            part = []
            for obj in [cut] + inside[i]:
                g = obj.Geometry.Duplicate()
                g.Transform(xforms[i][0])
                top = rdoc.Layers[obj.Attributes.LayerIndex].FullPath.split("::")[0].upper()
                out[top if top in LAYERS else "Other"].Add(g, GH_Path(i))
                part.append((g, obj.Attributes))
            parts.append(part)

        if Bake:
            rec = rdoc.BeginUndoRecord("CarryInside bake")
            for part in parts:
                group = rdoc.Groups.Add()
                for g, attrs in part:
                    a = attrs.Duplicate()
                    a.RemoveFromAllGroups()
                    a.AddToGroup(group)
                    rdoc.Objects.Add(g, a)
            rdoc.EndUndoRecord(rec)
            rdoc.Views.Redraw()
        CUT, INK, INT, Other = [out[k] for k in LAYERS + ["Other"]]
        comp.Message = "%d parts, %d inside" % (len(parts), sum(len(p) - 1 for p in parts))


if __name__ == "__main__" and "ghenv" not in globals():
    assert owner(set(), [1.0]) is None
    assert owner({0, 2}, [5.0, 1.0, 2.0]) == 2      # nested: the smaller Cut wins
    assert owner({1}, [5.0, 1.0]) == 1
    print("ok")
