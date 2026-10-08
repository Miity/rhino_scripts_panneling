# -*- coding: utf-8 -*-
"""Marks zips and tracks (keder track / guide rail) with stops and a number; the lines themselves are not touched.
One zip = all its lines on all panels (both sides of the tape, a side may be split over several panels).
A track is one side, it may also be split over several panels. The kind is the Type option while picking lines
(Zip / Track, remembered): zips Z1, Z2… in layer Parts::Zip, tracks (canalina) Can1, Can2… in Parts::Track.
Line picking repeats — Enter finishes.
For each line: cross stops (centred, in the CPlane) Trim in from its real ends — the zip is usually a bit
shorter than the line (option Trim, remembered per type: Zip 4 cm, Track 0) — and the number as text above
the middle between the stops; text style — option Style (remembered, default PAT 14 mm).
If a side is split (zip — 3+ lines, track — 2+), a click near a junction end (where it continues on another
panel) turns its stop into a tick half as long, right at the line end (no Trim there); another click — back.
Stops and text are one group per line, in the type's layer; the line stays in its own layer and group.
The data lives on the text (UserText): Zip = number, ZipLine = line id, ZipTrim = trim at start,end —
parts/ZipList.py computes the length from the line live. Lines that already have a number are skipped.
Numbering continues from the largest number in the layer (Z and Can separately).
Then the flip step: clicking a number moves it to the other side of the line (above ↔ below)
if it overlaps other text; Enter — done. Enter while picking lines — straight to flipping."""
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
for _m in ("DotToPanelText", "PatternTextStyles"):  # Rhino keeps modules from the first run for the session
    sys.modules.pop(_m, None)
import DotToPanelText as D

# type → (prefix, layer, in the prompt, from how many lines to ask about junctions, default Trim in cm)
TYPES = {"Zip": ("Z", "Parts::Zip", u"of the zip (both sides)", 3, 4.0),
         "Track": ("Can", "Parts::Track", u"of the track", 2, 0.0)}
KEY = "Zip"          # UserText on the text: number (Z<n> or Can<n>)
LINE = "ZipLine"     # UserText on the text: id of the marked line
TRIM = "ZipTrim"     # UserText on the text: "start,end" — stop distance from the line ends, document units
STYLE = "ZipStops"  # sticky key of the label style (PatternTextStyles.label_style)
KIND = "ZipStops.kind"


def point_at(crv, s):
    """Point and tangent at arc length s from the start."""
    ok, t = crv.LengthParameter(s)
    t = t if ok else (crv.Domain.T0 if s <= 0 else crv.Domain.T1)
    return crv.PointAt(t), crv.TangentAt(t)


def stop_line(crv, s, size, normal):
    """Cross line of length size, centred on the curve at arc length s."""
    pt, tan = point_at(crv, s)
    side = Vector3d.CrossProduct(tan, normal)
    side.Unitize()
    side *= size / 2.0
    return Rhino.Geometry.Line(pt - side, pt + side)


def label_plane(crv, trims, normal, gap):
    """Text plane: above the middle between the stops by gap, X axis along the curve (reads left to right)."""
    pt, u = point_at(crv, (trims[0] + crv.GetLength() - trims[1]) / 2.0)
    if u.X < -1e-9 or (abs(u.X) < 1e-9 and u.Y < 0):
        u = -u
    v = Vector3d.CrossProduct(normal, u)
    return Plane(pt + v * gap, u, v)


def read_trims(t):
    try:
        return [float(x) for x in rs.GetUserText(t, TRIM).split(",")]
    except Exception:
        return [0.0, 0.0]


def is_number(rhino_object, geometry, component_index):
    return bool(rhino_object.Attributes.GetUserString(KEY))


def marked_lines():
    """Ids (str) of lines that already have a number text."""
    out = set()
    for layer in [t[1] for t in TYPES.values()]:
        for o in (rs.ObjectsByLayer(layer) or []) if rs.IsLayer(layer) else []:
            if rs.IsText(o) and rs.GetUserText(o, LINE):
                out.add(rs.GetUserText(o, LINE))
    return out


