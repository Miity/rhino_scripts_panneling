# -*- coding: utf-8 -*-
"""FreeSheet — GhPython component for autonest_v4.gh.

The sheet minus the big panels already nested: the sheet outline with the placed
panels as holes. The small parts are nested onto it (OpenNest2 puts parts into
sheet holes' surroundings only — a hole is not material).

Inputs:
    Sheet  : the sheet curve (the same one the first nest got)
    Placed : All Geo of the first nest, one placed outline per branch (Tree access)
    Ids    : Sheet Id of the first nest, same branches (Tree access) — an outline
             not on sheet 0 (didn't fit) is no hole
Outputs:
    Sheets : one branch: the sheet outline first, then the holes — to Sheets
"""


def on_sheet(ids, i):
    """True when part i landed on sheet 0 (ids = sheet number per branch, -1 = didn't fit)."""
    return i < len(ids) and ids[i] == 0


if "ghenv" in globals():
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path

    comp = ghenv.Component
    sheet = list(comp.Params.Input[0].VolatileData.AllData(True))
    placed = comp.Params.Input[1].VolatileData
    sid = comp.Params.Input[2].VolatileData
    ids = [int(sid.Branches[i][0].Value) if sid.Branches[i].Count else -1 for i in range(sid.PathCount)]
    Sheets = DataTree[object]()
    if sheet:
        Sheets.Add(sheet[0].Value.DuplicateCurve(), GH_Path(0))
        holes = 0
        for i in range(placed.PathCount):
            if placed.Branches[i].Count and on_sheet(ids, i):
                Sheets.Add(placed.Branches[i][0].Value.DuplicateCurve(), GH_Path(0))
                holes += 1
        comp.Message = "%d holes" % holes


if __name__ == "__main__" and "ghenv" not in globals():
    assert on_sheet([0, -1, 0], 0) and not on_sheet([0, -1, 0], 1) and not on_sheet([0], 3)
    print("ok")
