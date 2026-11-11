# -*- coding: utf-8 -*-
"""Check of click_undo.Steps (Undo of the last click in click loops) and click_undo.click_options (the click prompt
with options: values remembered, Undo first, Style last; the prompts of the scripts keep their option order) in Rhino 8
(needs RhinoCommon):
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

    # ---- click_options: a prompt answered by the test
    import scriptcontext as sc
    import click_undo as CU

    class Prompt(object):
        """Stands in for a GetPoint: records the options, answers Get from a script of
        ("set", name, value) — a number / switch typed, ("pick", name[, list index]) — an option clicked,
        a Point3d — a click, None — Enter."""
        def __init__(self, answers):
            self.answers, self.names, self.held, self.index, self.list_index, self.point, self.asked = list(answers), [], {}, 0, 0, None, []

        def _add(self, name, value=None):
            self.names.append(name)
            self.held[name] = value
            return len(self.names)

        def ClearCommandOptions(self):
            self.names, self.held = [], {}

        def SetCommandPrompt(self, text):
            self.text = text

        def AcceptNothing(self, yes):
            pass

        def AddOption(self, name, *a):
            return self._add(name)

        def AddOptionDouble(self, name, value):
            return self._add(name, value)
        AddOptionToggle = AddOptionInteger = AddOptionDouble

        def AddOptionList(self, name, values, current):
            return self._add(name, current)

        def Get(self):
            self.asked.append(list(self.names))
            a = self.answers.pop(0)
            if a is None:
                return Rhino.Input.GetResult.Nothing
            if isinstance(a, Point3d):
                self.point = a
                return Rhino.Input.GetResult.Point
            if a[0] == "set":
                self.held[a[1]].CurrentValue = a[2]
            self.index = self.names.index(a[1]) + 1
            self.list_index = a[2] if a[0] == "pick" and len(a) > 2 else 0
            return Rhino.Input.GetResult.Option

        def OptionIndex(self):
            return self.index

        def Option(self):
            return type("O", (object,), {"CurrentListOptionIndex": self.list_index})()

        def Point(self):
            return self.point

    kept = dict(sc.sticky)
    old_doc = sc.doc
    sc.doc = doc = Rhino.RhinoDoc.CreateHeadless(None)
    doc.ModelUnitSystem = Rhino.UnitSystem.Millimeters
    try:
        sc.sticky.clear()
        pt = Point3d(1, 2, 3)
        opts = [("W", "t_w", 60.0, 0.0, 1e6), ("Layout", "t_lay", True), ("Count", "t_n", 3, 1, 9), ("Kind", "t_kind", ["A", "B"], 1), "All"]
        styled = []
        gp = Prompt([("set", "W", 75.0), ("set", "Layout", False), ("set", "Count", 5), ("pick", "Style"), pt])
        assert CU.click_options(gp, opts, style=lambda: styled.append(1)) == pt and styled == [1]
        assert gp.names == ["Undo", "W", "Layout", "Count", "Kind", "All", "Style"], gp.names
        assert (sc.sticky["t_w"], sc.sticky["t_lay"], sc.sticky["t_n"]) == (75.0, False, 5)
        gp = Prompt([None])  # the values typed last time are offered again
        assert CU.click_options(gp, opts) is None and gp.held["W"].CurrentValue == 75.0 and gp.held["Kind"] == 1 and "Style" not in gp.names
        assert CU.click_options(Prompt([("pick", "Undo")]), opts) == CU.UNDO
        assert CU.click_options(Prompt([("pick", "All")]), opts) == "All"
        assert CU.click_options(Prompt([("pick", "Kind", 0)]), opts) == CU.CHANGED and sc.sticky["t_kind"] == 0
        gp = Prompt([pt])
        assert CU.click_options(gp, opts, undo=False) == pt and gp.names[0] == "W"

        # ---- the prompts of the scripts: option order as before (Undo keeps U, the letters stay), values back
        for f in ("parts", "pattern", "markup", "curves"):
            sys.path.insert(0, os.path.join(os.path.dirname(HERE), f))
        for m in ("JoinCorner", "ZipCover", "Bordino", "Rinforzo", "TubePockets", "Break", "Seams", "Notches", "ReinfCircle",
                  "ZipStops", "PatternTextStyles", "DotToPanelText", "SplitCrvByAngle"):
            sys.modules.pop(m, None)
        import Bordino, Break, JoinCorner, Notches, Rinforzo, Seams, TubePockets, ZipCover

        def names(fn, *args):
            gp = Prompt([pt])
            assert fn(gp, *args) is not None
            return gp.names

        assert names(JoinCorner.ask) == ["Undo", "Angle"]
        assert names(ZipCover.ask) == ["Undo", "W", "Angle", "EditPanel", "Style"]
        assert names(Bordino.ask, "Bordino") == ["Undo", "W", "Plus", "Angle", "Up", "Style"]
        assert names(Rinforzo.ask) == ["Undo", "W", "Angle", "Layout", "Seam", "Up", "Style"]
        assert names(TubePockets.ask) == ["Undo", "W", "H", "Trim", "Seam", "Notch", "Rigid", "Layout", "Up", "Angle", "Style"]
        gp = Prompt([("set", "H", 150.0), ("set", "Rigid", True), ("set", "Up", 5000.0), pt])
        got = TubePockets.ask(gp)
        assert got == (pt, (2000.0, 150.0, 50.0, True, True, True, 30.0)), got  # w, h, trim, notch, rigid, seam, angle
        assert sc.sticky[TubePockets.UP_KEY] == 5000.0
        assert TubePockets.ask(Prompt([("pick", "Undo")])) == CU.UNDO and TubePockets.ask(Prompt([None])) is None
        assert names(Break.ask, doc) == ["Undo", "Type", "Pick"]
        gp = Prompt([("pick", "Type", 1), pt])  # Type → Ripresa: asked again without Pick, another prompt text
        assert Break.ask(gp, doc) == pt and gp.asked == [["Undo", "Type", "Pick"], ["Undo", "Type"]] and "ripresa" in gp.text
        gp = Prompt([("set", "Width", 15.0), ("pick", "Mode", 1), ("pick", "Corner", 2), ("pick", "All")])
        assert Seams.ask(gp, doc) == Seams.ALL
        assert gp.asked == [["Undo", "Mode", "Width", "All", "Angle"]] * 2 + [["Undo", "Mode", "Corner", "All", "Angle"]] * 2
        assert (sc.sticky["Seams_width"], sc.sticky["Seams_mode"], sc.sticky["Seams_corner"]) == (15.0, 1, 2)
        gp = Prompt([("pick", "Mode", 0), ("pick", "Mode", 2), ("set", "Count", 4), ("pick", "Mode", 1), pt])
        assert Notches.ask(gp, doc) == pt
        assert gp.asked == [["Undo", "Mode", "Every", "Angle"], ["Undo", "Mode", "Distance", "Percent", "Angle"],
                            ["Undo", "Mode", "First", "Last", "Count", "Angle"], ["Undo", "Mode", "First", "Last", "Count", "Angle"],
                            ["Undo", "Mode", "Angle"]], gp.asked
        assert Notches.opt("count") == 4 and Notches.opt("mode") == 1
    finally:
        sc.sticky.clear()
        sc.sticky.update(kept)
        sc.doc = old_doc
        doc.Dispose()
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
