# -*- coding: utf-8 -*-
"""Update existing TubePockets pockets with new parameters (H / Trim / Notch / Rigid).
Select any part of a pocket (or several with a window) — the pocket is rebuilt from its edge
in place, with the same number T<n>, layer and side. Only the parameters you changed in the options
change; the rest stay each pocket's own. Parameters are read from UserText (TP_H…, edge — TP_Seg on the contour).
Pocket = markup on the panel + full part above (TP_Up): you can select either, both are rebuilt.
Option Seam: Yes — after the update the view zooms to the parts and pattern/Seams.py runs on them (the same second step as
in TubePockets). Default Yes if a selected pocket had a seam cut line. A rebuilt pocket loses its old cut line (it is in
the pocket's group), so with Seam=No the allowance is dropped (a warning is printed). Seam=Yes with no other change —
nothing is rebuilt, Seams just runs on the existing parts (their cut lines are edited, not lost).
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("TubePockets", None)
import TubePockets as TP
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pattern"))
sys.modules.pop("Seams", None)
import Seams

KEYS = ("H", "Trim", "Notch", "Rigid")
TOGGLES = ("Notch", "Rigid")


def is_markup(o):
    """Markup on the panel, not the full part (PartMarkup; TP_Markup — pockets made before the common format)."""
    return bool(rs.GetUserText(o, "PartMarkup") or rs.GetUserText(o, "TP_Markup"))


def tagged(near, n, markup):
    """Objects in layer near (and its Parts / Labels twin) with UserText TP_N == n: markup or the full part."""
    return [o for o in TP.by_layer(rs.ObjectLayer(near)) if rs.GetUserText(o, "TP_N") == n and is_markup(o) == markup]


def read_pocket(ids, tol):
    """dict with the pocket's parameters (UserText TP_*) and geometry from group ids, or a reason string."""
    ids = [i for i in ids if not is_markup(i)]  # one group: markup + full part
    outline_ids = [i for i in ids if rs.IsCurve(i) and rs.GetUserText(i, "TP_Seg")]
    texts = [i for i in ids if rs.IsText(i)]
    if len(outline_ids) != 1 or not texts:
        return u"not a TubePockets pocket (no TP_Seg contour or T<n> label)"
    oid = outline_ids[0]
    seg = Rhino.Runtime.CommonObject.FromJSON(rs.GetUserText(oid, "TP_Seg"))  # the edge, stored on the contour
    ok, plane = rs.coercecurve(oid).TryGetPlane(tol)
    vals = dict((k, float(rs.GetUserText(oid, "TP_" + k) or 0)) for k in KEYS)
    up = rs.GetUserText(oid, "LayoutUp") or rs.GetUserText(oid, "TP_Up")  # TP_Up — before the common format
    vals["up"] = Rhino.Geometry.Vector3d(*[float(x) for x in up.split(",")]) if up else None
    vals["markup"] = tagged(oid, rs.GetUserText(oid, "TP_N"), True) if up else []
    vals.update(part=oid, name=u"T%s" % rs.GetUserText(oid, "TP_N"), had_seam=any(rs.GetUserText(i, Seams.KEY) for i in ids),
                n=int(rs.GetUserText(oid, "TP_N")), seg=seg, toward=rs.coercegeometry(texts[0]).Plane.Origin,  # label inside the pocket
                normal=plane.ZAxis if ok else rs.ViewCPlane().ZAxis, ids=ids,
                attrs=sc.doc.Objects.FindId(rs.coerceguid(oid)).Attributes.Duplicate())  # contour layer
    return vals


