# -*- coding: utf-8 -*-
"""Check of LayoutParts.layout in Rhino 8 (headless document):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_layout_parts.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_layout_parts.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Plane, Point3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    import LayoutParts as M

    doc = Rhino.RhinoDoc.CreateHeadless(None)
    sc.doc = doc
    rs.AddLayer("Parts")
    rs.AddLayer("Reinforcements", parent="Parts")
    rs.CurrentLayer("Parts::Reinforcements")
    panel = rs.AddRectangle(Plane.WorldXY, 100, 100)        # work area 0..100
    a = rs.AddCircle((0, 0, 0), 20)                           # part 1: group circle + text
    t = rs.AddText("RC1", Plane.WorldXY, 5)
    rs.AddObjectsToGroup([a, t], rs.AddGroup())
    b = rs.AddRectangle(Plane.WorldXY, 30, 10)                # part 2: single

    assert M.layout(doc, [a], 10.0, Plane.WorldXY) == ([], 0)    # no click and nothing laid out — nothing
    new, skipped = M.layout(doc, [a, b], 10.0, Plane.WorldXY, Point3d(0, 110, 0))  # only the circle from the group
    assert len(new) == 3 and skipped == 0, (len(new), skipped)
    copies = [i for i in new if rs.IsCurve(i)]
    circ = [i for i in copies if rs.IsCircle(i)][0]
    rect = [i for i in copies if not rs.IsCircle(i)][0]
    x0, y0, x1, y1 = M.box([circ], Plane.WorldXY)
    assert abs(x0) < 1e-6 and abs(y0 - 110) < 1e-6, (x0, y0)           # bottom-left corner — at the click point
    x0, y0, _, _ = M.box([rect], Plane.WorldXY)
    assert abs(x0 - 50) < 1e-6 and abs(y0 - 110) < 1e-6, (x0, y0)      # to the right of the group after the gap
    for i in new:
        assert rs.ObjectLayer(i) == "Parts::Reinforcements::Layout", rs.ObjectLayer(i)
    g = rs.ObjectGroups(circ)
    assert g and rs.ObjectGroups([i for i in new if rs.IsText(i)][0]) == g and g != rs.ObjectGroups(a)
    assert not rs.ObjectGroups(rect)
    assert rs.ObjectLayer(a) == "Parts::Reinforcements" and rs.ObjectGroups(a)  # the original is not touched

    # repeated run: everything is already laid out, copies are skipped too
    again, skipped = M.layout(doc, [a, b, circ], 10.0, Plane.WorldXY)
    assert not again and skipped == 3, (again, skipped)

    # a new part continues the row to the right of the laid out ones (rect 50..80)
    c = rs.AddRectangle(Plane.WorldXY, 5, 5)
    more, _ = M.layout(doc, [c], 10.0, Plane.WorldXY)
    x0, y0, _, _ = M.box(more, Plane.WorldXY)
    assert abs(x0 - 90) < 1e-6 and abs(y0 - 110) < 1e-6, (x0, y0)
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
