# -*- coding: utf-8 -*-
"""Перевірка Seam.strip у Rhino 8 (потрібен RhinoCommon):
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <цей файл>
Результат пишеться в test_seam.txt поруч."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_seam.txt"), "w")
try:
    from Rhino.Geometry import AreaMassProperties, Point3d, Polyline, PolylineCurve, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    import Seam as M

    Z, tol = Vector3d.ZAxis, 0.001
    # Г-подібне ребро 100 + 50, припуск 10 назовні (з боку -Y): гострий кут → площа = 10·(100+50) + 10·10
    edge = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(100, 0, 0), Point3d(100, 50, 0)]))
    curves, off = M.strip(edge, Point3d(50, -5, 0), 10, Z, tol)
    assert len(curves) == 1 and curves[0].IsClosed
    area = AreaMassProperties.Compute(curves[0]).Area
    assert abs(area - 1600) < 1e-3, area
    assert abs(off.PointAtStart.Y + 10) < 1e-6  # офсет з боку кліку
    pl = M.label_frame(edge, off, Z)
    assert -10 < pl.Origin.Y < 0 or pl.Origin.X > 100, pl.Origin  # підпис усередині смуги

    # замкнений квадрат 100 → кільце: копія + офсет 120×120
    sq = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(100, 0, 0), Point3d(100, 100, 0),
                                 Point3d(0, 100, 0), Point3d(0, 0, 0)]))
    curves, off = M.strip(sq, Point3d(-5, 50, 0), 10, Z, tol)
    assert len(curves) == 2
    assert abs(AreaMassProperties.Compute(off).Area - 14400) < 1e-3
    assert M.sewing_lengths(100, 20) == [10, 30, 50, 70, 90]  # логіка sewing_points підтягується
    # точки шва: копія ребра + точки, усе в шарі з attrs (Parts::Seam), а не в шарі вхідної лінії
    import Rhino
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    import System
    seam = doc.Layers.Add("Seam", System.Drawing.Color.Black)
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = seam
    line = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(100, 0, 0)]))
    ids = M.add_sewing_points(doc, line, 20, attrs)
    assert len(ids) == 6, len(ids)  # копія + 5 точок (10, 30, 50, 70, 90)
    assert all(doc.Objects.FindId(i).Attributes.LayerIndex == seam for i in ids)
    doc.Dispose()
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
