# -*- coding: utf-8 -*-
"""Rinforzo.make + UpdateRinforzo end to end in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_update_rinforzo.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_update_rinforzo.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import AreaMassProperties, Point3d, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    sys.path.insert(0, os.path.dirname(HERE))
    for m in ("ReinfCircle", "ZipCover", "ZipStops", "Rinforzo", "UpdateRinforzo", "click_undo"):
        sys.modules.pop(m, None)
    sc.doc = Rhino.RhinoDoc.CreateHeadless(None)  # own document
    rs.AddLayer("Reinforcements", parent=rs.AddLayer("Parts"))
    rs.CurrentLayer("Parts::Reinforcements")
    import Rinforzo as M
    import UpdateRinforzo as U
    from click_undo import Steps

    rs.ViewCPlane = lambda *a: Rhino.Geometry.Plane.WorldXY  # headless: no view
    doc, tol, Z = sc.doc, 0.001, Vector3d.ZAxis
    pid = rs.AddPolyline([(0, 0, 0), (500, 0, 0), (500, 300, 0), (0, 300, 0), (0, 0, 0)])
    panel = rs.coercecurve(pid)
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(M.layer(), -1)
    sc.sticky[M.UP_KEY] = 1000.0
    full, label = M.make(doc, pid, panel, Point3d(510, 150, 0), 60, 30, True, Z, tol, attrs, Steps(doc))
    contour = full[0]
    assert label == u"R6", label
    for k, v in (("W", "60"), ("Layout", "1"), ("Panel", str(pid))):
        assert rs.GetUserText(contour, "RF_" + k) == v, (k, rs.GetUserText(contour, "RF_" + k))
    g = rs.ObjectGroups(contour)
    area = lambda i: AreaMassProperties.Compute(rs.coercecurve(i)).Area
    assert abs(area(contour) - 18000) < 1e-2 and len(g) == 1, area(contour)
    before = len(rs.ObjectsByGroup(g[0]))

    class Opts(object):  # the option prompt: W 60 → 80, Seam No, Enter
        def __getattr__(self, name):
            return lambda *a: None
        def AddOptionDouble(self, name, o):
            if name == "W":
                o.CurrentValue = 80.0
        def Get(self):
            return Rhino.Input.GetResult.Nothing
    class NS(object):
        def __init__(self, real, **over):
            self.real, self.over = real, over
        def __getattr__(self, name):
            return self.over[name] if name in self.over else getattr(self.real, name)
    get_objects = rs.GetObjects
    U.Rhino = NS(Rhino, Input=NS(Rhino.Input, Custom=NS(Rhino.Input.Custom, GetOption=Opts)))
    rs.GetObjects = lambda *a, **k: [contour]
    try:
        U.main()
    finally:
        U.Rhino, rs.GetObjects = Rhino, get_objects
    news = [i for i in rs.AllObjects() if rs.GetUserText(i, "RF_W")]
    assert len(news) == 1, news  # the contour keeps its id (attributes are copied)
    c = news[0]
    assert sum(1 for i in rs.AllObjects() if rs.GetUserText(i, 'PartLink')) == before, 'stale/missing PartLink'
    assert rs.GetUserText(c, "RF_W") == "80.0" , rs.GetUserText(c, "RF_W")
    assert abs(area(c) - 80 * 300) < 1e-2, area(c)  # 80 wide, 300 long
    assert abs(rs.coercecurve(c).GetBoundingBox(True).Min.Y - 1000) < 1e-3  # still 1000 up
    g2 = rs.ObjectGroups(c)
    assert len(g2) == 1 and len(rs.ObjectsByGroup(g2[0])) == before, (g2, before)
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
