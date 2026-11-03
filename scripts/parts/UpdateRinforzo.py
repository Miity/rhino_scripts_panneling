# -*- coding: utf-8 -*-
"""Update existing Rinforzo strips with new parameters (W / Plus).
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

KEYS = ("W", "Plus")


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
    vals.update(contour=oid, layout=bool(int(rs.GetUserText(oid, "RF_Layout"))), panel_id=panel_id, panel=panel,
                click=click, had_seam=any(rs.GetUserText(i, Seams.KEY) for i in ids), ids=list(ids), up=up,
                normal=plane.ZAxis if ok else rs.ViewCPlane().ZAxis,
                attrs=sc.doc.Objects.FindId(rs.coerceguid(oid)).Attributes.Duplicate())
    return vals


HELP = u"""Options:
  W — strip width from the edge into the panel
  Plus — the strip is longer than the edge by this much, trimmed after sewing
  Seam — Yes: run the seam allowance step (Seams.py) on the strips afterwards; rebuilt strips lose the old cut line"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    sel = rs.GetObjects(u"Select Rinforzo strips (any part)", preselect=True)
    if not sel:
        return
    groups, strips = set(), []
    for o in sel:
        g = (rs.ObjectGroups(o) or [None])[0]
        if g is None or g in groups:
            continue
        groups.add(g)
        res = read_strip(rs.ObjectsByGroup(g), tol)  # one group: markup + full part
        if isinstance(res, dict):
            strips.append(res)
        else:
            print(u"Skipped: " + res)
    if not strips:
        return
    first = strips[0]
    print(u"Rinforzo now: W=%g Plus=%g" % tuple(first[k] for k in KEYS))
    go = Rhino.Input.Custom.GetOption()
    go.SetCommandPrompt(u"New parameters (Enter — apply to %d strips)" % len(strips))
    go.AcceptNothing(True)
    opts = dict((k, Rhino.Input.Custom.OptionDouble(first[k], 0.001 if k == "W" else 0.0, 1e6)) for k in KEYS)
    seam = Rhino.Input.Custom.OptionToggle(any(s["had_seam"] for s in strips), "No", "Yes")
    go.AddOptionToggle("Seam", seam)
    for k in KEYS:
        go.AddOptionDouble(k, opts[k])
    while True:
        r = go.Get()
        if r == Rhino.Input.GetResult.Option:
            continue
        if r != Rhino.Input.GetResult.Nothing:
            return
        break
    changed = dict((k, float(opts[k].CurrentValue)) for k in KEYS if float(opts[k].CurrentValue) != first[k])
    if not changed and not seam.CurrentValue:
        print(u"Nothing changed")
        return
    parts, steps = [], Steps(doc)
    saved_up = sc.sticky.get(RF.UP_KEY)
    for s in strips:
        if not changed:  # only Seams again, on the parts as they are
            parts.append(s["contour"])
            continue
        s.update(changed)
        s["attrs"].RemoveFromAllGroups()
        for key in list(s["attrs"].GetUserStrings().AllKeys):  # the old data (RF_*, PartLink…) must not go to every new object
            s["attrs"].DeleteUserString(key)
        sc.sticky[RF.UP_KEY] = s["up"].Length  # the full part goes up as far as before (add_part uses CPlane Y)
        rs.DeleteObjects(s["ids"])
        steps.start()
        got = RF.make(doc, s["panel_id"], s["panel"], s["click"], s["W"], s["Plus"], s["Angle"], s["layout"],
                      s["normal"], tol, s["attrs"], steps)
        if got is None:
            continue
        print(u"Updated: " + got[1])
        if seam.CurrentValue:
            parts.append(got[0][0])
        elif s["had_seam"]:
            print(u"%s: the old seam cut line is gone (Seam=No)" % got[1])
    if saved_up is not None:
        sc.sticky[RF.UP_KEY] = saved_up
    if changed:
        print(u"Changed: " + ", ".join(u"%s=%g" % kv for kv in sorted(changed.items())))
    if parts:  # second step: seam allowance
        rs.ZoomBoundingBox(rs.BoundingBox(parts))
        Seams.main(parts)


if __name__ == "__main__":
    main()