def rebuild(p, doc, tol):
    """The pocket again with its new parameters. (label, full contour id) or None (skipped, printed)."""
    h, trim, notch, rigid = p["H"], p["Trim"], bool(p["Notch"]), bool(p["Rigid"])
    seg, toward, up = p["seg"], p["toward"], p["up"]
    if up is not None:  # build in place of the markup, the full part goes to up again
        seg = seg.DuplicateCurve()
        seg.Translate(-up)
        toward = toward - up
    res = TP.pocket(seg, toward, 0, h, trim, notch, p["normal"], tol, rigid)
    if not isinstance(res, tuple):
        print(u"%s skipped: %s" % (p["name"], res))
        return None
    p["attrs"].RemoveFromAllGroups()
    for key in list(p["attrs"].GetUserStrings().AllKeys):  # the old data (TP_*, PartLink…) is written again
        p["attrs"].DeleteUserString(key)
    rs.DeleteObjects(list(p["ids"]) + p["markup"])
    return TP.add_pocket(doc, res + (toward,), h, trim, notch, p["n"], p["attrs"], p["normal"], tol, rigid, up)


def update(what, read, rebuild, keys, toggles=(), lowest=None):
    """The steps of an Update script (also parts/UpdateRinforzo.py): select parts (any object of each) → read(group
    ids, tol) → their parameters as options (keys; toggles — Yes / No ones; lowest — {key: smallest value}) + Seam →
    rebuild(item, doc, tol) for each when something changed → Seams.py on the parts when Seam = Yes.
    An item is a dict: the keys, "name", "part" (full contour id), "had_seam"."""
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    sel = rs.GetObjects(u"Select %s (any part)" % what, preselect=True)
    if not sel:
        return
    groups, items = set(), []
    for o in sel:
        g = (rs.ObjectGroups(o) or [None])[0]
        if g is None or g in groups:
            continue
        groups.add(g)
        res = read(rs.ObjectsByGroup(g), tol)  # one group: markup + full part
        if isinstance(res, dict):
            items.append(res)
        else:
            print(u"Skipped: " + res)
    if not items:
        return
    first = items[0]
    print(u"%s now: %s" % (first["name"], u" ".join(u"%s=%g" % (k, first[k]) for k in keys)))
    C = Rhino.Input.Custom
    go = C.GetOption()
    go.SetCommandPrompt(u"New parameters (Enter — apply to %d %s)" % (len(items), what))
    go.AcceptNothing(True)
    seam = C.OptionToggle(any(p["had_seam"] for p in items), "No", "Yes")
    go.AddOptionToggle("Seam", seam)
    opts = {}
    for k in keys:
        if k in toggles:
            opts[k] = C.OptionToggle(bool(first[k]), "No", "Yes")
            go.AddOptionToggle(k, opts[k])
        else:
            opts[k] = C.OptionDouble(first[k], (lowest or {}).get(k, 0.0), 1e6)
            go.AddOptionDouble(k, opts[k])
    while True:
        r = go.Get()
        if r == Rhino.Input.GetResult.Option:
            continue
        if r != Rhino.Input.GetResult.Nothing:
            return
        break
    changed = dict((k, float(opts[k].CurrentValue)) for k in keys if float(opts[k].CurrentValue) != first[k])
    if not changed and not seam.CurrentValue:
        print(u"Nothing changed")
        return
    parts = []
    for p in items:
        if not changed:  # only Seams again, on the parts as they are
            parts.append(p["part"])
            continue
        p.update(changed)
        got = rebuild(p, doc, tol)
        if got is None:
            continue
        label, part = got
        print(u"Updated: " + label)
        if seam.CurrentValue:
            parts.append(part)
        elif p["had_seam"]:
            print(u"%s: the old seam cut line is gone (Seam=No)" % label)
    if changed:
        print(u"Changed: " + ", ".join(u"%s=%g" % kv for kv in sorted(changed.items())))
    if parts:  # second step: seam allowance
        Seams.main(parts)


HELP = u"""Options:
  H — pocket height from the edge into the panel
  Trim — how much shorter the pocket top is at each end
  Notch — pocket centre mark (a tick from the edge into the pocket)
  Rigid — Yes: top is a copy of the edge without changing its shape; No: regular offset
  Seam — Yes: run the seam allowance step (Seams.py) on the pockets afterwards; rebuilt pockets lose the old cut line"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    update(u"pockets", read_pocket, rebuild, KEYS, TOGGLES)


if __name__ == "__main__":
    main()
