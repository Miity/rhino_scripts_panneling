# -*- coding: utf-8 -*-
"""Check of the curves/ and markup/ toolbar scripts end to end in Rhino 8 (needs RhinoCommon), each main() on a headless
document with the prompts answered by the test: SplitCrvByAngle, smooth_corners, ReducePoints (NURBS input), TrimCrvEnds
(units, Undo of a click), KeepCrvEnds, TrimOutsidePanel, CrvToPolyline, line_type (linetype made when missing),
PointsToCrosses (layer / groups by attributes), DotToPanelText (NURBS panel), find_exact_connection.
Run through Rhino MCP (run_python) or rhinocode; the result is written to test_curves_markup.txt next to it."""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.dirname(HERE) + os.sep
out = open(os.path.join(HERE, "test_curves_markup.txt"), "w")
import Rhino
import System
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Point3d, Polyline, PolylineCurve, Circle, ArcCurve, Ellipse, Plane

for f in ("curves", "markup", "cut", "parts", "pattern", ""):
    sys.path.insert(0, R + f)
MODS = ("SplitCrvByAngle", "smooth_corners", "ReducePoints", "TrimCrvEnds", "KeepCrvEnds", "TrimOutsidePanel",
        "CrvToPolyline", "find_exact_connection", "line_type", "PointsToCrosses", "DotToPanelText",
        "PatternTextStyles", "click_undo")
for m in MODS:
    sys.modules.pop(m, None)

PATCHED = ("GetObjects", "GetObject", "GetReal", "GetString", "GetBoolean", "SelectedObjects", "GetCurveObject", "MessageBox")
saved = dict((n, getattr(rs, n)) for n in PATCHED)
old_doc = sc.doc


def pl(*p):
    return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in p]))


def new_doc(units=Rhino.UnitSystem.Millimeters):
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    doc.ModelUnitSystem = units
    sc.doc = doc
    return doc


def layer(doc, name):
    return doc.Layers.Add(name, System.Drawing.Color.Black)


def add(doc, geom, layer_index=None, group=None, user=None):
    a = Rhino.DocObjects.ObjectAttributes()
    if layer_index is not None:
        a.LayerIndex = layer_index
    if group is not None:
        a.AddToGroup(group)
    for k, v in (user or {}).items():
        a.SetUserString(k, v)
    return doc.Objects.Add(geom, a)


def info(doc, o):
    g = o.Geometry
    return "%s layer=%s groups=%s len=%.2f" % (type(g).__name__, doc.Layers[o.Attributes.LayerIndex].Name,
                                               list(o.Attributes.GetGroupList() or []),
                                               g.GetLength() if isinstance(g, Rhino.Geometry.Curve) else 0)


def section(name, fn):
    out.write("\n=== %s\n" % name)
    so, sys.stdout = sys.stdout, out
    try:
        fn()
        sys.stdout = so
        out.write("\nRESULT %s: OK\n" % name)
    except Exception:
        sys.stdout = so
        out.write("\nRESULT %s: FAILED\n%s\n" % (name, traceback.format_exc()))
    finally:
        sys.stdout = so
        sc.sticky.pop("SplitCrvByAngle_angle", None)
        for n in PATCHED:
            setattr(rs, n, saved[n])
        if sc.doc is not old_doc:
            sc.doc.Dispose()
            sc.doc = old_doc


def reals(*values):
    values = list(values)
    return lambda *a, **k: values.pop(0)


