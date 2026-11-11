# -*- coding: utf-8 -*-
"""Update existing Rinforzo strips with new parameters (W).
Select any part of a strip (or several with a window) — the strip is rebuilt in place from its panel and the edge
it sits on, with the same layer. Only the parameters you changed in the options change; the rest stay each strip's own.
Parameters are read from UserText RF_* on the strip contour (RF_Panel — the panel it was made on). The edge is found
again from where the strip lies (the panel point nearest to the middle of the strip), so a strip moved with its
panel is still found; a panel that is gone — the strip is skipped.
Option Seam: Yes — after the update the view zooms to the parts and pattern/Seams.py runs on them (the same second step as
in Rinforzo). Default Yes if a selected strip had a seam cut line. A rebuilt strip loses its old cut line (it is in
the strip's group), so with Seam=No the allowance is dropped (a warning is printed). Seam=Yes with no other change —
nothing is rebuilt, Seams just runs on the existing parts.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("Rinforzo", None)
import Rinforzo as RF
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pattern"))
sys.modules.pop("Seams", None)
import Seams
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.modules.pop("click_undo", None)
from click_undo import Steps
sys.modules.pop("UpdateTubePockets", None)
from UpdateTubePockets import update  # the steps of an Update script: select, options, rebuild, Seams

KEYS = ("W",)


def read_strip(ids, tol):
    """dict with the strip's parameters (UserText RF_*) and where it sits, or a reason string."""
    contours = [i for i in ids if rs.IsCurve(i) and rs.GetUserText(i, "RF_W")]
    if len(contours) != 1:
        return u"not a Rinforzo strip (no RF_W contour)"
    oid = contours[0]
    panel_id = rs.GetUserText(oid, "RF_Panel")
    if not panel_id or not rs.IsCurve(panel_id):
        return u"the panel of this strip is gone"
    up = rs.GetUserText(oid, "LayoutUp")
    up = Rhino.Geometry.Vector3d(*[float(x) for x in up.split(",")]) if up else Rhino.Geometry.Vector3d.Zero
    panel = rs.coercecurve(panel_id)
    box = rs.coercecurve(oid).GetBoundingBox(True)
    # ponytail: the middle of the strip box is nearest to its own edge unless the strip is wider than the edge is long
    click = panel.PointAt(panel.ClosestPoint(box.Center - up)[1])
    ok, plane = panel.TryGetPlane(tol)
    vals = dict((k, float(rs.GetUserText(oid, "RF_" + k))) for k in KEYS + ("Angle",))
    vals.update(part=oid, name=u"Rinforzo", layout=bool(int(rs.GetUserText(oid, "RF_Layout"))), panel_id=panel_id, panel=panel,
                click=click, had_seam=any(rs.GetUserText(i, Seams.KEY) for i in ids), ids=list(ids), up=up,
                normal=plane.ZAxis if ok else rs.ViewCPlane().ZAxis,
                attrs=sc.doc.Objects.FindId(rs.coerceguid(oid)).Attributes.Duplicate())
    return vals


HELP = u"""Options:
  W — strip width from the edge into the panel
  Seam — Yes: run the seam allowance step (Seams.py) on the strips afterwards; rebuilt strips lose the old cut line"""  # printed at start — visible under the option fields


def rebuild(s, doc, tol):
    """The strip again with its new width. (label, full contour id) or None (skipped)."""
    s["attrs"].RemoveFromAllGroups()
    for key in list(s["attrs"].GetUserStrings().AllKeys):  # the old data (RF_*, PartLink…) must not go to every new object
        s["attrs"].DeleteUserString(key)
    sc.sticky[RF.UP_KEY] = s["up"].Length  # the full part goes up as far as before (add_part uses CPlane Y)
    rs.DeleteObjects(s["ids"])
    steps = Steps(doc)
    steps.start()
    got = RF.make(doc, s["panel_id"], s["panel"], s["click"], s["W"], s["Angle"], s["layout"],
                  s["normal"], tol, s["attrs"], steps)
    return (got[1], got[0][0]) if got is not None else None


def main():
    print(HELP)
    saved_up = sc.sticky.get(RF.UP_KEY)
    try:
        update(u"strips", read_strip, rebuild, KEYS, lowest={"W": 0.001})
    finally:
        if saved_up is not None:
            sc.sticky[RF.UP_KEY] = saved_up


if __name__ == "__main__":
    main()
