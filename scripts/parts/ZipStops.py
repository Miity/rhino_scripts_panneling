# -*- coding: utf-8 -*-
"""Marks zips and tracks (keder track / guide rail).
One zip = all its lines on all panels (both sides of the tape, a side may be split over several panels).
A track is one side, it may also be split over several panels. The kind is the Type option while picking lines
(Zip / Track, remembered): zips Z1, Z2… in layer Parts::Zip, tracks Trk1, Trk2… in Parts::Track.
Line picking repeats — Enter finishes.
Each line moves to its layer and gets a number: UserText Zip + text above the midpoint,
along the line; text style — option Style (remembered, default PAT 10 mm).
At the ends of each line — cross stops (centred, in the CPlane). If a side is split
(zip — 3+ lines, track — 2+), a click near a junction end (where it continues on another panel)
changes the stop to a tick half as long; another click — back.
The line, its stops and text are one group (one per line: lines lie on different panels).
Numbering continues from the largest number in the layer (Z and Trk separately); already marked lines are skipped.
Then the flip step: clicking a zip moves its number to the other side of the curve (above ↔ below)
if it overlaps other text; Enter — done. Enter while picking curves — straight to flipping.
Length table for ordering — parts/ZipList.py."""
import os
import re
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.DocObjects import TextHorizontalAlignment, TextVerticalAlignment
from Rhino.Geometry import Plane, Vector3d

# style picking and PAT styles — from scripts/markup/DotToPanelText.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
import DotToPanelText as D

# type → (prefix, layer, in the prompt, from how many lines to ask about junctions)
TYPES = {"Zip": ("Z", "Parts::Zip", u"of the zip (both sides)", 3),
         "Track": ("Trk", "Parts::Track", u"of the track", 2)}
KEY = "Zip"  # UserText key with the number (Z<n> or Trk<n>)
STYLE = "ZipStops.style"
KIND = "ZipStops.kind"


def stop_lines(crv, size, normal):
    lines = []
    for t in (crv.Domain.T0, crv.Domain.T1):
        pt = crv.PointAt(t)
        side = Vector3d.CrossProduct(crv.TangentAt(t), normal)
        side.Unitize()
        side *= size / 2.0
        lines.append(Rhino.Geometry.Line(pt - side, pt + side))
    return lines


def label_plane(crv, normal, gap):
    """Text plane: above the curve midpoint by gap, X axis along the curve (reads left to right)."""
    ok, t = crv.LengthParameter(crv.GetLength() / 2.0)
    t = t if ok else crv.Domain.Mid
    u = crv.TangentAt(t)
    if u.X < -1e-9 or (abs(u.X) < 1e-9 and u.Y < 0):
        u = -u
    v = Vector3d.CrossProduct(normal, u)
    return Plane(crv.PointAt(t) + v * gap, u, v)


def is_zip(rhino_object, geometry, component_index):
    return bool(rhino_object.Attributes.GetUserString(KEY))


def flip_label(doc, oid):
    """Zip number to the other side of the curve: mirror about the curve, alignment Bottom ↔ Top."""
    name = rs.GetUserText(oid, KEY)
    crv = rs.coercecurve(oid)
    for g in rs.ObjectGroups(oid) or []:
        for t in rs.ObjectsByGroup(g) or []:
            if rs.IsText(t) and rs.TextObjectText(t) == name:
                te = rs.coercegeometry(t)
                mid = label_plane(crv, te.Plane.ZAxis, 0)
                y = mid.YAxis * ((te.Plane.Origin - mid.Origin) * mid.YAxis)
                pl = te.Plane
                pl.Origin = mid.Origin - y
                te.Plane = pl
                te.TextVerticalAlignment = (TextVerticalAlignment.Top if y * mid.YAxis > 0
                                            else TextVerticalAlignment.Bottom)
                doc.Objects.Replace(t, te)
                return True
    return False


def flip_stage(doc):
    while True:
        oid = rs.GetObject(u"Click a zip to move its number to the other side (Enter — done)",
                           rs.filter.curve, custom_filter=is_zip)
        if not oid:
            return
        if not flip_label(doc, oid):
            print(u"%s: number text not found in the curve's group" % rs.GetUserText(oid, KEY))
        doc.Views.Redraw()


