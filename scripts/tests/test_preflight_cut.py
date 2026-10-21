# -*- coding: utf-8 -*-
"""Check of PreflightCut.duplicates in Rhino 8 (needs RhinoCommon):
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
    import PreflightCut as M

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
        msg, bad = M.duplicates(doc)
        assert not bad, (msg, bad)
        # duplicate on the same layer
        line("cut", (0, 0, 0), (100, 0, 0))
        msg, bad = M.duplicates(doc)
        assert len(bad) == 1, (msg, bad)
        # cut over int is one knife -> also a duplicate
        line("int", (0, 0, 0), (100, 0, 0))
        msg, bad = M.duplicates(doc)
        assert len(bad) == 2, (msg, bad)
        # ink over cut is a different tool -> not a duplicate
        n = len(bad)
        line("ink", (0, 0, 0), (100, 0, 0))
        msg, bad = M.duplicates(doc)
        assert len(bad) == n, (msg, bad)
        out.write("OK %s\n" % msg)
    finally:
        sc.doc = live
        doc.Dispose()
except Exception:
    out.write(traceback.format_exc())
out.close()
