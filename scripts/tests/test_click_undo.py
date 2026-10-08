# -*- coding: utf-8 -*-
"""Check of click_undo.Steps (Undo of the last click in click loops) in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_click_undo.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_click_undo.txt"), "w")
try:
    import Rhino
    from Rhino.Geometry import LineCurve, Point3d
    sys.path.insert(0, os.path.dirname(HERE))
    sys.modules.pop("click_undo", None)
    from click_undo import Steps

    doc = Rhino.RhinoDoc.CreateHeadless(None)
    a = doc.Objects.AddCurve(LineCurve(Point3d(0, 0, 0), Point3d(10, 0, 0)))
    b = doc.Objects.AddCurve(LineCurve(Point3d(0, 5, 0), Point3d(10, 5, 0)))
    d = doc.Objects.AddPoint(Point3d(1, 1, 0))
    g = doc.Groups.Add()
    steps = Steps(doc)

    def length(i):
        return doc.Objects.FindId(i).Geometry.GetLength()

    steps.start()  # click 1: replace a, add a point
    steps.change(a)
    doc.Objects.Replace(a, LineCurve(Point3d(0, 0, 0), Point3d(30, 0, 0)))
    p1 = doc.Objects.AddPoint(Point3d(2, 2, 0))
    steps.start()  # click 2: replace b + put it in a group, delete d
    steps.change(b)
    doc.Objects.Replace(b, LineCurve(Point3d(0, 5, 0), Point3d(50, 5, 0)))
    at = doc.Objects.FindId(b).Attributes.Duplicate()
    at.AddToGroup(g)
    doc.Objects.ModifyAttributes(b, at, True)
    steps.delete(d)
    steps.start()  # click 3: skipped (nothing changed) — Undo must go past it

    assert steps.undo()  # → click 2 back: b old and out of the group, d back (same id); a and p1 untouched
    assert abs(length(b) - 10) < 1e-9 and doc.Objects.FindId(b).Attributes.GroupCount == 0
    assert doc.Objects.FindId(d) is not None and abs(length(a) - 30) < 1e-9 and doc.Objects.FindId(p1) is not None
    assert steps.undo()  # → click 1 back: a old, p1 gone, b (restored by the previous Undo) NOT deleted
    assert abs(length(a) - 10) < 1e-9 and doc.Objects.FindId(p1) is None and doc.Objects.FindId(b) is not None
    assert not steps.undo()  # nothing left
    doc.Dispose()
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
