# -*- coding: utf-8 -*-
"""Check of MergeOutline (merge + main on a headless doc) in Rhino 8 (needs RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_merge_outline.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_merge_outline.txt"), "w")
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import AreaMassProperties, Arc, Curve, LineCurve, Point3d, Polyline, PolylineCurve
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("JoinCorner", "MergeOutline"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import MergeOutline as M

    tol = 0.001
    def pl(*p, **k):
        return PolylineCurve(Polyline([Point3d(x, y, 0) for x, y in (p + (p[0],) if k.get("closed") else p)]))
    def area(c):
        return AreaMassProperties.Compute(c).Area
    def total(cs):
        return sum(c.GetLength() for c in cs)

    # panel with a round right side (closed, seam on the right edge), strip B outside it ending on its corners
    right = Arc(Point3d(100, 0, 0), Point3d(120, 50, 0), Point3d(100, 100, 0)).ToNurbsCurve()
    A = Curve.JoinCurves([pl((100, 100), (0, 100), (0, 0), (100, 0)), right], tol)[0]
    A.ChangeClosedCurveSeam(A.Domain.ParameterAt(0.8))  # seam somewhere on the inner edge
    arcB = Arc(Point3d(110, 0, 0), Point3d(140, 50, 0), Point3d(110, 100, 0)).ToNurbsCurve()
    B = Curve.JoinCurves([LineCurve(Point3d(100, 0, 0), Point3d(110, 0, 0)), arcB,
                          LineCurve(Point3d(110, 100, 0), Point3d(100, 100, 0))], tol)[0]
    area_union = area(A) + AreaMassProperties.Compute(
        Curve.JoinCurves([B, right], tol)[0]).Area
    res = M.merge([A, B], tol)
    assert isinstance(res, tuple), res
    outline, rest, left = res
    assert not left
    assert outline.IsClosed and abs(area(outline) - area_union) < 0.01, (area(outline), area_union)
    assert [k for k, _ in rest] == [0] and len(rest[0][1]) == 1, rest  # old right edge, one open curve of A
    inner = rest[0][1][0]
    assert not inner.IsClosed and abs(inner.GetLength() - right.GetLength()) < 0.01, inner.GetLength()
    assert abs(total([outline]) - (A.GetLength() - right.GetLength() + B.GetLength())) < 0.01
    # the order of the curves does not matter
    res2 = M.merge([B, A], tol)
    assert isinstance(res2, tuple) and abs(area(res2[0]) - area_union) < 0.01 and [k for k, _ in res2[1]] == [1]

    # polylines stay one clean polyline: 100×100 square + open U strip around its right side
    sq = pl((0, 0), (100, 0), (100, 100), (0, 100), closed=True)
    u = pl((100, 0), (110, 0), (110, 100), (100, 100))
    outline, rest, _ = M.merge([sq, u], tol)
    ok, poly = outline.TryGetPolyline()
    # 4 corners + closing point (+ the seam vertex left where the pieces were joined)
    assert ok and poly.Count <= 6 and  abs(area(outline) - 11000) < 1e-6, (ok, poly.Count, list(poly))
    assert len(rest) == 1 and abs(rest[0][1][0].GetLength() - 100) < 1e-6

    # two overlapping panels: outline of both, the edges inside stay as open curves (one per source)
    p1, p2 = pl((0, 0), (10, 0), (10, 10), (0, 10), closed=True), pl((5, 5), (15, 5), (15, 15), (5, 15), closed=True)
    outline, rest, _ = M.merge([p1, p2], tol)
    assert abs(area(outline) - (100 + 100 - 25)) < 1e-6, area(outline)
    assert sorted(k for k, _ in rest) == [0, 1] and all(abs(total(c) - 10) < 1e-6 for _, c in rest), rest

    # a stray tick (touching the panel from inside, as seam ticks do) and a far curve are left out, not an error
    tick = pl((50, 0), (50, 10))
    far = pl((300, 0), (310, 0))
    outline, rest, left = M.merge([sq, u, tick, far], tol)
    assert left == [2, 3] and abs(area(outline) - 11000) < 1e-6 and [k for k, _ in rest] == [0], (left, rest)

    # errors (a message, not a tuple): no area, separate areas, different planes
    for bad in (pl((200, 0), (210, 0), (210, 10)), pl((200, 0), (210, 0), (210, 10), (200, 10), closed=True),
                PolylineCurve([Point3d(0, 0, 5), Point3d(10, 0, 5), Point3d(10, 10, 6)])):
        assert not isinstance(M.merge([sq, bad], tol), tuple)

    # main on a headless doc: layer / group / UserText stay on the panel, B deleted and its group merged
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    sc.doc = doc
    rs.AddLayer("Parts")
    rs.AddLayer("Panels", parent="Parts")
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath("Parts::Panels", -1)
    attrs.SetUserString("Part", "P13")
    a_id = doc.Objects.AddCurve(A, attrs)
    b_id = doc.Objects.AddCurve(B)
    dot = doc.Objects.AddTextDot("P13", Point3d(5, 5, 0))
    g = rs.AddGroup()
    rs.AddObjectsToGroup([a_id, dot], g)
    rs.GetObjects = lambda *a, **k: [b_id, a_id]  # closed one is taken first anyway
    M.main()
    assert doc.Objects.FindId(b_id) is None
    panel = doc.Objects.FindId(a_id)
    assert panel is not None and panel.Geometry.IsClosed and abs(area(panel.Geometry) - area_union) < 0.01
    assert rs.GetUserText(a_id, "Part") == "P13" and rs.ObjectLayer(a_id) == "Parts::Panels"
    assert g in (rs.ObjectGroups(a_id) or []) and dot in rs.ObjectsByGroup(g)
    opens = [o for o in doc.Objects if o.Id not in (a_id, dot) and o.ObjectType == Rhino.DocObjects.ObjectType.Curve]
    assert len(opens) == 1 and not opens[0].Geometry.IsClosed
    assert rs.GetUserText(opens[0].Id, "Part") is None and rs.ObjectLayer(opens[0].Id) == "Parts::Panels"
    assert g in (rs.ObjectGroups(opens[0].Id) or [])
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
