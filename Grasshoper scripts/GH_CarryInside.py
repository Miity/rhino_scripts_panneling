# -*- coding: utf-8 -*-
"""CarryInside — GhPython component for autonest_v2.gh.

Each panel (a Rhino group: CUT + INT, INK, texts…, from PanelGroups) goes to
its nested place: the CUT's own OpenNest transform is applied to a copy of
every member.

A CUT that doesn't fit OpenNest puts on an extra copy of the sheet (IDS ≥
number of sheets): it is left out with a warning, the message counts the
placed ones ("11/12 placed").

Inputs:
    Ids  : Ids output of PanelGroups — branch {i}: CUT id, then the rest of
           its group (Tree access)
    X    : Transform output of OpenNest (Tree access)
    Bake : Button — copies (CUT + its group) added to the Rhino document with
           their own layer / colour / linetype, one group per panel, one undo
Outputs (one per layer, to bake each into its layer; branch {i} = panel i):
    CUT   : moved CUT copies
    INK   : moved copies from layer INK
    INT   : moved copies from layer INT
    Other : moved copies from any other layer
    N     : "<panel>: <objects with its CUT>" per panel
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


if "ghenv" in globals():
    import System
    import Rhino
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path

    LAYERS = ["CUT", "INK", "INT", "Other"]
    comp = ghenv.Component
    rdoc = Rhino.RhinoDoc.ActiveDoc
    idata = comp.Params.Input[0].VolatileData
    parts = [[o for o in (rdoc.Objects.FindId(System.Guid(str(g))) for g in idata.Branches[n]) if o]
             for n in range(idata.PathCount)]
    xdata = comp.Params.Input[1].VolatileData
    xforms = [list(xdata.Branches[i]) if i < xdata.PathCount else [] for i in range(len(parts))]
    nest = find_nest(comp.Params.Input[1])
    off = set()
    if nest:
        sheet_of = nest.Params.Output[4].VolatileData
        sheets = nest.Params.Input[0].VolatileDataCount
        off = set(i for i in range(min(len(parts), sheet_of.PathCount))
                  if sheet_of.Branches[i].Count and sheet_of.Branches[i][0].Value >= sheets)

    if not parts:
        comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Error, "Ids must come from PanelGroups")
    elif any(xforms):
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
        comp.Message = "%d/%d placed, %d with them" % (placed, len(parts), inside)


if __name__ == "__main__" and "ghenv" not in globals():
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
