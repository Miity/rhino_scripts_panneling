# -*- coding: utf-8 -*-
"""Check of JoinCorner with Layout=Yes parts (markup on the panel + part above) in Rhino 8:
DOTNET_ROLL_FORWARD=Major "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode" script <this file>
The result is written to test_join_corner_layout.txt next to it."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(HERE, "test_join_corner_layout.txt"), "w")
made = []
try:
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    from Rhino.Geometry import Point3d, Polyline, PolylineCurve, TextEntity, Vector3d
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "parts"))
    for m in ("ReinfCircle", "ZipCover", "JoinCorner"):  # live Rhino keeps old module versions
        sys.modules.pop(m, None)
    import ZipCover
    import JoinCorner as J
    import ReinfCircle as RC

    Z, tol, doc = Vector3d.ZAxis, 0.001, sc.doc
    # panel 100×50, flaps W=10 over the top and right edges, Layout=Yes
    pan = PolylineCurve(Polyline([Point3d(0, 0, 0), Point3d(100, 0, 0), Point3d(100, 50, 0),
                                  Point3d(0, 50, 0), Point3d(0, 0, 0)]))
    marks = []
    for click in (Point3d(50, 51, 0), Point3d(101, 25, 0)):
        crv = ZipCover.flap(pan, click, 10, 30, Z, tol)[0]
        te = TextEntity.Create("ZC 10", rs.WorldXYPlane(), doc.DimStyles.Current, False, 0, 0)
        full, mk = RC.add_part(doc, [crv], te, RC.off_panel(crv, [pan], tol), doc.CreateDefaultAttributes())
        made += full + mk
        marks.append(mk[0])
    ids = J.to_full(marks)  # markup selected → full parts above
    assert len(ids) == 2 and all(rs.IsCurveClosed(i) for i in ids)
    up = J.link_of(ids[0])[1]
    res = J.join(rs.coercecurve(ids[0]), rs.coercecurve(ids[1]), Point3d(105, 55, 0) + up, tol)
    assert len(res) == 1 and res[0].IsClosed, res
    la, lb = J.link_of(ids[0])[0], J.link_of(ids[1])[0]
    J.rebuild_markup(doc, res, [(ids[0], la), (ids[1], lb)], up, tol)
    new = [o for o in J.linked(la, True) if rs.IsCurve(o)]
    made += J.linked(la, True) + J.linked(lb, True)
    # new markup: (0,50)→(0,60)→(110,60)→(110,0)→(100,0) = 10 + 110 + 60 + 10
    assert len(new) == 1 and abs(rs.CurveLength(new[0]) - 190) < 1e-6, [rs.CurveLength(o) for o in new]
    assert not [o for o in J.linked(lb, True) if rs.IsCurve(o)]  # old markup of the second one — deleted
    out.write("OK\n")
except Exception:
    out.write(traceback.format_exc())
finally:
    try:
        rs.DeleteObjects([o for o in set(made) if rs.IsObject(o)])
    except Exception:
        pass
out.close()
