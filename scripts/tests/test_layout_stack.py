# -*- coding: utf-8 -*-
"""End to end: real Bordino / Pettola / Rinforzo parts on a panel turned 30° + an RC part; LayoutStack.main (click prompt
faked: options + click / Enter) on the whole selection → only the ticked kinds (Rinforzo, Bordini; never Pettola / RC), copies along X reading left to
right, stacked down from the click Gap apart, Rinforzo first, longest first; a second run skips them, LayoutParts too; Enter + Hide=Yes, Rinforzo=No → only the
bordini parts up are hidden.
Rhino 8: DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_layout_stack.txt next to it."""
import math
import os
import sys
import traceback
import types

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_layout_stack.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Plane, Point3d, Polyline, PolylineCurve, TextEntity, Transform, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ZipCover", "ZipStops", "Bordino", "Rinforzo", "LayoutParts", "LayoutStack",
              "PatternTextStyles", "click_undo"):
        sys.modules.pop(m, None)
    import Bordino as B
    import LayoutParts as LP
    import LayoutStack as L
    import Rinforzo as R

    doc = Rhino.RhinoDoc.CreateHeadless(None)
    sc.doc = doc
    sc.sticky.update({"Parts_up": 10000.0, "ZipCover_angle": 30.0, "Bordino": 35.0, "Bordino_plus": 60.0,
                      "Pettola": 100.0, "Pettola_plus": 60.0, R.STICKY: 60.0, R.STICKY + "_plus": 100.0,
                      R.STICKY + "_layout": True})
    rs.ViewCPlane = lambda *a, **k: Plane.WorldXY
    turn = Transform.Rotation(math.radians(30), Vector3d.ZAxis, Point3d.Origin)
    pl = PolylineCurve(Polyline([Point3d(*p) for p in ((0, 0, 0), (500, 0, 0), (500, 300, 0), (0, 300, 0), (0, 0, 0))]))
    pl.Transform(turn)
    pid = doc.Objects.AddCurve(pl)

    def click(x, y):
        p = Point3d(x, y, 0)
        p.Transform(turn)
        return p

    def make(mod, c, *kind):
        rs.GetObject = lambda *a, **k: pid
        seq = [c, None]
        mod.ask = lambda *a: seq.pop(0)
        mod.main(*kind)

    make(B, click(250, 1), "Bordino")    # bottom edge 500 → strip 560 × 35 at 30°
    make(B, click(499, 150), "Bordino")  # right edge 300 → strip 360 × 35 at 120°
    make(B, click(250, 299), "Pettola")  # not taken
    make(R, click(1, 150))               # left edge 300 → rinforzo 400 × 60 at 120°, label Bottom / Top aligned
    rs.CurrentLayer("Parts::Reinforcements")
    rc = [rs.AddRectangle(Plane(Point3d(0, 3000, 0), Vector3d.ZAxis), 80, 40),
          rs.AddText("RC3  r=4", Plane(Point3d(10, 3010, 0), Vector3d.ZAxis), 10)]
    rs.AddObjectsToGroup(rc, rs.AddGroup())  # a reinforcement, not a strip: not taken

    every = [o.Id for o in doc.Objects]
    todo, done = L.pick(doc, every, L.KINDS[1:])
    assert [k for k, _ in todo] == [0, 0] and not done, (todo, done)  # Bordini only
    todo, done = L.pick(doc, every, L.KINDS)
    assert sorted(k for k, _ in todo) == [0, 1, 1] and not done, (todo, done)
    run = {}

    class Opt(object):
        def __init__(self, v, *a):
            self.CurrentValue = v

    class GP(object):  # the click prompt: options set as given in run, then a click (at) or Enter (at=None)
        def __init__(self):
            self.o = {}
        def SetCommandPrompt(self, s):
            pass
        def AcceptNothing(self, b):
            pass
        def AddOptionToggle(self, n, t):
            self.o[n] = t
        AddOptionDouble = AddOptionToggle
        def Get(self):
            for n, v in run["set"].items():
                self.o[n].CurrentValue = v
            return self.Result()
        def Result(self):
            return Rhino.Input.GetResult.Point if run["at"] else Rhino.Input.GetResult.Nothing
        def CommandResult(self):
            return Rhino.Commands.Result.Success
        def Point(self):
            return run["at"]
    L.Rhino = types.SimpleNamespace(Commands=Rhino.Commands, Input=types.SimpleNamespace(
        GetResult=Rhino.Input.GetResult, Custom=types.SimpleNamespace(GetPoint=GP, OptionToggle=Opt, OptionDouble=Opt)))
    rs.GetObjects = lambda *a, **k: every
    run.update(at=Point3d(0, -5000, 0), set={"Rinforzo": True, "Bordini": True, "Gap": 10.0, "Hide": False})
    L.main()
    copies = [o for o in doc.Objects if o.Attributes.GetUserString(LP.KEY)]
    lay = set(doc.Layers[o.Attributes.LayerIndex].FullPath for o in copies)
    assert lay == {"Parts::Bordino::Layout", "Parts::Reinforcements::Layout"}, lay
    rects = sorted([o.Geometry for o in copies if isinstance(o.Geometry, Rhino.Geometry.Curve)],
                   key=lambda c: -c.GetBoundingBox(True).Max.Y)
    texts = [o.Geometry for o in copies if isinstance(o.Geometry, TextEntity)]
    assert len(rects) == 3 and len(texts) == 3, (len(rects), len(texts))
    tol = 1e-6
    y = -5000.0
    for c, (length, w) in zip(rects, ((400.0, 60.0), (560.0, 35.0), (360.0, 35.0))):  # Rinforzo, then longest first
        bb = c.GetBoundingBox(True)
        assert abs(bb.Min.X) < tol and abs(bb.Max.Y - y) < tol, (bb.Min, bb.Max, y)
        assert abs(bb.Max.X - bb.Min.X - length) < tol and abs(bb.Max.Y - bb.Min.Y - w) < tol, (bb.Min, bb.Max)
        y -= w + 10.0
    assert sorted(t.PlainText for t in texts) == ["B3.5", "B3.5", "R6"], [t.PlainText for t in texts]
    for t in texts:
        assert t.Plane.XAxis.X > 1 - tol, t.Plane.XAxis  # along X, left to right
        o = t.GetBoundingBox(True).Center
        assert any(r.GetBoundingBox(True).Contains(o) for r in rects), o  # inside its strip
    groups = set(tuple(o.Attributes.GetGroupList() or []) for o in copies)
    assert len(groups) == 3, groups  # each strip with its label
    todo, done = L.pick(doc, every, L.KINDS)  # again: already laid out
    assert not todo and len(done) == 3, (todo, done)
    assert set(str(o.Id) for _, u in done for o in u) == set(o.Attributes.GetUserString(LP.KEY) for o in copies)
    new, skipped = LP.layout(doc, every, 10.0, Plane.WorldXY, Point3d(0, -8000, 0), 20.0)
    assert skipped == 3, skipped  # LayoutParts: the stacked ones are already on the canvas
    assert not [o for o in map(doc.Objects.FindId, every) if o.IsHidden]
    run.update(at=None, set={"Rinforzo": False, "Bordini": True, "Hide": True})  # Enter: only Hide, bordini only
    L.main()
    hidden = [o for o in map(doc.Objects.FindId, every) if o.IsHidden]  # doc.Objects skips hidden objects
    assert sorted(o.Geometry.PlainText for o in hidden if isinstance(o.Geometry, TextEntity)) == ["B3.5", "B3.5"], \
        [(o.Geometry.GetType().Name, rs.ObjectLayer(o.Id)) for o in hidden]
    assert len(hidden) == 4 and not any(o.Attributes.GetUserString("PartMarkup") for o in hidden), len(hidden)
    assert sc.sticky["LayoutStackHide"] and not sc.sticky["LayoutStackRinforzo"]  # remembered
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