def split_by_angle():
    import SplitCrvByAngle as M
    doc = new_doc()
    li, g = layer(doc, "A"), doc.Groups.Add()
    ell = add(doc, pl((0, 0), (100, 0), (100, 50)), li, g)
    step = add(doc, pl((0, 100), (100, 100), (100.3, 100.3), (100, 150)), li)  # micro step at the corner
    arcs = Rhino.Geometry.PolyCurve()
    arcs.Append(Rhino.Geometry.Line(Point3d(0, 200, 0), Point3d(100, 200, 0)))
    arcs.Append(Rhino.Geometry.Arc(Point3d(100, 200, 0), Rhino.Geometry.Vector3d(0, 1, 0), Point3d(150, 250, 0)))
    arc_id = add(doc, arcs, li)
    straight = add(doc, pl((0, 300), (50, 300), (100, 300.5)), li)
    rs.GetObjects = lambda *a, **k: [ell, step, arc_id, straight]
    rs.GetReal = reals(45.0, 1.0)
    M.main()
    objs = list(doc.Objects)
    for o in objs:
        print(info(doc, o))
    lens = sorted(round(o.Geometry.GetLength(), 1) for o in objs)
    assert len(objs) == 7, len(objs)
    assert doc.Objects.FindId(straight) is not None and doc.Objects.FindId(ell) is None
    assert all(doc.Layers[o.Attributes.LayerIndex].Name == "A" for o in objs)
    assert sum(1 for o in objs if list(o.Attributes.GetGroupList() or []) == [g]) == 2
    assert sc.sticky["SplitCrvByAngle_angle"] == 45.0


def smooth():
    import smooth_corners as M
    doc = new_doc()
    li = layer(doc, "A")
    sq = add(doc, pl((0, 0), (100, 0), (100, 100), (0, 100), (0, 0)), li)
    arcs = Rhino.Geometry.PolyCurve()  # not a polyline: a line and an arc meeting at a corner
    arcs.Append(Rhino.Geometry.Line(Point3d(0, 200, 0), Point3d(100, 200, 0)))
    arcs.Append(Rhino.Geometry.Arc(Point3d(100, 200, 0), Rhino.Geometry.Vector3d(0, 1, 0), Point3d(150, 250, 0)))
    arc_id = add(doc, arcs, li)
    rs.GetObjects = lambda *a, **k: [sq, arc_id]
    rs.GetReal = reals(20.0, 5.0)
    M.main()
    g = doc.Objects.FindId(sq).Geometry
    n_arcs = sum(1 for i in range(g.SegmentCount) if isinstance(g.SegmentCurve(i), ArcCurve))
    print("square: %d arcs, length %.3f (expected %.3f)" % (n_arcs, g.GetLength(), 400 - 8 * 5 + 2 * math.pi * 5))
    assert n_arcs == 4 and abs(g.GetLength() - (400 - 40 + 2 * math.pi * 5)) < 1e-6 and g.IsClosed
    g2 = doc.Objects.FindId(arc_id).Geometry
    print("line + arc: %s, start tangent continuous now: length %.2f" % (type(g2).__name__, g2.GetLength()))
    assert doc.Layers[doc.Objects.FindId(arc_id).Attributes.LayerIndex].Name == "A"
    assert sc.sticky["smooth_corners_angle"] == 20.0 and sc.sticky["smooth_corners_radius"] == 5.0


def reduce_points():
    import ReducePoints as M
    doc = new_doc()
    nurbs = Ellipse(Plane.WorldXY, 500, 300).ToNurbsCurve()
    r = M.reduce(nurbs, 1.0, 10.0, False)
    n0 = M.CrvToPolyline.polyline_copy(nurbs).TryGetPolyline()[1].Count
    print("NURBS ellipse: polyline copy %d points -> %d" % (n0, r.TryGetPolyline()[1].Count))
    assert r is not None and r.TryGetPolyline()[1].Count < n0
    assert Rhino.Geometry.Curve.GetDistancesBetweenCurves(r, nurbs, 0.001)[1] <= 1.1 + 1e-6


def trim_ends():
    import TrimCrvEnds as M
    doc = new_doc(Rhino.UnitSystem.Centimeters)
    asked = []
    a = add(doc, pl((0, 0), (100, 0)))
    rs.GetObjects = lambda *x, **k: [a]
    rs.GetReal = lambda prompt, default, *x, **k: asked.append(default) or 20.0
    rs.GetString = lambda *x, **k: "Both"
    sc.sticky.pop("trim_ends_dist", None)
    M.main()
    print("default in a cm document: %s" % asked[0])
    assert abs(asked[0] - 5.0) < 1e-9 and abs(doc.Objects.FindId(a).Geometry.GetLength() - 60) < 1e-9
    # mode One: two clicks, Undo, Undo, Undo (nothing left), Enter
    b = add(doc, pl((0, 10), (100, 10)))
    picks = [(b, 0.02), (b, 0.9), M.UNDO, M.UNDO, M.UNDO, None]
    lens = []

    def click():
        lens.append(round(doc.Objects.FindId(b).Geometry.GetLength(), 3))
        return picks.pop(0)
    M.click_end = click
    rs.GetReal = lambda *x, **k: 20.0
    rs.GetString = lambda *x, **k: "One"
    M.main()
    print("length before each click: %s" % lens)
    assert lens == [100.0, 80.0, 60.0, 80.0, 100.0, 100.0], lens


