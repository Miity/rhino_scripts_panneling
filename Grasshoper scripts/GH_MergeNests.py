# -*- coding: utf-8 -*-
"""MergeNests — GhPython component for autonest_v4.gh.

The two nests (big panels, then small parts) back into the order of PanelGroups:
branch {i} = panel i. A panel that didn't fit (Sheet Id not 0) gets an empty
branch, so CarryInside leaves it out with its warning.

Inputs (all Tree access, No Type Hint):
    BigX, SmallX     : Transforms of the first / second nest
    BigId, SmallId   : Sheet Id of the first / second nest
    BigGeo, SmallGeo : All Geo of the first / second nest
    BigIdx, SmallIdx : SplitBySize outputs (panel number of each branch; List access)
Outputs:
    X   : Transforms in panel order — to CarryInside
    Geo : placed outlines in panel order — to SeedSearch / the preview
    N   : "<big placed>/<big>  <small placed>/<small>"
"""


def order(big_idx, small_idx):
    """[(nest 0 big / 1 small, branch k) per panel i] from the two index lists."""
    where = {}
    for k, i in enumerate(big_idx):
        where[i] = (0, k)
    for k, i in enumerate(small_idx):
        where[i] = (1, k)
    return [where[i] for i in sorted(where)]


if "ghenv" in globals():
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path

    comp = ghenv.Component
    P = [p.VolatileData for p in comp.Params.Input]
    X, Geo = DataTree[object](), DataTree[object]()
    first = lambda tree, k: tree.Branches[k][0] if k < tree.PathCount and tree.Branches[k].Count else None
    placed = [0, 0]
    for i, (n, k) in enumerate(order([g.Value for g in P[6].AllData(True)], [g.Value for g in P[7].AllData(True)])):
        x, sid, geo = (P[0], P[2], P[4]) if n == 0 else (P[1], P[3], P[5])
        s = first(sid, k)
        X.EnsurePath(GH_Path(i))
        Geo.EnsurePath(GH_Path(i))
        if s is not None and int(s.Value) == 0 and first(x, k) is not None and first(geo, k) is not None:
            X.Add(first(x, k).Value, GH_Path(i))
            Geo.Add(first(geo, k).Value, GH_Path(i))
            placed[n] += 1
    N = "%d/%d  %d/%d" % (placed[0], P[6].DataCount, placed[1], P[7].DataCount)
    comp.Message = N


if __name__ == "__main__" and "ghenv" not in globals():
    assert order([0, 2], [1, 3]) == [(0, 0), (1, 0), (0, 1), (1, 1)]
    assert order([], [0]) == [(1, 0)]
    print("ok")
