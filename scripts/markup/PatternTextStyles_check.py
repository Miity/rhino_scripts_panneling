#! python3
# -*- coding: utf-8 -*-
# Check of PatternTextStyles in a temporary document (open files are not touched):
# text in a 430 x 4467 mm strip must get "PAT 28 mm", 28 mm, font SLF-RHN Architect.
import os
import sys
import Rhino
import Rhino.Geometry as rg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import PatternTextStyles as P

doc = Rhino.RhinoDoc.CreateHeadless(None)
try:
    doc.Objects.AddRectangle(rg.Rectangle3d(rg.Plane.WorldXY, 430, 4467))
    plane = rg.Plane(rg.Point3d(100, 2000, 0), rg.Vector3d.ZAxis)
    tid = doc.Objects.AddText(rg.TextEntity.Create("sx 4", plane, doc.DimStyles.Current, False, 0, 0))
    print(P.auto_size(doc, [tid], P.ensure_styles(doc)))
    te = doc.Objects.FindId(tid).Geometry
    assert doc.DimStyles.FindId(te.DimensionStyleId).Name == "PAT 28 mm"
    assert abs(te.TextHeight * te.DimensionScale - 28) < 1e-9
    assert te.Font.QuartetName == P.FONT
    assert [P.height_for(w) for w in (30, 100, 2480)] == [2.5, 5, 40]
    names = [P.style_name(h) for h in P.SERIES]
    assert sorted(names) == names  # in Rhino's list (alphabetical) the styles follow by size
    import scriptcontext as sc  # label style of a script: default PAT 14 mm, option Style overrides it
    sc.sticky.pop("Check.style", None)
    assert P.label_style(doc, "Check").Name == "PAT 14 mm"
    sc.sticky["Check.style"] = "PAT 40 mm"
    assert P.label_style(doc, "Check").Name == "PAT 40 mm"
    sc.sticky["Check.style"] = "deleted style"
    assert P.label_style(doc, "Check").Name == "PAT 14 mm"
    sc.sticky.pop("Check.style")
    print("PatternTextStyles: OK")
finally:
    doc.Dispose()
