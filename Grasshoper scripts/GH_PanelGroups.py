# -*- coding: utf-8 -*-
"""PanelGroups — GhPython component for autonest_v2.gh.

Panels come grouped in Rhino: one CUT (closed curve on layer CUT) + its INT,
INK, texts… Only the CUTs go to OpenNest; the rest of each group goes with
its CUT after nesting (CarryInside).

Inputs:
    Parts : the grouped panels referenced from Rhino (Set Multiple — a window
            over the groups is enough: a CUT brings its whole group), Tree access,
            No Type Hint (the default ghdoc hint fails on texts)
Outputs:
    Cut   : the CUT of each panel, one per branch {i} — to OpenNest Geo
    Ids   : branch {i}: the CUT's id, then every other member of its group(s)
            — to CarryInside
"""


def panels(objs, is_cut, groups_of, members):
    """objs (ids, input order) → ([[cut, member…] per CUT], loose objs, CUTs sharing a group with another CUT)."""
    parts, shared, taken = [], [], set()
    for c in [o for o in objs if is_cut(o)]:
        mates = []
        for g in groups_of(c):
            for m in members(g):
                if m != c and m not in mates:
                    mates.append(m)
        if any(is_cut(m) for m in mates):
            shared.append(c)
        parts.append([c] + [m for m in mates if not is_cut(m)])
        taken.update(parts[-1])
    return parts, [o for o in objs if o not in taken], shared


if "ghenv" in globals():
    import Rhino
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path

    comp = ghenv.Component
    rdoc = Rhino.RhinoDoc.ActiveDoc
    warn = lambda text: comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning, text)
    ids = []
    for g in comp.Params.Input[0].VolatileData.AllData(True):
        if g.IsReferencedGeometry and g.ReferenceID not in ids:
            ids.append(g.ReferenceID)

    def is_cut(i):
        o = rdoc.Objects.FindId(i)
        return (o is not None and isinstance(o.Geometry, Rhino.Geometry.Curve) and o.Geometry.IsClosed
                and rdoc.Layers[o.Attributes.LayerIndex].FullPath.split("::")[0].upper() == "CUT")

    parts, loose, shared = panels(
        ids, is_cut,
        lambda i: list(rdoc.Objects.FindId(i).Attributes.GetGroupList() or []),
        lambda g: [o.Id for o in rdoc.Groups.GroupMembers(g)])

    Cut, Ids = DataTree[object](), DataTree[object]()
    for n, part in enumerate(parts):
        Cut.Add(rdoc.Objects.FindId(part[0]).Geometry.Duplicate(), GH_Path(n))
        for i in part:
            Ids.Add(str(i), GH_Path(n))
    if not parts:
        comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Error, "no closed curve on layer CUT in Parts")
    if loose:
        warn("%d object(s) not in a group with a CUT — left out" % len(loose))
    if shared:
        warn("%d CUT(s) share a group with another CUT — both get its members" % len(shared))
    comp.Message = "%d panels" % len(parts)


if __name__ == "__main__" and "ghenv" not in globals():
    layer = {"c1": "CUT", "c2": "CUT", "c3": "CUT", "i1": "INT", "k1": "INK", "x": "INK", "k3": "INK"}
    groups = {"c1": [0], "i1": [0, 5], "k1": [0], "c2": [], "c3": [7], "k3": [7]}
    members = {0: ["c1", "i1", "k1"], 5: ["i1"], 7: ["c3", "k3"]}
    p, loose, shared = panels(["i1", "c1", "c2", "x", "c3"], lambda o: layer[o] == "CUT",
                              lambda o: groups.get(o, []), lambda g: members[g])
    assert p == [["c1", "i1", "k1"], ["c2"], ["c3", "k3"]], p   # k1 / k3 not selected — come with their group
    assert loose == ["x"] and shared == []
    p, loose, shared = panels(["c1", "c3"], lambda o: o.startswith("c"),
                              lambda o: [0], lambda g: ["c1", "c3", "i1"])
    assert shared == ["c1", "c3"] and p[0] == ["c1", "i1"]
    print("ok")
