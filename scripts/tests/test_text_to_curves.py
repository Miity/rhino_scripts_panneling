# -*- coding: utf-8 -*-
"""TextToCurves: дзеркальний / перевернутий текст «L» → криві читаються як на екрані з Top.
Запуск у Rhino 8: DOTNET_ROLL_FORWARD=Major rhinocode script <цей файл>; результат — у OUT."""
import os
import sys
import traceback

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_text_to_curves.txt")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))

try:
    import Rhino
    import Rhino.Geometry as rg
    import scriptcontext as sc
    import TextToCurves as M

    doc = Rhino.RhinoDoc.CreateHeadless(None)
    sc.doc = doc
    X, Y, Z = rg.Vector3d.XAxis, rg.Vector3d.YAxis, rg.Vector3d.ZAxis

    def l_shape(plane):
        """'L' читається, якщо вертикальна риска зліва, а горизонтальна знизу (вид Top)."""
        te = rg.TextEntity.Create(u"L", plane, doc.DimStyles.Current, False, 0, 0)
        crvs = M.text_curves(te, X, Y)
        pts = []
        for c in crvs:
            pts.extend(c.ToPolyline(0.01, 0.1, 0, 0).ToPolyline())
        bb = rg.BoundingBox(pts)
        w, h = bb.Max.X - bb.Min.X, bb.Max.Y - bb.Min.Y
        left = sum(1 for p in pts if p.X < bb.Min.X + w * 0.3)
        right = sum(1 for p in pts if p.X > bb.Max.X - w * 0.3)
        low = sum(1 for p in pts if p.Y < bb.Min.Y + h * 0.3)
        high = sum(1 for p in pts if p.Y > bb.Max.Y - h * 0.3)
        return left > right and low > high

    o = rg.Point3d(10, 5, 0)
    assert l_shape(rg.Plane(o, X, Y)), "normal"
    assert l_shape(rg.Plane(o, X, -Y)), "mirrored (normal -Z)"
    assert l_shape(rg.Plane(o, -X, Y)), "mirrored left-right"
    assert l_shape(rg.Plane(o, -X, -Y)), "rotated 180"
    res = "ok"
except Exception:
    res = traceback.format_exc()

with open(OUT, "w") as f:
    f.write(res)