def flip_label(doc, t):
    """Number to the other side of its line: mirror about the line, alignment Bottom ↔ Top."""
    crv = rs.coercecurve(rs.GetUserText(t, LINE) or "", -1, False)
    if crv is None:
        return False
    te = rs.coercegeometry(t)
    mid = label_plane(crv, read_trims(t), te.Plane.ZAxis, 0)
    y = mid.YAxis * ((te.Plane.Origin - mid.Origin) * mid.YAxis)
    pl = te.Plane
    pl.Origin = mid.Origin - y
    te.Plane = pl
    te.TextVerticalAlignment = TextVerticalAlignment.Top if y * mid.YAxis > 0 else TextVerticalAlignment.Bottom
    doc.Objects.Replace(t, te)
    return True


def flip_stage(doc):
    while True:
        t = rs.GetObject(u"Click a zip number to move it to the other side of the line (Enter — done)",
                         rs.filter.annotation, custom_filter=is_number)
        if not t:
            return
        if not flip_label(doc, t):
            print(u"%s: its line is gone (deleted?)" % rs.GetUserText(t, KEY))
        doc.Views.Redraw()


def next_number(kind):
    """Next number after the largest <prefix><n> in the type's layer (UserText, text or TextDot of old marks)."""
    prefix, layer = TYPES[kind][:2]
    nums = [0]
    for o in (rs.ObjectsByLayer(layer) or []) if rs.IsLayer(layer) else []:
        s = rs.GetUserText(o, KEY) or (rs.TextObjectText(o) if rs.IsText(o) else
                                       rs.TextDotText(o) if rs.IsTextDot(o) else "")
        m = re.match(prefix + r"(\d+)$", s or "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


def get_lines(kind, nums, last, cm):
    """Picking the lines of one zip / track with the Type and Trim options. Returns (ids or None, type, trim)."""
    go = Rhino.Input.Custom.GetObject()
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Curve
    go.EnablePreSelect(not nums, True)  # preselection — only for the first one
    while True:
        prefix, _, what, _, trim_cm = TYPES[kind]
        trim = Rhino.Input.Custom.OptionDouble(sc.sticky.get("ZipStops.trim." + kind, trim_cm * cm), 0.0, 1e6)
        n = nums.get(kind) or next_number(kind)
        go.SetCommandPrompt(u"%s%d: select all lines %s (Enter — %s)" % (prefix, n, what, last))
        go.ClearCommandOptions()
        opt_type = go.AddOption("Type", kind)
        go.AddOptionDouble("Trim", trim)
        res = go.GetMultiple(1, 0)
        if res == Rhino.Input.GetResult.Option:
            if go.OptionIndex() == opt_type:
                kind = "Track" if kind == "Zip" else "Zip"
                sc.sticky[KIND] = kind
            else:
                sc.sticky["ZipStops.trim." + kind] = trim.CurrentValue
            go.EnablePreSelect(False, True)
            continue
        if res == Rhino.Input.GetResult.Object:
            return [go.Object(k).ObjectId for k in range(go.ObjectCount)], kind, trim.CurrentValue
        return None, kind, trim.CurrentValue


def mark_line(doc, oid, crv, name, trim, size, normal, ds, gap, attrs):
    """Stops trim in from both ends + number text with the data; one group. The line is not touched.
    Returns [line id, curve, [stop id at start, at end], text id, trims]."""
    trims = [trim, trim]
    stops = [doc.Objects.AddLine(stop_line(crv, s, size, normal), attrs) for s in (trim, crv.GetLength() - trim)]
    te = Rhino.Geometry.TextEntity.Create(name, label_plane(crv, trims, normal, gap), ds, False, 0, 0)
    te.TextHorizontalAlignment = TextHorizontalAlignment.Center
    te.TextVerticalAlignment = TextVerticalAlignment.Bottom
    a = attrs.Duplicate()
    a.SetUserString(KEY, name)
    a.SetUserString(LINE, str(oid))
    a.SetUserString(TRIM, u"%r,%r" % tuple(trims))
    tid = doc.Objects.AddText(te, a)
    rs.AddObjectsToGroup(stops + [tid], rs.AddGroup())
    return [oid, crv, stops, tid, trims]


def junction_stage(doc, name, lines, trim, size, normal, gap):
    """Click near an end: stop Trim in ↔ tick at the very end (junction); the text follows the middle."""
    notch = set()
    while True:
        pt = rs.GetPoint(u"%s: click near a junction — the end where it continues on another panel (Enter — done)" % name)
        if pt is None:
            return
        d, i, e = min((pt.DistanceTo(l[1].PointAt((l[1].Domain.T0, l[1].Domain.T1)[e])), i, e)
                      for i, l in enumerate(lines) for e in (0, 1))
        oid, crv, stops, tid, trims = lines[i]
        notch ^= set([(i, e)])
        trims[e] = 0.0 if (i, e) in notch else trim
        s = trims[e] if e == 0 else crv.GetLength() - trims[e]
        doc.Objects.Replace(stops[e], stop_line(crv, s, size / 2.0 if (i, e) in notch else size, normal))
        te = rs.coercegeometry(tid)
        te.Plane = label_plane(crv, trims, te.Plane.ZAxis, gap)
        doc.Objects.Replace(tid, te)
        a = doc.Objects.FindId(tid).Attributes.Duplicate()
        a.SetUserString(TRIM, u"%r,%r" % tuple(trims))
        doc.Objects.ModifyAttributes(tid, a, True)
        doc.Views.Redraw()


HELP = u"""Options:
  Type — Zip: zip (both sides, Z<n>); Track: canalina (one side, Can<n>)
  Trim — stops this far in from the real line ends (zip shorter than the line); remembered per type
  Style — number text style (default PAT 14 mm)"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    cm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Centimeters, doc.ModelUnitSystem)  # 1 cm in document units
    nums = {}  # type → next number in this run
    kind = sc.sticky.get(KIND) if sc.sticky.get(KIND) in TYPES else "Zip"  # old sessions may remember "Can"
    ids, kind, trim = get_lines(kind, nums, u"only flip numbers", cm)
    if not ids:
        flip_stage(doc)
        return
    size = D.pts.get_number(u"Stop length", sc.sticky.get("zip_stop_size", cm), STYLE)
    if not size:
        return
    sc.sticky["zip_stop_size"] = size
    ds = D.pts.label_style(doc, STYLE)
    gap = 0.5 * ds.TextHeight * ds.DimensionScale
    normal = rs.ViewCPlane().ZAxis
    done = marked_lines()

    while ids:
        prefix, layer, _, junctions, _ = TYPES[kind]
        todo = [i for i in ids if not rs.IsCurveClosed(i) and str(i) not in done  # closed: no ends
                and rs.CurveLength(i) - 2 * trim > tol]
        if len(todo) < len(ids):
            print(u"Closed, already marked or shorter than 2 × Trim, skipped: %d" % (len(ids) - len(todo)))
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
            lines = [mark_line(doc, oid, rs.coercecurve(oid), name, trim, size, normal, ds, gap, attrs) for oid in todo]
            done.update(str(i) for i in todo)
            rs.UnselectAllObjects()
            doc.Views.Redraw()
            if len(lines) >= junctions:  # side split over several panels
                junction_stage(doc, name, lines, trim, size, normal, gap)
            print(u"%s: lines %d" % (name, len(lines)))
        rs.UnselectAllObjects()
        ids, kind, trim = get_lines(kind, nums, u"done", cm)
    flip_stage(doc)


if __name__ == "__main__":
    main()
