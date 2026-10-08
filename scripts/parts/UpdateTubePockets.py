# -*- coding: utf-8 -*-
"""Update existing TubePockets pockets with new parameters (H / Trim / SA / Hem / Notch / Rigid).
Select any part of a pocket (or several with a window) — the pocket is rebuilt from its seam line
in place, with the same number T<n>, layer and side. Only the parameters you changed in the options
change; the rest stay each pocket's own. Parameters are read from UserText (TP_H…); in old pockets
without UserText — from the geometry (h from the label, in cm; SA and Trim — from the contour).
Pocket = markup on the panel + full part above (TP_Up): you can select either, both are rebuilt.
"""
import os
import re
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("TubePockets", None)
import TubePockets as TP

KEYS = ("H", "Trim", "SA", "Hem", "Notch", "Rigid")
TOGGLES = ("Notch", "Rigid")


def tagged(near, n, markup):
    """Objects in layer near with UserText TP_N == n: markup or the full part."""
    return [o for o in rs.ObjectsByLayer(rs.ObjectLayer(near)) or []
            if rs.GetUserText(o, "TP_N") == n and bool(rs.GetUserText(o, "TP_Markup")) == markup]


def read_pocket(ids, tol):
    """dict with the pocket's parameters and geometry from group ids, or a reason string."""
    curves = [(i, rs.coercecurve(i)) for i in ids if rs.IsCurve(i)]
    texts = [i for i in ids if rs.IsText(i)]
    m = re.match(TP.PREFIX + r"(\d+)\s+h=([\d.]+)", rs.TextObjectText(texts[0]) if texts else "")
    outline_ids = [i for i, c in curves if c.IsClosed]
    outline = [c for i, c in curves if c.IsClosed]
    opened = sorted([c for i, c in curves if not c.IsClosed], key=lambda c: -c.GetLength())
    if not m or len(outline) != 1:
        return u"does not look like a pocket (no T<n> label or contour)"
    if not opened:
        # ponytail: a pocket with SA=0 has no separate seam line — rebuilding from the contour is not done.
        return u"no seam line (SA=0) — rebuild with TubePockets"
    seg, outline = opened[0], outline[0]
    ok, plane = outline.TryGetPlane(tol)
    normal = plane.ZAxis if ok else rs.ViewCPlane().ZAxis
    toward = rs.coercegeometry(texts[0]).Plane.Origin  # the label sits inside the pocket
    side = lambda p: Rhino.Geometry.Vector3d.Multiply(
        Rhino.Geometry.Vector3d.CrossProduct(seg.TangentAt(seg.ClosestPoint(p)[1]), p - seg.PointAt(seg.ClosestPoint(p)[1])), normal)
    s_in = side(toward)
    pts = [c.PointAtStart for c in outline.DuplicateSegments()]
    sa = max([abs(side(p)) for p in pts if side(p) * s_in < -tol] or [0.0])
    h = float(rs.GetUserText(ids[0], "TP_H") or 0) or float(m.group(2)) * Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Centimeters, sc.doc.ModelUnitSystem)  # label h is rounded to 1 mm, in cm
    inner = [p for p in pts if side(p) * s_in > 0 and abs(abs(side(p)) - h) < 0.01 * h]
    trim = min([seg.GetLength(Rhino.Geometry.Interval(seg.Domain.Min, seg.ClosestPoint(p)[1])) for p in inner] or [0.0])
    vals = {"H": h, "Trim": trim, "SA": sa, "Notch": float(len(opened) > 1), "Rigid": 0.0, "Hem": 0.0}
    for k in KEYS:
        v = rs.GetUserText(ids[0], "TP_" + k)
        if v:
            vals[k] = float(v)
    up = rs.GetUserText(outline_ids[0], "TP_Up")
    vals["up"] = Rhino.Geometry.Vector3d(*[float(x) for x in up.split(",")]) if up else None
    vals["markup"] = tagged(outline_ids[0], rs.GetUserText(outline_ids[0], "TP_N"), True) if up else []
    vals.update(n=int(m.group(1)), seg=seg, toward=toward, normal=normal, ids=ids,
                attrs=sc.doc.Objects.FindId(rs.coerceguid(outline_ids[0])).Attributes.Duplicate())  # contour layer, not Fold
    return vals


HELP = u"""Options:
  H — pocket height from the edge into the panel
  Trim — how much shorter the pocket top is at each end
  SA — seam allowance from the edge outward from the panel
  Hem — hem allowance at the ends, on each side (0 — none)
  Notch — pocket centre mark (a tick across the seam line)
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
        ids = rs.ObjectsByGroup(g)
        if rs.GetUserText(ids[0], "TP_Markup"):  # markup on the panel selected → full part above
            full = tagged(ids[0], rs.GetUserText(ids[0], "TP_N"), False)
            g = full and (rs.ObjectGroups(full[0]) or [None])[0]
            if not g:
                print(u"Skipped: no full part for markup TP%s" % rs.GetUserText(ids[0], "TP_N"))
                continue
            if g in groups:
                continue
            groups.add(g)
            ids = rs.ObjectsByGroup(g)
        res = read_pocket(ids, tol)
        if isinstance(res, dict):
            pockets.append(res)
        else:
            print(u"Skipped: " + res)
    if not pockets:
        return
    first = pockets[0]
    print(u"TP%d now: H=%g Trim=%g SA=%g Hem=%g Notch=%d Rigid=%d" % ((first["n"],) + tuple(first[k] for k in KEYS)))
    go = Rhino.Input.Custom.GetOption()
    go.SetCommandPrompt(u"New parameters (Enter — apply to %d pockets)" % len(pockets))
    go.AcceptNothing(True)
    opts = dict((k, Rhino.Input.Custom.OptionDouble(first[k], 0.0, 1e6)) for k in ("H", "Trim", "SA", "Hem"))
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
        h, trim, sa, notch, rigid = p["H"], p["Trim"], p["SA"], bool(p["Notch"]), bool(p["Rigid"])
        hem = p["Hem"]
        seg, toward, up = p["seg"], p["toward"], p["up"]
        if up is not None:  # build in place of the markup, the full part goes to up again
            seg = seg.DuplicateCurve()
            seg.Translate(-up)
            toward = toward - up
        res = TP.pocket(seg, toward, 0, h, trim, sa, notch, p["normal"], tol, rigid, hem)
        if not isinstance(res, tuple):
            print(u"TP%d skipped: %s" % (p["n"], res))
            continue
        p["attrs"].RemoveFromAllGroups()
        rs.DeleteObjects(list(p["ids"]) + p["markup"])
        print(u"Updated: " + TP.add_pocket(doc, res + (toward,), h, trim, sa, notch, p["n"], p["attrs"], p["normal"],
                                           tol, rigid, hem, up))
    print(u"Changed: " + ", ".join(u"%s=%g" % kv for kv in sorted(changed.items())))


if __name__ == "__main__":
    main()
