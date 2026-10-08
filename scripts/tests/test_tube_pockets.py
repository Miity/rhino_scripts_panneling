# -*- coding: utf-8 -*-
"""Check of TubePockets.pocket in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_tube_pockets.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_tube_pockets.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, LineCurve, Point3d, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ZipCover", "OffsetRigid", "TubePockets"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import TubePockets as M

    Z, tol = Vector3d.ZAxis, 0.001
    line = LineCurve(Point3d(0, 0, 0), Point3d(1000, 0, 0))
    # W 600 centred, H 100 up, Trim 50, no SA: trapezoid (600+500)/2·100
    outline, seg, mark, folds, simple = M.pocket(line, Point3d(300, 40, 0), 600, 100, 50, True, Z, tol)
    assert outline.IsClosed
    assert abs(AreaMassProperties.Compute(outline).Area - 55000) < 1e-3
    assert abs(seg.PointAtStart.X - 200) < 1e-6 and abs(seg.PointAtEnd.X - 800) < 1e-6
    assert abs(mark.PointAtStart.X - 500) < 1e-6 and abs(mark.PointAtStart.Y) < 1e-6
    assert abs(mark.PointAtEnd.Y - 10) < 1e-6  # H/10 into the pocket
    bb = outline.GetBoundingBox(True)
    assert abs(bb.Min.Y) < 1e-6 and abs(bb.Max.Y - 100) < 1e-6
    # W 0 — the whole line; click below → pocket downward
    outline, seg, mark, folds, simple = M.pocket(line, Point3d(300, -40, 0), 0, 100, 50, False, Z, tol)
    assert abs(AreaMassProperties.Compute(outline).Area - 95000) < 1e-3 and mark is None
    assert outline.GetBoundingBox(True).Min.Y < -99
    # Trim too large → reason as a string
    assert not isinstance(M.pocket(line, Point3d(0, 40, 0), 80, 100, 50, False, Z, tol), tuple)
    # panel 1000×500: click near the top edge → pocket downward (inward), bottom on the edge; both directions
    from Rhino.Geometry import Polyline, PolylineCurve
    pts = [Point3d(0, 0, 0), Point3d(1000, 0, 0), Point3d(1000, 500, 0), Point3d(0, 500, 0), Point3d(0, 0, 0)]
    for order in (pts, pts[::-1]):
        panel = PolylineCurve(Polyline(order))
        edge = M.pick_edge(panel, Point3d(400, 520, 0), 30, tol)[3]
        assert abs(edge.GetLength() - 1000) < 1e-6 and abs(edge.PointAtStart.Y - 500) < 1e-6
        outline, seg, mark, folds, simple = M.pocket(edge, M.inward(panel, edge, Z), 600, 100, 50, True, Z, tol)
        bb = outline.GetBoundingBox(True)
        assert abs(bb.Min.Y - 400) < 1e-6 and abs(bb.Max.Y - 500) < 1e-6, bb
        assert abs(AreaMassProperties.Compute(outline).Area - 55000) < 1e-3
    # UpdateTubePockets.read_pocket: pocket in the document → parameters; without UserText — from geometry
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    sys.modules.pop("UpdateTubePockets", None)
    import UpdateTubePockets as U
    line = LineCurve(Point3d(0, 0, 0), Point3d(1000, 0, 0))
    toward = Point3d(300, 40, 0)
    res = M.pocket(line, toward, 600, 100, 50, True, Z, tol) + (toward,)
    before = set(rs.AllObjects() or [])
    M.add_pocket(sc.doc, res, 100, 50, True, 7, sc.doc.CreateDefaultAttributes(), Z, tol)
    ids = [o for o in rs.AllObjects() if o not in before]
    try:
        for legacy in (False, True):
            if legacy:
                for o in ids:
                    for k in U.KEYS:
                        rs.SetUserText(o, "TP_" + k, None)
                    if rs.IsText(o):  # old pockets: h in the label (cm)
                        rs.TextObjectText(o, u"T7  h=%g" % (100 * Rhino.RhinoMath.UnitScale(
                            sc.doc.ModelUnitSystem, Rhino.UnitSystem.Centimeters)))
            p = U.read_pocket(ids, tol)
            assert p["n"] == 7 and p["H"] == 100 and abs(p["Trim"] - 50) < 1e-6, p
            assert p["Notch"] == 1 and abs(p["seg"].GetLength() - 600) < 1e-6, (legacy, p)
            r = M.pocket(p["seg"], p["toward"], 0, 100, 30, True, Z, tol)  # Trim 50 → 30
            assert abs(AreaMassProperties.Compute(r[0]).Area - 57000) < 1e-3
    finally:
        rs.DeleteObjects(ids)
    # Hem: fold lines in sublayer <layer>::Fold, in the group; Update takes the contour layer and Hem from UserText
    res = M.pocket(line, toward, 600, 100, 0, False, Z, tol, False, 20) + (toward,)
    attrs = sc.doc.CreateDefaultAttributes()
    before = set(rs.AllObjects() or [])
    M.add_pocket(sc.doc, res, 100, 0, False, 8, attrs, Z, tol, False, 20)
    ids = [o for o in rs.AllObjects() if o not in before]
    base = sc.doc.Layers[attrs.LayerIndex].FullPath
    try:
        folds = [o for o in ids if rs.ObjectLayer(o) == base + "::Fold"]
        assert len(folds) == 2 and all(rs.ObjectGroups(o) == rs.ObjectGroups(ids[0]) for o in ids)
        p = U.read_pocket(list(reversed(ids)), tol)
        assert p["Hem"] == 20 and p["attrs"].LayerIndex == attrs.LayerIndex, p
    finally:
        rs.DeleteObjects(ids)
        rs.DeleteLayer(base + "::Fold")
    # markup in place + full part at up: markup is open (ends + top, without seam line); Update sees the pair
    up = Vector3d(0, 10000, 0)
    res = M.pocket(line, toward, 600, 100, 50, True, Z, tol, False, 20)
    assert not res[4].IsClosed and abs(res[4].GetLength() - (500 + 2 * (50 ** 2 + 100 ** 2) ** 0.5)) < 1e-6
    before = set(rs.AllObjects() or [])
    M.add_pocket(sc.doc, res + (toward,), 100, 50, True, 9, attrs, Z, tol, False, 20, up)
    ids = [o for o in rs.AllObjects() if o not in before]
    try:
        markup = [o for o in ids if rs.GetUserText(o, "TP_Markup")]
        full = [o for o in ids if o not in markup]
        assert len(markup) == 2 and rs.ObjectGroups(markup[0]) == rs.ObjectGroups(markup[1])
        assert all(rs.BoundingBox(o)[0].Y < 1000 for o in markup)
        assert all(rs.BoundingBox(o)[0].Y > 9000 for o in full) and len(full) == 5  # contour, 2 folds, mark, text (seam line not drawn)
        assert set(U.tagged(markup[0], "9", False)) == set(o for o in full if rs.ObjectLayer(o) == rs.ObjectLayer(markup[0]))
        assert len(rs.ObjectGroups(full[0])) == 1 and all(rs.ObjectGroups(o) == rs.ObjectGroups(full[0]) for o in ids)  # one group
        p = U.read_pocket([o for o in rs.ObjectsByGroup(rs.ObjectGroups(full[0])[0]) if not rs.GetUserText(o, "TP_Markup")], tol)
        assert p["up"] == up and set(p["markup"]) == set(markup) and p["n"] == 9, p
        seg = p["seg"].DuplicateCurve()
        seg.Translate(-up)
        assert abs(seg.PointAtStart.Y) < 1e-6  # the edge returns to the markup position
        # UpdateTubePockets: select the markup on the panel, H 100 → 120: rebuilt, again one group (markup + part up)
        class Opts(object):  # the option prompt: H changed, Enter
            def __getattr__(self, name):
                return lambda *a: None
            def AddOptionDouble(self, name, o):
                if name == "H":
                    o.CurrentValue = 120.0
            def Get(self):
                return Rhino.Input.GetResult.Nothing
        class NS(object):  # Rhino as U sees it, with some names replaced (.NET namespaces can't be patched)
            def __init__(self, real, **over):
                self.real, self.over = real, over
            def __getattr__(self, name):
                return self.over[name] if name in self.over else getattr(self.real, name)
        get_objects = rs.GetObjects
        U.Rhino = NS(Rhino, Input=NS(Rhino.Input, Custom=NS(Rhino.Input.Custom, GetOption=Opts)))
        rs.GetObjects = lambda *a, **k: [markup[0]]
        try:
            U.main()
        finally:
            U.Rhino, rs.GetObjects = Rhino, get_objects
        ids = [o for o in rs.AllObjects() if o not in before]
        g = rs.ObjectGroups(ids[0])
        assert len(ids) == 7 and len(g) == 1 and all(rs.ObjectGroups(o) == g for o in ids), (len(ids), g)
        assert all(rs.GetUserText(o, "TP_H") == "120" for o in ids)
    finally:
        rs.DeleteObjects(ids)
        if rs.IsLayer(base + "::Fold"):
            rs.DeleteLayer(base + "::Fold")
    # Rigid: arc R1000 (45°..135°), pocket towards the centre H 100: rigid — same length, centre moved exactly by H;
    # standard — arc R900 (shorter by 0.9)
    from Rhino.Geometry import Arc, ArcCurve
    import math
    arc = ArcCurve(Arc(Point3d(707.1068, 707.1068, 0), Point3d(0, 1000, 0), Point3d(-707.1068, 707.1068, 0)))
    rig = M.pocket_side(arc, Point3d(0, 0, 0), 100, Z, tol, True)
    std = M.pocket_side(arc, Point3d(0, 0, 0), 100, Z, tol, False)
    assert abs(rig.GetLength() - arc.GetLength()) < 1e-3
    assert abs(rig.PointAt(rig.Domain.Mid).Y - 900) < 1e-3, rig.PointAt(rig.Domain.Mid)
    assert abs(std.GetLength() - 0.9 * arc.GetLength()) < 1e-2
    res = M.pocket(arc, Point3d(0, 0, 0), 0, 100, 50, True, Z, tol, True)
    assert isinstance(res, tuple) and res[0].IsClosed, res
    # Hem 20: rectangular pocket (Trim 0) 600×100 → ends outward by 20: 640×100, two fold lines x=200 / 800
    outline, seg, mark, folds, simple = M.pocket(line, Point3d(300, 40, 0), 600, 100, 0, False, Z, tol, False, 20)
    assert abs(AreaMassProperties.Compute(outline).Area - 64000) < 1e-3
    assert len(folds) == 2 and sorted(round(f.PointAtStart.X) for f in folds) == [200, 800]
    assert abs(folds[0].GetLength() - 100) < 1e-6
    # with Trim 50 (slanted end): bottom (edge) extends to x=200−10√5 (end ⟂ slant by 20), top — farther from the edge; contour closed
    outline, seg, mark, folds, simple = M.pocket(line, Point3d(300, 40, 0), 600, 100, 50, False, Z, tol, False, 20)
    bb = outline.GetBoundingBox(True)
    assert outline.IsClosed and abs(bb.Min.X - (200 - 10 * 5 ** 0.5)) < 1e-6 and abs(bb.Max.X - (800 + 10 * 5 ** 0.5)) < 1e-6, bb
    assert AreaMassProperties.Compute(outline).Area > 55000 + 2 * 20 * 100
    # Hem on an arc with Rigid
    res = M.pocket(arc, Point3d(0, 0, 0), 0, 100, 50, True, Z, tol, True, 20)
    assert isinstance(res, tuple) and res[0].IsClosed and len(res[3]) == 2, res
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