def next_number(kind):
    """Next number after the largest <prefix><n> in the type's layer (curve UserText, text or TextDot of old marks)."""
    prefix, layer = TYPES[kind][:2]
    nums = [0]
    for o in (rs.ObjectsByLayer(layer) or []) if rs.IsLayer(layer) else []:
        s = rs.GetUserText(o, KEY) or (rs.TextObjectText(o) if rs.IsText(o) else
                                       rs.TextDotText(o) if rs.IsTextDot(o) else "")
        m = re.match(prefix + r"(\d+)$", s or "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


def get_lines(kind, nums, last):
    """Picking the lines of one zip / track with the Type option. Returns (id or None, type)."""
    go = Rhino.Input.Custom.GetObject()
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Curve
    go.EnablePreSelect(not nums, True)  # preselection — only for the first one
    while True:
        prefix, _, what, _ = TYPES[kind]
        n = nums.get(kind) or next_number(kind)
        go.SetCommandPrompt(u"%s%d: select all lines %s (Enter — %s)" % (prefix, n, what, last))
        go.ClearCommandOptions()
        go.AddOption("Type", kind)
        res = go.GetMultiple(1, 0)
        if res == Rhino.Input.GetResult.Option:
            kind = "Track" if kind == "Zip" else "Zip"
            sc.sticky[KIND] = kind
            go.EnablePreSelect(False, True)
            continue
        if res == Rhino.Input.GetResult.Object:
            return [go.Object(k).ObjectId for k in range(go.ObjectCount)], kind
        return None, kind


def ask_size(doc, size, style):
    """Stop length with the Style option. Returns (length or None, style)."""
    while True:
        gn = Rhino.Input.Custom.GetNumber()
        gn.SetCommandPrompt(u"Stop length (text style: %s)" % style)
        gn.SetDefaultNumber(size)
        gn.SetLowerLimit(0.0, True)
        opt = gn.AddOption("Style")
        res = gn.Get()
        if res == Rhino.Input.GetResult.Option and gn.OptionIndex() == opt:
            style = D.pick_style(doc, style)
            continue
        if res == Rhino.Input.GetResult.Number:
            return gn.Number(), style
        return None, style


def mark_line(doc, oid, crv, name, size, normal, ds, gap, attrs):
    """Line → layer attrs with a number, stops at the ends, text; one group. Returns stop ids [start, end]."""
    # ModifyAttributes, not rs.ObjectLayer + rs.SetUserText: this way Undo reverts the layer and the tag
    a = rs.coercerhinoobject(oid).Attributes.Duplicate()
    a.LayerIndex = attrs.LayerIndex
    a.SetUserString(KEY, name)
    doc.Objects.ModifyAttributes(oid, a, True)
    stops = [doc.Objects.AddLine(ln, attrs) for ln in stop_lines(crv, size, normal)]
    te = Rhino.Geometry.TextEntity.Create(name, label_plane(crv, normal, gap), ds, False, 0, 0)
    te.TextHorizontalAlignment = TextHorizontalAlignment.Center
    te.TextVerticalAlignment = TextVerticalAlignment.Bottom
    rs.AddObjectsToGroup([oid] + stops + [doc.Objects.AddText(te, attrs)], rs.AddGroup())
    return stops


def junction_stage(doc, name, lines, size, normal):
    """lines = [(curve, [stop id at start, at end])]. Click near an end: stop ↔ junction tick."""
    notch = set()
    while True:
        pt = rs.GetPoint(u"%s: click near a junction — the end where it continues on another panel (Enter — done)" % name)
        if pt is None:
            return
        d, i, e = min((pt.DistanceTo(c.PointAt((c.Domain.T0, c.Domain.T1)[e])), i, e)
                      for i, (c, _) in enumerate(lines) for e in (0, 1))
        crv, stops = lines[i]
        notch ^= set([(i, e)])
        ln = stop_lines(crv, size / 2.0 if (i, e) in notch else size, normal)[e]
        doc.Objects.Replace(stops[e], ln)
        doc.Views.Redraw()


HELP = u"""Options:
  Type — Zip: zip (both sides, Z<n>); Track: track (one side, Trk<n>)
  Style — number text style"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    nums = {}  # type → next number in this run
    kind = sc.sticky.get(KIND, "Zip") if sc.sticky.get(KIND) in TYPES else "Zip"  # old sessions may remember "Can"
    ids, kind = get_lines(kind, nums, u"only flip numbers")
    if not ids:
        flip_stage(doc)
        return
    D.pts.ensure_styles(doc)
    style = sc.sticky.get(STYLE)
    if not style or doc.DimStyles.FindName(style) is None:
        style = D.pts.style_name(10)
    # 1 cm in document units
    cm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Centimeters, doc.ModelUnitSystem)
    size, style = ask_size(doc, sc.sticky.get("zip_stop_size", cm), style)
    sc.sticky[STYLE] = style
    if not size:
        return
    sc.sticky["zip_stop_size"] = size
    ds = doc.DimStyles.FindName(style)
    gap = 0.5 * ds.TextHeight * ds.DimensionScale
    normal = rs.ViewCPlane().ZAxis
    layers = [t[1] for t in TYPES.values()]

    while ids:
        prefix, layer, _, junctions = TYPES[kind]
        todo = [i for i in ids if not rs.IsCurveClosed(i)  # a closed curve has no ends
                and not (rs.GetUserText(i, KEY) and rs.ObjectLayer(i) in layers)]  # already marked
        if len(todo) < len(ids):
            print(u"Closed or already marked, skipped: %d" % (len(ids) - len(todo)))
        if todo:
            if not rs.IsLayer("Parts"):
                rs.AddLayer("Parts")
            if not rs.IsLayer(layer):
                rs.AddLayer(layer.split("::")[1], parent="Parts")
            attrs = doc.CreateDefaultAttributes()
            attrs.LayerIndex = doc.Layers.FindByFullPath(layer, -1)
            n = nums.get(kind) or next_number(kind)
            nums[kind] = n + 1
            name = prefix + str(n)
            lines = []
            for oid in todo:
                crv = rs.coercecurve(oid)
                lines.append((crv, mark_line(doc, oid, crv, name, size, normal, ds, gap, attrs)))
            rs.UnselectAllObjects()
            doc.Views.Redraw()
            if len(lines) >= junctions:  # side split over several panels
                junction_stage(doc, name, lines, size, normal)
            print(u"%s: lines %d" % (name, len(lines)))
        rs.UnselectAllObjects()
        ids, kind = get_lines(kind, nums, u"done")
    flip_stage(doc)


if __name__ == "__main__":
    main()
