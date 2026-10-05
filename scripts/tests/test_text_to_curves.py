# -*- coding: utf-8 -*-
"""TextToCurves: текст «L» під кутами 0–355° (звичайний і після Mirror), збережений у .3dm,
після читання з файлу → криві не дзеркальні (як на екрані з Top), а Explode — дзеркальні.
Запуск у Rhino 8: DOTNET_ROLL_FORWARD=Major rhinocode script <цей файл>; результат — у OUT."""
import math
import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "test_text_to_curves.txt")
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "markup"))

try:
    import Rhino
    import Rhino.Geometry as rg
    import scriptcontext as sc
    import TextToCurves as M
    try:
        reload(M)
    except NameError:
        import importlib
        importlib.reload(M)  # rhinocode тримає старий модуль між запусками

    Z = rg.Vector3d.ZAxis
    o = rg.Point3d(10, 5, 0)
    frames = {}
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    for deg in range(0, 360, 5):
        a = math.radians(deg)
        u = rg.Vector3d(math.cos(a), math.sin(a), 0)
        v = rg.Vector3d.CrossProduct(Z, u)
        for name, mirror in (("n", None), ("m", u), ("mx", v)):
            te = rg.TextEntity.Create(u"L", rg.Plane(o, u, v), doc.DimStyles.Current, False, 0, 0)
            if mirror is not None:  # як команда Mirror: дзеркалять готовий текст
                te.Transform(rg.Transform.Mirror(o, mirror))
            frames[doc.Objects.AddText(te)] = (name, deg, [rg.Plane(o, u, v), rg.Plane(o, -u, -v)])
    path = os.path.join(tempfile.gettempdir(), "test_text_to_curves.3dm")
    doc.Write3dmFile(path, Rhino.FileIO.FileWriteOptions())
    doc = Rhino.RhinoDoc.OpenHeadless(path)  # як у користувача: текст прочитаний із файлу
    sc.doc = doc

    def readable(crvs, frame):
        """'L' не дзеркальне, якщо в frame риска зліва, а горизонталь знизу."""
        pts = []
        for c in crvs:
            pts.extend(frame.RemapToPlaneSpace(p)[1] for p in c.ToPolyline(0.01, 0.1, 0, 0).ToPolyline())
        bb = rg.BoundingBox(pts)
        w, h = bb.Max.X - bb.Min.X, bb.Max.Y - bb.Min.Y
        left = sum(1 for p in pts if p.X < bb.Min.X + w * 0.3)
        right = sum(1 for p in pts if p.X > bb.Max.X - w * 0.3)
        low = sum(1 for p in pts if p.Y < bb.Min.Y + h * 0.3)
        high = sum(1 for p in pts if p.Y > bb.Max.Y - h * 0.3)
        return left > right and low > high

    bad, exploded_bad = [], 0
    for obj in doc.Objects:
        name, deg, fr = frames[obj.Id]
        if not any(readable(M.text_curves(obj.Geometry), f) for f in fr):
            bad.append("%s%d" % (name, deg))
        exploded = [g for g in obj.Geometry.Explode() if isinstance(g, rg.Curve)]
        exploded_bad += not any(readable(exploded, f) for f in fr)
    assert not bad, "mirrored: " + " ".join(bad)
    assert exploded_bad, "Explode більше не дзеркалить — перевірка нічого не ловить"
    res = "ok (Explode дав дзеркальних: %d із %d)" % (exploded_bad, len(frames))

    # Реальний файл: у p1.3dm Explode дає дзеркальні P3, CZ 20, Can3, Z2 (звірено знімком екрана).
    P1 = "/Users/dmytro/Desktop/p1.3dm"
    if os.path.exists(P1):
        doc = Rhino.RhinoDoc.OpenHeadless(P1)
        sc.doc = doc
        for obj in doc.Objects:
            te = obj.Geometry
            if not isinstance(te, rg.TextEntity):
                continue
            got = [c.PointAtStart for c in M.text_curves(te)]
            raw = [g.PointAtStart for g in te.Explode() if isinstance(g, rg.Curve)]
            assert max(a.DistanceTo(b) for a, b in zip(got, raw)) > 1.0, te.PlainText
        res += "; p1.3dm ok"
except Exception:
    res = traceback.format_exc()

with open(OUT, "w") as f:
    f.write(res)