def keep_ends():
    import KeepCrvEnds as M
    doc = new_doc()
    li, g = layer(doc, "A"), doc.Groups.Add()
    a = add(doc, pl((0, 0), (100, 0)), li, g)
    rs.GetObjects = lambda *x, **k: [a]
    rs.GetReal = lambda *x, **k: 5.0
    M.main()
    objs = list(doc.Objects)
    for o in objs:
        print(info(doc, o))
    assert len(objs) == 2 and all(abs(o.Geometry.GetLength() - 5) < 1e-9 for o in objs)
    assert all(doc.Layers[o.Attributes.LayerIndex].Name == "A" and g in list(o.Attributes.GetGroupList()) and
               len(list(o.Attributes.GetGroupList())) == 2 for o in objs)


def trim_outside():
    import TrimOutsidePanel as M
    doc = new_doc()
    panel = add(doc, pl((0, 0), (100, 0), (100, 60), (0, 60), (0, 0)))
    through = add(doc, pl((-20, 10), (120, 10)))
    inner = add(doc, pl((10, 50), (90, 50)))
    rs.GetObjects = lambda *x, **k: [through, inner]
    rs.GetObject = lambda *x, **k: panel
    M.main()
    sel = [o for o in doc.Objects if o.IsSelected(False)]
    print("selected after: %s" % sorted(round(o.Geometry.GetLength(), 1) for o in sel))
    assert sorted(round(o.Geometry.GetLength(), 1) for o in sel) == [80.0, 100.0]


def crv_to_polyline():
    import CrvToPolyline as M
    doc = new_doc()
    c = add(doc, ArcCurve(Circle(Point3d(0, 0, 0), 500)))
    rs.GetObjects = lambda *x, **k: [c]
    M.main()
    assert doc.Objects.FindId(c).Geometry.TryGetPolyline()[0]


def linetype():
    import line_type as M
    doc = new_doc()
    a = add(doc, pl((0, 0), (1000, 0)))
    assert not any(lt.Name == M.NAME for lt in doc.Linetypes)
    rs.GetObjects = lambda *x, **k: [a]
    M.main()
    M.main()
    lts = [lt for lt in doc.Linetypes if lt.Name == M.NAME and not lt.IsDeleted]
    o = doc.Objects.FindId(a)
    segs = [(lts[0].GetSegment(i)[0], lts[0].GetSegment(i)[1]) for i in range(lts[0].SegmentCount)]
    print("linetypes named %s: %d, segments %s, object linetype %s, source %s" % (
        M.NAME, len(lts), segs, doc.Linetypes[o.Attributes.LinetypeIndex].Name, o.Attributes.LinetypeSource))
    assert len(lts) == 1 and o.Attributes.LinetypeIndex == lts[0].LinetypeIndex
    assert o.Attributes.LinetypeSource == Rhino.DocObjects.ObjectLinetypeSource.LinetypeFromObject
    assert segs == [(400.0, True), (2.0, False)], segs


