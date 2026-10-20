# -*- coding: utf-8 -*-
"""Update existing TubePockets pockets with new parameters (H / Trim / Hem / Notch / Rigid).
Select any part of a pocket (or several with a window) — the pocket is rebuilt from its edge
in place, with the same number T<n>, layer and side. Only the parameters you changed in the options
change; the rest stay each pocket's own. Parameters are read from UserText (TP_H…, edge — TP_Seg on the contour).
Pocket = markup on the panel + full part above (TP_Up): you can select either, both are rebuilt.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("TubePockets", None)
import TubePockets as TP

KEYS = ("H", "Trim", "Hem", "Notch", "Rigid")
TOGGLES = ("Notch", "Rigid")


def tagged(near, n, markup):
    """Objects in layer near (and its Parts / Labels twin) with UserText TP_N == n: markup or the full part."""
    return [o for o in TP.by_layer(rs.ObjectLayer(near))
            if rs.GetUserText(o, "TP_N") == n and bool(rs.GetUserText(o, "TP_Markup")) == markup]


def read_pocket(ids, tol):
    """dict with the pocket's parameters (UserText TP_*) and geometry from group ids, or a reason string."""
    outline_ids = [i for i in ids if rs.IsCurve(i) and rs.GetUserText(i, "TP_Seg")]
    texts = [i for i in ids if rs.IsText(i)]
    if len(outline_ids) != 1 or not texts:
        return u"not a TubePockets pocket (no TP_Seg contour or T<n> label)"
    oid = outline_ids[0]
    seg = Rhino.Runtime.CommonObject.FromJSON(rs.GetUserText(oid, "TP_Seg"))  # the edge, stored on the contour
    ok, plane = rs.coercecurve(oid).TryGetPlane(tol)
    vals = dict((k, float(rs.GetUserText(oid, "TP_" + k) or 0)) for k in KEYS)
    up = rs.GetUserText(oid, "TP_Up")
    vals["up"] = Rhino.Geometry.Vector3d(*[float(x) for x in up.split(",")]) if up else None
    vals["markup"] = tagged(oid, rs.GetUserText(oid, "TP_N"), True) if up else []
    vals.update(n=int(rs.GetUserText(oid, "TP_N")), seg=seg, toward=rs.coercegeometry(texts[0]).Plane.Origin,  # label inside the pocket
                normal=plane.ZAxis if ok else rs.ViewCPlane().ZAxis, ids=ids,
                attrs=sc.doc.Objects.FindId(rs.coerceguid(oid)).Attributes.Duplicate())  # contour layer, not Fold
    return vals


HELP = u"""Options:
  H — pocket height from the edge into the panel
  Trim — how much shorter the pocket top is at each end
  Hem — hem allowance at the ends, on each side (0 — none)
  Notch — pocket centre mark (a tick from the edge into the pocket)
  Rigid — Yes: top is a copy of the edge without changing its shape; No: regular offset"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    sel = rs.GetObjects(u"Select TP pockets (any part)", preselect=True)
    if not sel:
        return
    groups, pockets = set(), []
    for o in sel:
        g = (rs.ObjectGroups(o) or [None])[0]
        if g is None or g in groups:
            continue
        groups.add(g)
        ids = [i for i in rs.ObjectsByGroup(g) if not rs.GetUserText(i, "TP_Markup")]  # one group: markup + full part
        res = read_pocket(ids, tol)
        if isinstance(res, dict):
            pockets.append(res)
        else:
            print(u"Skipped: " + res)
    if not pockets:
        return
    first = pockets[0]
    print(u"TP%d now: H=%g Trim=%g Hem=%g Notch=%d Rigid=%d" % ((first["n"],) + tuple(first[k] for k in KEYS)))
    go = Rhino.Input.Custom.GetOption()
    go.SetCommandPrompt(u"New parameters (Enter — apply to %d pockets)" % len(pockets))
    go.AcceptNothing(True)
    opts = dict((k, Rhino.Input.Custom.OptionDouble(first[k], 0.0, 1e6)) for k in ("H", "Trim", "Hem"))
    for k in TOGGLES:
        opts[k] = Rhino.Input.Custom.OptionToggle(bool(first[k]), "No", "Yes")
    for k in KEYS:
        (go.AddOptionToggle if k in TOGGLES else go.AddOptionDouble)(k, opts[k])
    while True:
        r = go.Get()
        if r == Rhino.Input.GetResult.Option:
            continue
        if r != Rhino.Input.GetResult.Nothing:
            return
        break
    changed = dict((k, float(opts[k].CurrentValue)) for k in KEYS if float(opts[k].CurrentValue) != first[k])
    if not changed:
        print(u"Nothing changed")
        return
    for p in pockets:
        p.update(changed)
        h, trim, notch, rigid = p["H"], p["Trim"], bool(p["Notch"]), bool(p["Rigid"])
        hem = p["Hem"]
        seg, toward, up = p["seg"], p["toward"], p["up"]
        if up is not None:  # build in place of the markup, the full part goes to up again
            seg = seg.DuplicateCurve()
            seg.Translate(-up)
            toward = toward - up
        res = TP.pocket(seg, toward, 0, h, trim, notch, p["normal"], tol, rigid, hem)
        if not isinstance(res, tuple):
            print(u"TP%d skipped: %s" % (p["n"], res))
            continue
        p["attrs"].RemoveFromAllGroups()
        rs.DeleteObjects(list(p["ids"]) + p["markup"])
        print(u"Updated: " + TP.add_pocket(doc, res + (toward,), h, trim, notch, p["n"], p["attrs"], p["normal"],
                                           tol, rigid, hem, up))
    print(u"Changed: " + ", ".join(u"%s=%g" % kv for kv in sorted(changed.items())))


if __name__ == "__main__":
    main()
