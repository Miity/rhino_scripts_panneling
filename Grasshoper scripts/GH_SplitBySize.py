# -*- coding: utf-8 -*-
"""SplitBySize — GhPython component for autonest_v4.gh.

Big panels are nested first, small parts then fill what is left (v4 nests twice).
A part is BIG when the area of its bounding box is at least Big % of the largest one.

Inputs:
    Cut : the Cut output of PanelGroups, one closed curve per branch {i} (Tree access, No Type Hint)
    Big : percent of the largest bounding box area (default 5)
Outputs:
    BigCut   : the big curves, one per branch {k} — to the first Geometry
    SmallCut : the small curves, one per branch {k} — to the second Geometry
    BigIdx   : original panel number of each big curve (branch {i} of Cut)
    SmallIdx : the same for the small ones — both go to MergeNests
"""


def split(areas, pct):
    """Indexes of the big parts: area >= pct % of the largest; the rest are small."""
    top = max(areas) if areas else 0
    big = [i for i, a in enumerate(areas) if a >= top * pct / 100.0]
    return big, [i for i in range(len(areas)) if i not in big]


if "ghenv" in globals():
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path

    comp = ghenv.Component
    data = comp.Params.Input[0].VolatileData
    curves = [data.Branches[i][0].Value if data.Branches[i].Count else None for i in range(data.PathCount)]
    box = [c.GetBoundingBox(True) if c is not None else None for c in curves]
    areas = [(b.Max.X - b.Min.X) * (b.Max.Y - b.Min.Y) if b is not None else 0 for b in box]
    BigIdx, SmallIdx = split(areas, 5.0 if Big is None else float(Big))
    BigCut, SmallCut = DataTree[object](), DataTree[object]()
    for tree, idx in ((BigCut, BigIdx), (SmallCut, SmallIdx)):
        for k, i in enumerate(idx):
            if curves[i] is not None:
                tree.Add(curves[i].DuplicateCurve(), GH_Path(k))
    comp.Message = "%d big / %d small" % (len(BigIdx), len(SmallIdx))


if __name__ == "__main__" and "ghenv" not in globals():
    assert split([100, 50, 4, 5, 1], 5) == ([0, 1, 3], [2, 4])      # 5 % of 100 = 5
    assert split([100, 50], 0) == ([0, 1], [])
    assert split([], 5) == ([], [])
    print("ok")