def crosses():
    import PointsToCrosses as M
    for shape in ("Cross", "Circle"):
        doc = new_doc()
        li, g = layer(doc, "A"), doc.Groups.Add()
        layer(doc, "Last")  # a later layer: nothing may land on it
        p = add(doc, Rhino.Geometry.Point(Point3d(10, 20, 0)), li, g, {"Notch": "Point"})
        dot = add(doc, Rhino.Geometry.TextDot("x", Point3d(50, 20, 0)), li)
        rs.SelectedObjects = lambda *x, **k: [p, dot]
        rs.GetString = lambda *x, **k: shape
        rs.GetReal = lambda *x, **k: 2.0
        rs.GetBoolean = lambda *x, **k: [True]
        M.points_to_crosses()
        objs = list(doc.Objects)
        for o in objs:
            print(info(doc, o), "UserText", o.Attributes.GetUserStrings().Count)
        assert len(objs) == (4 if shape == "Cross" else 2)
        assert all(doc.Layers[o.Attributes.LayerIndex].Name == "A" and o.Attributes.GetUserStrings().Count == 0 for o in objs)
        mine = [o for o in objs if g in list(o.Attributes.GetGroupList() or [])]
        assert len(mine) == (2 if shape == "Cross" else 1)
        if shape == "Cross":
            assert all(len(list(o.Attributes.GetGroupList())) == (2 if o in mine else 1) for o in objs)
            assert all(abs(o.Geometry.GetLength() - 4) < 1e-9 for o in objs)
        else:
            assert all(abs(o.Geometry.GetLength() - 4 * math.pi) < 1e-6 for o in objs)
        doc.Dispose()
        sc.doc = old_doc


def dot_to_panel_text():
    import DotToPanelText as M
    doc = new_doc()
    M.pts.ensure_styles(doc)
    style = M.pts.label_style(doc, M.STICKY)
    panel = Ellipse(Plane.WorldXY, 500, 300).ToNurbsCurve()
    tid = M.place_text(doc, "P7", panel, Point3d(400, 250, 0), style, Rhino.DocObjects.ObjectAttributes(), doc.ModelAbsoluteTolerance)
    bb = doc.Objects.FindId(tid).Geometry.GetBoundingBox(True)
    corners_ = [Point3d(x, y, 0) for x in (bb.Min.X, bb.Max.X) for y in (bb.Min.Y, bb.Max.Y)]
    inside = [panel.Contains(c, Plane.WorldXY, 0.01) == Rhino.Geometry.PointContainment.Inside for c in corners_]
    print("text box %.1f..%.1f x %.1f..%.1f, corners inside the NURBS panel: %s" % (bb.Min.X, bb.Max.X, bb.Min.Y, bb.Max.Y, inside))
    assert all(inside)


def exact_connection():
    import find_exact_connection as M
    doc = new_doc()
    c = add(doc, pl((0, 100), (200, 100)))
    asked = []
    rs.GetCurveObject = lambda *x, **k: (c, False, 0, Point3d(0, 100, 0), 0.0, "")
    rs.GetObject = lambda *x, **k: None
    rs.GetPoint = lambda *x, **k: Point3d(100, 0, 0)
    rs.GetReal = lambda prompt, default=None, *x, **k: asked.append(default) or 125.0
    sc.sticky.pop("find_exact_connection_length", None)
    M.find_exact_connection()
    M.find_exact_connection()
    lines = [o.Geometry.GetLength() for o in doc.Objects if isinstance(o.Geometry, Rhino.Geometry.Curve) and o.Id != c]
    print("offered lengths: %s, lines: %s" % (asked, [round(x, 3) for x in lines]))
    assert asked == [None, 125.0] and len(lines) == 4 and all(abs(x - 125) < 1e-6 for x in lines)


saved_getpoint = rs.GetPoint
try:
    for name, fn in (("SplitCrvByAngle", split_by_angle),
                     ("smooth_corners", smooth), ("ReducePoints", reduce_points), ("TrimCrvEnds", trim_ends),
                     ("KeepCrvEnds", keep_ends), ("TrimOutsidePanel", trim_outside), ("CrvToPolyline", crv_to_polyline),
                     ("line_type", linetype), ("PointsToCrosses", crosses), ("DotToPanelText", dot_to_panel_text),
                     ("find_exact_connection", exact_connection)):
        section(name, fn)
finally:
    rs.GetPoint = saved_getpoint
    sc.doc = old_doc
    text = open(out.name).read() if out.close() is None else ""
    open(out.name, "a").write("OK\n" if "FAILED" not in text else "FAILED\n")
