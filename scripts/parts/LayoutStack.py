# -*- coding: utf-8 -*-
"""Strips on the canvas, turned along the grain: before nesting with a fixed fabric direction.
Select objects (a window over the panels / parts up is fine), then at the click options Rinforzo (R<w> parts in
Parts::Reinforcements; RC / RD / RO are not strips) and Bordini (Parts::Bordino) = Yes / No — what to stack, remembered.
Only those parts are taken (the copy up; the markup on the panel is skipped). Each one is copied as LayoutParts does
(contour + label code "B3.5 P4", sublayer <layer>::Layout, UserText LayoutOf), turned so it lies flattest along
CPlane X (label reading left to right), and stacked one under another from the click point (top-left corner),
Gap apart (0 — touching, as the fascia strips): Rinforzo first, then Bordini, longest first in each.
Already laid out parts (a copy with LayoutOf exists) are skipped; to lay out again — delete the copy.
Layout then skips them too. Option Hide=Yes — the parts laid out now and the ones of the selection laid out before are
hidden (only the part itself, the copy up; the markup on the panel stays); Show brings them back. Enter instead of
the click — nothing stacked, only Hide.
"""
import math
import os
import re
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Plane, TextEntity, Transform, Vector3d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("LayoutParts", None)  # Rhino keeps modules from the first run for the session
from LayoutParts import KEY, is_part, outer, own, parts, place

STICKY = "LayoutStack"
KINDS = [  # (option, layer, label code) — parts that may be turned along the grain
    (u"Rinforzo", "Parts::Reinforcements", re.compile(r"(?:^|\s)R\d")),
    (u"Bordini", "Parts::Bordino", re.compile(r"(?:^|\s)B\d")),
]


def kind_of(doc, u, kinds):
    """Index in kinds of the part u (objects), or None."""
    text = u" ".join(o.Geometry.PlainText for o in u if isinstance(o.Geometry, TextEntity))
    lays = set(doc.Layers[o.Attributes.LayerIndex].FullPath for o in u)
    return next((i for i, (_, lay, code) in enumerate(kinds) if lay in lays and code.search(text)), None)


def pick(doc, ids, kinds):
    """Parts of kinds in the selection: (not laid out yet, already laid out), each [(kind index, [objects])]."""
    copied = set(o.Attributes.GetUserString(KEY) for o in doc.Objects)
    found = []
    for p in parts(ids):
        u = [doc.Objects.FindId(i) for i in p]
        k = kind_of(doc, u, kinds) if is_part(doc, u) else None
        if k is not None:
            found.append((k, u))
    done = [(k, u) for k, u in found if any(str(o.Id) in copied for o in u)]
    return [p for p in found if p not in done], done


def turn(u, plane):
    """Rotation about plane Z laying the part u flattest along plane X (lowest bbox over its segment directions),
    turned over if its label would read right to left."""
    c = outer(u)
    to_plane = Transform.PlaneToPlane(plane, Plane.WorldXY)  # bbox in CPlane coordinates
    best = (float("inf"), Transform.Identity)
    for s in c.DuplicateSegments() or []:
        d = s.PointAtEnd - s.PointAtStart
        if d.IsTiny():
            continue
        rot = Transform.Rotation(-math.atan2(d * plane.YAxis, d * plane.XAxis), plane.ZAxis, plane.Origin)
        bb = c.GetBoundingBox(to_plane * rot)
        best = min(best, (bb.Max.Y - bb.Min.Y, rot), key=lambda b: b[0])
    rot = best[1]
    for o in u:
        if isinstance(o.Geometry, TextEntity):
            x = Vector3d(o.Geometry.Plane.XAxis)
            x.Transform(rot)
            if x * plane.XAxis < 0:
                rot = Transform.Rotation(math.pi, plane.ZAxis, plane.Origin) * rot
            break
    return rot


def stack(doc, todo, plane, start, gap):
    """Copies of the parts turned along plane X, stacked down from start (top-left corner) gap apart,
    by kind, longest first. Returns the copy ids."""
    ok, x, y = plane.ClosestParameter(start)
    to_plane = Transform.PlaneToPlane(plane, Plane.WorldXY)
    rows = []
    for k, u in todo:
        rot = turn(u, plane)
        bb = outer(u).GetBoundingBox(to_plane * rot)
        rows.append((k, bb.Min.X - bb.Max.X, bb, rot, u))
    rows.sort(key=lambda r: r[:2])
    new = []
    for k, _, bb, rot, u in rows:
        xf = Transform.Translation(plane.XAxis * (x - bb.Min.X) + plane.YAxis * (y - bb.Max.Y)) * rot
        geo = own(doc, u)
        for _, g in geo:
            g.Transform(xf)
        new += place(doc, geo)
        y -= bb.Max.Y - bb.Min.Y + gap
    return new


HELP = u"""Options:
  Rinforzo — stack the R<w> strips (Parts::Reinforcements; RC / RD / RO are not taken)
  Bordini — stack the bordini (Parts::Bordino; Pettola is not taken)
  Gap — space between the stacked parts (0 — touching)
  Hide — hide the laid out parts of the selection (now and before; the copy up only), Show brings them back
  Enter instead of a click — nothing stacked, only Hide"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select objects with the parts (window over the panels / parts up)", preselect=True)
    if not ids:
        return
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Point to stack from (top-left corner; Enter — only Hide)")
    gp.AcceptNothing(True)
    ticks = [(n, Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + n, n != "Hide"), "No", "Yes"))
             for n in [k[0] for k in KINDS] + ["Hide"]]
    gap = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_gap", 0.0), 0.0, 1e6)
    for n, t in ticks[:-1]:
        gp.AddOptionToggle(n, t)
    gp.AddOptionDouble("Gap", gap)
    gp.AddOptionToggle(*ticks[-1])
    while gp.Get() == Rhino.Input.GetResult.Option:
        pass
    on = {}
    for n, t in ticks:
        sc.sticky[STICKY + n] = on[n] = t.CurrentValue
    sc.sticky[STICKY + "_gap"] = gap.CurrentValue
    if gp.CommandResult() != Rhino.Commands.Result.Success:
        return
    kinds = [k for k in KINDS if on[k[0]]]
    todo, done = pick(doc, ids, kinds)
    if gp.Result() == Rhino.Input.GetResult.Point:
        stack(doc, todo, rs.ViewCPlane(), gp.Point(), gap.CurrentValue)
    else:
        todo = []  # Enter: nothing laid out now
    hidden = rs.HideObjects([o.Id for _, u in todo + done for o in u]) if on["Hide"] else 0
    doc.Views.Redraw()
    print(u"Stacked: %s; already laid out: %d; hidden: %d objects" % (
        u", ".join(u"%s %d" % (k[0], sum(1 for i, _ in todo if i == j)) for j, k in enumerate(kinds)), len(done),
        hidden or 0))


if __name__ == "__main__":
    main()
