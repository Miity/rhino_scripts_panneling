# -*- coding: utf-8 -*-
"""Check of PreflightCut.duplicates / notches in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_preflight_cut.txt next to it. Works in its own headless document, your open drawing is not touched."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_preflight_cut.txt"), "w")
try:
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "cut"))
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pattern"))
    import PreflightCut as M
    import ConvertNotches as CN
    from Rhino.Geometry import Point3d, Transform, Vector3d

    import Rhino
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    live = sc.doc
    sc.doc = doc
    for name in ("cut", "int", "ink"):
        if not rs.IsLayer(name):
            rs.AddLayer(name)
    made = []

    def line(layer, a, b):
        oid = rs.AddLine(a, b)
        rs.ObjectLayer(oid, layer)
        made.append(oid)
        return oid

    try:
        # clean: nothing overlaps
        line("cut", (0, 0, 0), (100, 0, 0))
        line("int", (0, 10, 0), (100, 10, 0))
        msg, bad = M.duplicates(doc, made)
        assert not bad, (msg, bad)
        # duplicate on the same layer
        line("cut", (0, 0, 0), (100, 0, 0))
        msg, bad = M.duplicates(doc, made)
        assert len(bad) == 1, (msg, bad)
        # cut over int is one knife -> also a duplicate
        line("int", (0, 0, 0), (100, 0, 0))
        msg, bad = M.duplicates(doc, made)
        assert len(bad) == 2, (msg, bad)
        # ink over cut is a different tool -> not a duplicate
        n = len(bad)
        line("ink", (0, 0, 0), (100, 0, 0))
        msg, bad = M.duplicates(doc, made)
        assert len(bad) == n, (msg, bad)
        out.write("OK %s\n" % msg)

        # knife notches: a 100 x 100 part on cut, one V (Standard) on its bottom edge
        for oid in list(made):
            rs.DeleteObject(oid)
        del made[:]
        sq = rs.AddPolyline([(0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 100, 0), (0, 0, 0)])
        rs.ObjectLayer(sq, "cut")
        p = CN.spec(dict(CN.DEFAULTS, tool=1))
        attrs = CN.notch_attrs(doc, p, [])
        attrs.LayerIndex = doc.Layers.FindByFullPath("int", -1)
        legs = [doc.Objects.AddCurve(g, attrs) for g in
                CN.shapes(Point3d(50, 0, 0), Vector3d(0, -1, 0), Vector3d.ZAxis, p)]
        assert len(legs) == 2, legs
        msg, bad = M.notches(doc, [sq] + legs)
        assert not bad, (msg, bad)
        # the part moved, the notch stayed: now in the middle of the material
        rs.MoveObject(sq, (0, -40, 0))
        msg, bad = M.notches(doc, [sq] + legs)
        assert len(bad) == 2, (msg, bad)
        rs.MoveObject(sq, (0, 40, 0))
        # mirrored notch: pointing out of the part
        rs.TransformObjects(legs, Transform.Mirror(Point3d(0, 0, 0), Vector3d(0, 1, 0)))
        msg, bad = M.notches(doc, [sq] + legs)
        assert len(bad) == 2, (msg, bad)
        rs.TransformObjects(legs, Transform.Mirror(Point3d(0, 0, 0), Vector3d(0, 1, 0)))
        # half a V
        msg, bad = M.notches(doc, [sq, legs[0]])
        assert bad == [legs[0]], (msg, bad)
        # no CUT line selected: every leg fails
        msg, bad = M.notches(doc, legs)
        assert len(bad) == 2, (msg, bad)
        out.write("OK %s\n" % msg)
    finally:
        sc.doc = live
        doc.Dispose()
except Exception:
    out.write(traceback.format_exc())
out.close()
