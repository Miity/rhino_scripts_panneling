# -*- coding: utf-8 -*-
"""Marks zips and tracks (keder track / guide rail) with stops and a number; the input is not touched.
Select panels (closed curves) and / or open curves once, then click near each edge / curve of one zip — on all
panels — and Enter; next zip, Enter on an empty zip — done. As in sewing_points: the nearest selected object to
the click, only its edge corner to corner near the click (corner — a break larger than Angle; a curve without
corners — the whole curve). One zip = both sides of the tape, a side may be split over several panels.
A track is one side, it may also be split. The kind is the Type option (Zip / Track, remembered):
zips Z1, Z2… in layer Parts::Zip, tracks (canalina) Can1, Can2… in Parts::Track.
For each edge: cross stops (centred, in the CPlane) Trim in from its real ends — the zip is usually a bit shorter
than the line (option Trim, remembered per type: Zip 4 cm, Track 0).
If a side is split (zip — 3+ edges, track — 2+), after Enter: a click near a junction end (where it continues on
another panel) turns its stop into a tick half as long, right at the edge end (no Trim there); another click — back.
Marks are on the text's side: a stop — a leg across the edge, then 90° along it towards the middle; a junction —
a short leg across. Number text near the middle between the stops (left or right of it), on a panel inside the
panel, on a curve above or below; the first spot whose text box is free (no other visible curve, text, point
crosses it), else the first spot with a warning. Text style — option Style (default PAT 14 mm).
Marks and text are one group per edge, in the type's layer; panels and curves keep their layer and group.
The data lives on the text (UserText): Zip = number, ZipLine = panel / curve id, ZipEdge = edge midpoint,
ZipAngle, ZipTrim = trim at start,end, ZipLen = edge length when marked — parts/ZipList.py finds the edge again
and measures it live. An edge that already has a number is skipped. Numbering continues from the largest number
in the layer (Z and Can separately).
Then the flip step: clicking a number moves it to the other side of the line (mirror) if it is in the way;
Enter — done. Enter on the object selection — straight to flipping."""
import os
import re
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.DocObjects import TextHorizontalAlignment, TextVerticalAlignment
from Rhino.Geometry import (Curve, LineCurve, Plane, Point3d, PointContainment, Polyline, PolylineCurve,
                            Vector3d)
from Rhino.Geometry.Intersect import Intersection

HERE = os.path.dirname(os.path.abspath(__file__))
# style picking and PAT styles — from scripts/markup/DotToPanelText.py
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "markup"))
for _m in ("DotToPanelText", "PatternTextStyles"):  # Rhino keeps modules from the first run for the session
    sys.modules.pop(_m, None)
import DotToPanelText as D

sys.path.insert(0, os.path.dirname(HERE))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

sys.path.insert(0, HERE)
for _m in ("ZipCover", "sewing_points"):
    sys.modules.pop(_m, None)
from ZipCover import close_panel, pick_edge  # panel edge corner to corner
from sewing_points import curve_edge  # open curve piece corner to corner

# type → (prefix, layer, in the prompt, from how many edges to ask about junctions, default Trim in cm)
TYPES = {"Zip": ("Z", "Parts::Zip", u"of the zip (both sides)", 3, 4.0),
         "Track": ("Can", "Parts::Track", u"of the track", 2, 0.0)}
KEY = "Zip"          # UserText on the text: number (Z<n> or Can<n>)
LINE = "ZipLine"     # UserText on the text: id of the panel / curve
EDGE = "ZipEdge"     # UserText on the text: "x,y,z" — edge midpoint (finds the edge again)
ANGLE_KEY = "ZipAngle"  # UserText on the text: Angle the edge was picked with
TRIM = "ZipTrim"     # UserText on the text: "start,end" — stop distance from the edge ends, document units
LEN = "ZipLen"       # UserText on the text: edge length when marked — used if the edge is not found any more
SIDE = "ZipSide"     # UserText on the text: 1 / -1 — marks left / right of the edge direction (the text's side)
JUNCTION = "ZipJunction"  # UserText on the text: "0,1" — which edge ends are junctions
STYLE = "ZipStops"   # sticky key of the label style (PatternTextStyles.label_style)
KIND = "ZipStops.kind"
ANGLE = "SewingMarks_angle"  # shared with sewing_points
TEXT_SPOTS = 6  # how far along the edge the text may move: text widths from the middle, each way


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


def zip_marks(edge, trims, junction, side, size, up):
    """Final marks of one edge, all on one side (side 1 — left of the edge direction, -1 — right; the text's side):
    a stop — leg across the edge then 90° along it towards the middle of the zip; a junction — a short leg across
    (half a stop) right at the end. Returns [Curve]."""
    length = edge.GetLength()
    out = []
    for e in (0, 1):
        s = trims[e] if e == 0 else length - trims[e]
        pt, tan = point_at(edge, s)
        n = Vector3d.CrossProduct(up, tan)
        n.Unitize()
        n *= side
        if junction[e]:
            out.append(LineCurve(pt, pt + n * (size / 2.0)))
        else:
            tan.Unitize()
            corner = pt + n * size
            out.append(PolylineCurve(Polyline([pt, corner, corner + tan * (size if e == 0 else -size)])))
    return out


def side_of(edge, s, direction, up):
    """1 if direction points left of the edge direction at arc length s, else -1."""
    tan = point_at(edge, s)[1]
    return 1 if Vector3d.CrossProduct(up, tan) * direction > 0 else -1


def edge_at(obj, click, angle, tol):
    """(edge, panel or None, error or None): panel edge corner to corner near the click, or the open curve's piece."""
    panel = close_panel(obj)  # closed, or "almost closed" from DXF → panel
    if panel is not None:
        res = pick_edge(panel, click, angle, tol)
        if not isinstance(res, tuple):
            return None, None, res
        return res[3], panel, None
    return curve_edge(obj, click, angle, tol), None, None


def mid_point(edge):
    return point_at(edge, edge.GetLength() / 2.0)[0]


def edge_of(t, tol):
    """(edge, panel or None) a number text marks, found again from its UserText; edge None — not found."""
    obj = rs.coercecurve(rs.GetUserText(t, LINE) or "", -1, False)
    if obj is None:
        return None, None
    try:
        pt = Point3d(*[float(x) for x in rs.GetUserText(t, EDGE).split(",")])
        angle = float(rs.GetUserText(t, ANGLE_KEY))
    except Exception:
        return obj, None  # no edge data — the whole curve
    edge, panel, err = edge_at(obj, pt, angle, tol)
    if edge is None or edge.PointAt(edge.ClosestPoint(pt)[1]).DistanceTo(pt) > 1000 * tol:
        return None, None
    return edge, panel


def inward(panel, edge, s, up, step):
    """Unit vector across the edge at arc length s, pointing into the panel."""
    pt, u = point_at(edge, s)
    side = Vector3d.CrossProduct(up, u)
    side.Unitize()
    if panel.Contains(pt + side * step, Plane(pt, up), step * 0.01) != PointContainment.Inside:
        side = -side
    return side


def is_number(rhino_object, geometry, component_index):
    return bool(rhino_object.Attributes.GetUserString(KEY))


def marked_edges():
    """[(panel / curve id str, edge midpoint or None)] of the number texts in the type layers."""
    out = []
    for layer in [t[1] for t in TYPES.values()]:
        for o in (rs.ObjectsByLayer(layer) or []) if rs.IsLayer(layer) else []:
            if rs.IsText(o) and rs.GetUserText(o, LINE):
                try:
                    pt = Point3d(*[float(x) for x in rs.GetUserText(o, EDGE).split(",")])
                except Exception:
                    pt = None
                out.append((rs.GetUserText(o, LINE), pt))
    return out


RINF_LINE = "RinfLine"  # UserText on a Rinforzo markup label: id of its panel (marks the label)
BORD_EDGE = "BordEdge"  # UserText on a Bordino label (B<w> on the panel): "x,y,z" — midpoint of its edge
BORD_LINE = "BordLine"  # UserText on a Bordino label: id of its panel
BORD_NEAR_CM = 10.0  # zip edge and Bordino edge midpoints closer than this = one side (see bordino_near)


def holds(strip, pt, tol):
    """pt inside the closed strip outline or on it."""
    ok, pl = strip.TryGetPlane(tol)
    return strip.Contains(pt, pl if ok else Plane.WorldXY, 100 * tol) != PointContainment.Outside


def canvas_part(doc, link):
    """(objects, LayoutUp vector) of the full part up on the canvas linked by PartLink link; ([], None) — none."""
    full = [o for o in doc.Objects if link and o.Attributes.GetUserString("PartLink") == link
            and not o.Attributes.GetUserString("PartMarkup") and o.Attributes.GetUserString("LayoutUp")]
    if not full:
        return [], None
    return full, Vector3d(*[float(x) for x in full[0].Attributes.GetUserString("LayoutUp").split(",")])


def stored_point(o, key):
    """Point3d kept in UserText key ("x,y,z"), or None."""
    try:
        return Point3d(*[float(x) for x in rs.GetUserText(o, key).split(",")])
    except Exception:
        return None


def zip_text(at, key=None):
    """The number text (Z<n> / Can<n>) whose edge midpoint satisfies at(point, text) — e.g. lies on a Rinforzo strip —
    or None; key(point, text) — of several, the smallest wins."""
    found = []
    for t in TYPES.values():
        for o in (rs.ObjectsByLayer(t[1]) or []) if rs.IsLayer(t[1]) else []:
            pt = stored_point(o, EDGE)
            if pt is not None and rs.IsText(o) and at(pt, o):
                found.append((key(pt, o) if key else 0, o))
    return min(found, key=lambda f: f[0])[1] if found else None


def rinforzo_text(doc, mid, tol):
    """The Rinforzo markup label (R<w>) whose strip holds mid (a zip edge midpoint), or None.
    The strip in place = its full part on the canvas moved back down."""
    for o in rs.ObjectsByType(512) or []:
        if rs.GetUserText(o, RINF_LINE):
            full, up = canvas_part(doc, rs.GetUserText(o, "PartLink"))
            for f in full:
                if isinstance(f.Geometry, Curve) and f.Geometry.IsClosed:
                    c = f.Geometry.DuplicateCurve()
                    c.Translate(-up)
                    if holds(c, mid, tol):
                        return o


def bordino_near(zid, zmid, bmid, pid, tol):
    """Distance between the zip's edge midpoint zmid and a Bordino edge midpoint bmid (panel id pid), if they are one
    side of the panel: midpoints closer than BORD_NEAR_CM, and the zip is on this panel's edge or on an open line
    inside it (zip line — old edge after ZipCover; the bordino is then on the outer edge), not on a neighbour panel.
    Else None. ponytail: a fixed distance — two parallel edges of a panel narrower than it could be mixed up."""
    d = zmid.DistanceTo(bmid)
    if d > BORD_NEAR_CM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Centimeters, sc.doc.ModelUnitSystem):
        return None
    line = rs.GetUserText(zid, LINE) or ""
    if line.lower() == str(pid).lower():
        return d
    obj, panel = rs.coercecurve(line, -1, False), rs.coercecurve(str(pid), -1, False)
    if obj is not None and not obj.IsClosed and panel is not None and holds(panel, zmid, tol):
        return d


def bordino_text(zid, mid, tol):
    """The Bordino label (B<w> on the panel) of the zip's edge (midpoint mid), the nearest one, or None."""
    found = []
    for o in rs.ObjectsByType(512) or []:
        pt, pid = stored_point(o, BORD_EDGE), rs.GetUserText(o, BORD_LINE)
        d = bordino_near(zid, mid, pt, pid, tol) if pt is not None and pid else None
        if d is not None:
            found.append((d, o))
    return min(found, key=lambda f: f[0])[1] if found else None


def labels_after(doc, zid, mid, tol, steps=None):
    """Labels of the zip's edge (midpoint mid) right after its number zid, in the order Z<n> R<w> B<w>.
    Returns the Rinforzo label or None."""
    prev, rid = zid, rinforzo_text(doc, mid, tol)
    for o in (rid, bordino_text(zid, mid, tol)):
        if o:
            beside(doc, prev, o, steps)
            prev = o
    return rid


def beside(doc, zid, rid, steps=None):
    """The Rinforzo label rid right after the number text zid (reading direction), same baseline, a gap apart.
    Only the label moves — the number's marks depend on its place."""
    z = rs.coercegeometry(zid)
    pl = z.Plane
    # size measured flat with its style, as in place_text: a Duplicate loses the style, the box in its own plane is
    # loose for turned text
    ds = doc.DimStyles.FindId(z.DimensionStyleId) or doc.DimStyles.Current
    bb = Rhino.Geometry.TextEntity.Create(z.PlainText, Plane.WorldXY, ds, False, 0, 0).GetBoundingBox(True)
    w, h = bb.Max.X - bb.Min.X, bb.Max.Y - bb.Min.Y
    end = {TextHorizontalAlignment.Left: w, TextHorizontalAlignment.Center: w / 2.0}.get(z.TextHorizontalAlignment, 0.0)
    r = rs.coercegeometry(rid).Duplicate()
    r.Plane = Plane(pl.PointAt(end + 0.4 * h, 0), pl.XAxis, pl.YAxis)
    r.TextHorizontalAlignment = TextHorizontalAlignment.Left
    r.TextVerticalAlignment = z.TextVerticalAlignment
    if steps:
        steps.change(rid)
    doc.Objects.Replace(rid, r)


def to_part(doc, link, marks, text, steps):
    """Zip marks (curves) and the number text onto the full part of a Rinforzo strip (PartLink link) up on the canvas:
    marks copied by its LayoutUp, its label becomes text ('Z20 R6')."""
    full, up = canvas_part(doc, link)
    if not full:
        return
    group = rs.ObjectGroups(full[0].Id)
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = full[0].Attributes.LayerIndex  # the part's own layer
    new = []
    for c in marks:
        c = c.DuplicateCurve()
        c.Translate(up)
        new.append(doc.Objects.AddCurve(c, attrs))
    if group:
        rs.AddObjectsToGroup(new, group[0])
    for o in full:
        if rs.IsText(o.Id):
            steps.change(o.Id)
            rs.TextObjectText(o.Id, text)


def is_marked(marked, oid, mid, near):
    return any(i == str(oid) and (p is None or p.DistanceTo(mid) < near) for i, p in marked)


def obstacles(doc):
    """[(bbox, curve or None)] of the visible curves, texts, points, dots — what a number text must not cross."""
    s = Rhino.DocObjects.ObjectEnumeratorSettings()
    s.HiddenObjects = False
    s.VisibleFilter = True
    out = []
    # ponytail: every visible object is scanned once per zip — fine for pattern files, slow for huge ones
    for o in doc.Objects.GetObjectList(s):
        g = o.Geometry
        if isinstance(g, Curve):
            out.append((g.GetBoundingBox(True), g))
        elif isinstance(g, (Rhino.Geometry.Point, Rhino.Geometry.TextDot, Rhino.Geometry.AnnotationBase)):
            out.append((g.GetBoundingBox(True), None))
    return out


def blocked(corners, obs, up, tol):
    """True if the text box (4 corners) is crossed by an obstacle or holds one."""
    rect = PolylineCurve(Polyline(list(corners) + [corners[0]]))
    rb = rect.GetBoundingBox(True)
    for bb, g in obs:
        if bb.Min.X > rb.Max.X or bb.Max.X < rb.Min.X or bb.Min.Y > rb.Max.Y or bb.Max.Y < rb.Min.Y:
            continue
        if g is None:
            return True  # text / point / dot box overlaps — conservative
        if Intersection.CurveCurve(rect, g, tol, tol).Count:
            return True
        if rect.Contains(g.PointAtStart, Plane(g.PointAtStart, up), tol) == PointContainment.Inside:
            return True
    return False


def place_text(name, edge, panel, s_c, ds, gap, up, tol, obs):
    """Number text next to arc length s_c (the middle between the stops): left / right of it, inside the panel (on a curve —
    above / below), the first free spot. Returns (TextEntity, its corners, found a free spot, side 1 / -1 of the
    edge it is on)."""
    te0 = Rhino.Geometry.TextEntity.Create(name, Plane.WorldXY, ds, False, 0, 0)
    bb = te0.GetBoundingBox(True)
    w, ht = bb.Max.X - bb.Min.X, bb.Max.Y - bb.Min.Y
    h = ds.TextHeight * ds.DimensionScale
    length = edge.GetLength()
    first = None
    for k in range(TEXT_SPOTS):
        for along in (1, -1):
            s = s_c + along * (h + k * w)
            if not 0 <= s <= length:
                continue
            pt, u = point_at(edge, s)
            if u.X < -1e-9 or (abs(u.X) < 1e-9 and u.Y < 0):
                u = -u  # reads left to right
            v = Vector3d.CrossProduct(up, u)
            toward = point_at(edge, min(length, s + 1e-3 * length))[0] - pt  # +s direction
            left = (toward * u > 0) == (along > 0)  # text grows from the anchor away from the middle
            if panel is not None:
                sides = [inward(panel, edge, s, up, h) * v > 0]
            else:
                sides = [True, False]
            for above in sides:
                plane = Plane(pt + v * (gap if above else -gap), u, v)
                x0, x1 = (0.0, w) if left else (-w, 0.0)
                y0, y1 = (0.0, ht) if above else (-ht, 0.0)
                corners = [plane.PointAt(x0, y0), plane.PointAt(x1, y0), plane.PointAt(x1, y1), plane.PointAt(x0, y1)]
                if panel is not None and any(panel.Contains(c, Plane(c, up), tol) != PointContainment.Inside
                                             for c in corners):
                    continue
                te = Rhino.Geometry.TextEntity.Create(name, plane, ds, False, 0, 0)
                te.TextHorizontalAlignment = TextHorizontalAlignment.Left if left else TextHorizontalAlignment.Right
                te.TextVerticalAlignment = TextVerticalAlignment.Bottom if above else TextVerticalAlignment.Top
                side = side_of(edge, s, v if above else -v, up)
                if first is None:
                    first = (te, corners, side)
                if not blocked(corners, obs, up, tol):
                    return te, corners, True, side
    if first is None:  # nothing fits inside the panel at all — at the middle
        pt, u = point_at(edge, s_c)
        te = Rhino.Geometry.TextEntity.Create(name, Plane(pt, u, Vector3d.CrossProduct(up, u)), ds, False, 0, 0)
        return te, [pt, pt, pt, pt], False, 1
    return first[0], first[1], False, first[2]


def flip_label(doc, t, tol, steps=None):
    """Number to the other side of its line (mirror about the line, alignment Bottom ↔ Top) and its marks with it."""
    edge, panel = edge_of(t, tol)
    if edge is None:
        return False
    te = rs.coercegeometry(t)
    pl = te.Plane
    o = pl.Origin
    cp = edge.PointAt(edge.ClosestPoint(o)[1])
    pl.Origin = cp + (cp - o)
    te.Plane = pl
    te.TextVerticalAlignment = (TextVerticalAlignment.Top if te.TextVerticalAlignment == TextVerticalAlignment.Bottom
                                else TextVerticalAlignment.Bottom)
    doc.Objects.Replace(t, te)
    labels_after(doc, t, mid_point(edge), tol, steps)
    try:
        side = -int(rs.GetUserText(t, SIDE))
        junction = [x == "1" for x in rs.GetUserText(t, JUNCTION).split(",")]
        size = float(rs.GetUserText(t, "ZipSize"))
    except Exception:
        return True  # marks from an older version — only the text moves
    groups = rs.ObjectGroups(t) or []
    for g in groups:
        for m in rs.ObjectsByGroup(g) or []:
            if rs.IsCurve(m):
                if steps:
                    steps.delete(m)
                else:
                    doc.Objects.Delete(m, True)
    a = doc.Objects.FindId(t).Attributes
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = a.LayerIndex
    up = te.Plane.ZAxis
    new = [doc.Objects.AddCurve(c, attrs)
           for c in zip_marks(edge, read_trims(t), junction, side, size, up)]
    if groups:
        rs.AddObjectsToGroup(new, groups[0])
    a = a.Duplicate()
    a.SetUserString(SIDE, str(side))
    doc.Objects.ModifyAttributes(t, a, True)
    return True


def zip_span(edge, trims):
    """The zip itself, stop to stop: the edge without the trims at its ends (for the strip's part on the canvas)."""
    return edge.Trim(point_param(edge, trims[0]), point_param(edge, edge.GetLength() - trims[1]))


def point_param(crv, s):
    ok, t = crv.LengthParameter(s)
    return t if ok else (crv.Domain.T0 if s <= 0 else crv.Domain.T1)


def read_trims(t):
    try:
        return [float(x) for x in rs.GetUserText(t, TRIM).split(",")]
    except Exception:
        return [0.0, 0.0]


def flip_stage(doc):
    steps = Steps(doc)
    tol = doc.ModelAbsoluteTolerance
    while True:
        go = Rhino.Input.Custom.GetObject()
        go.SetCommandPrompt(u"Click a zip number to move it to the other side of the line (Enter — done)")
        go.GeometryFilter = Rhino.DocObjects.ObjectType.Annotation
        go.SetCustomGeometryFilter(is_number)
        go.EnablePreSelect(False, True)
        go.AcceptNothing(True)
        i_undo = go.AddOption("Undo")
        res = go.Get()
        if res == Rhino.Input.GetResult.Option and go.OptionIndex() == i_undo:
            steps.undo()
            continue
        if res != Rhino.Input.GetResult.Object:
            return
        t = go.Object(0).ObjectId
        steps.start()
        steps.change(t)
        if not flip_label(doc, t, tol, steps):
            print(u"%s: its edge is gone (panel / curve deleted or changed)" % rs.GetUserText(t, KEY))
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


def layer_attrs(doc, kind):
    layer = TYPES[kind][1]
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(layer):
        rs.AddLayer(layer.split("::")[1], parent="Parts")
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer, -1)
    return attrs


def ask_click(kind, nums, picked, cm):
    """Click near an edge / curve with options Type / Trim / Angle / Undo. Returns (point, UNDO or None, type, trim)."""
    while True:
        prefix, _, what, _, trim_cm = TYPES[kind]
        trim = Rhino.Input.Custom.OptionDouble(sc.sticky.get("ZipStops.trim." + kind, trim_cm * cm), 0.0, 1e6)
        angle = Rhino.Input.Custom.OptionDouble(sc.sticky.get(ANGLE, 30.0), 1.0, 179.0)
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"%s%d: click near each edge / curve %s — %d picked (Enter — %s)" % (
            prefix, nums.get(kind) or next_number(kind), what, picked, u"finish it" if picked else u"done"))
        gp.AcceptNothing(True)
        opt_undo = gp.AddOption("Undo")
        opt_type = gp.AddOption("Type", kind)
        gp.AddOptionDouble("Trim", trim)
        gp.AddOptionDouble("Angle", angle)
        res = gp.Get()
        sc.sticky["ZipStops.trim." + kind] = trim.CurrentValue
        sc.sticky[ANGLE] = angle.CurrentValue
        if res == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == opt_undo:
                return UNDO, kind, trim.CurrentValue
            if gp.OptionIndex() == opt_type:
                kind = "Track" if kind == "Zip" else "Zip"
                sc.sticky[KIND] = kind
            continue
        return (gp.Point() if res == Rhino.Input.GetResult.Point else None), kind, trim.CurrentValue


def junction_stage(doc, name, lines, size, up):
    """Click near an edge end: stop Trim in ↔ tick at the very end (junction). Returns the junction ends {(i, e)}."""
    notch = set()
    steps, toggled = Steps(doc), []
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"%s: click near a junction — the end where it continues on another panel (Enter — done)" % name)
        gp.AcceptNothing(True)
        i_undo = gp.AddOption("Undo")
        res = gp.Get()
        if res == Rhino.Input.GetResult.Option and gp.OptionIndex() == i_undo:
            if toggled and steps.undo():  # stop back; the end is a normal / junction end again
                i, e = toggled.pop()
                notch ^= set([(i, e)])
                lines[i]["trims"][e] = 0.0 if (i, e) in notch else lines[i]["trim"]
            elif not toggled:
                print(u"Nothing to undo")
            continue
        if res != Rhino.Input.GetResult.Point:
            return notch
        steps.start()
        toggled.append(toggle_end(doc, lines, notch, gp.Point(), size, up, steps))
        doc.Views.Redraw()


def toggle_end(doc, lines, notch, pt, size, up, steps=None):
    """Edge end nearest pt: stop Trim in ↔ junction tick at the very end. Returns (edge index, end 0 / 1)."""
    d, i, e = min((pt.DistanceTo(l["edge"].PointAt((l["edge"].Domain.T0, l["edge"].Domain.T1)[e])), i, e)
                  for i, l in enumerate(lines) for e in (0, 1))
    l = lines[i]
    if steps:
        steps.change(l["stops"][e])
    notch ^= set([(i, e)])
    l["trims"][e] = 0.0 if (i, e) in notch else l["trim"]
    s = l["trims"][e] if e == 0 else l["edge"].GetLength() - l["trims"][e]
    doc.Objects.Replace(l["stops"][e], stop_line(l["edge"], s, size / 2.0 if (i, e) in notch else size, up))
    return i, e


def finish_zip(doc, lines, notch, name, kind, size, ds, gap, up, tol, angle, steps):
    """Number texts with the data, then the final marks (stops, junctions) on the text's side;
    the click-time crosses are removed. Marks and text one group per edge."""
    attrs = layer_attrs(doc, kind)
    for l in lines:
        for sid in l["stops"]:
            steps.delete(sid)
    obs = obstacles(doc)
    for i, l in enumerate(lines):
        edge, panel = l["edge"], l["panel"]
        s_c = (l["trims"][0] + edge.GetLength() - l["trims"][1]) / 2.0
        te, corners, free, side = place_text(name, edge, panel, s_c, ds, gap, up, tol, obs)
        if not free:
            print(u"%s: no free spot for the number — placed anyway, move / flip it" % name)
        obs.append((PolylineCurve(Polyline(list(corners) + [corners[0]])).GetBoundingBox(True), None))
        junction = [(i, 0) in notch, (i, 1) in notch]
        marks = zip_marks(edge, l["trims"], junction, side, size, up)
        new = [doc.Objects.AddCurve(c, attrs) for c in marks]
        obs.extend((c.GetBoundingBox(True), c) for c in marks)
        a = attrs.Duplicate()
        a.SetUserString(KEY, name)
        a.SetUserString(LINE, str(l["id"]))
        m = mid_point(edge)
        a.SetUserString(EDGE, u"%r,%r,%r" % (m.X, m.Y, m.Z))
        a.SetUserString(ANGLE_KEY, u"%r" % angle)
        a.SetUserString(TRIM, u"%r,%r" % tuple(l["trims"]))
        a.SetUserString(LEN, u"%r" % edge.GetLength())
        a.SetUserString(SIDE, str(side))
        a.SetUserString(JUNCTION, u"%d,%d" % tuple(junction))
        a.SetUserString("ZipSize", u"%r" % size)
        zid = doc.Objects.AddText(te, a)
        new.append(zid)
        rs.AddObjectsToGroup(new, rs.AddGroup())
        rid = labels_after(doc, zid, m, tol, steps)  # Rinforzo / Bordino made before: Z<n> R<w> B<w>
        if rid:  # the strip's part on the canvas shows the zip too
            to_part(doc, rs.GetUserText(rid, "PartLink"), marks + [zip_span(edge, l["trims"])], name + u" " + rs.TextObjectText(rid), steps)


HELP = u"""Options:
  Type — Zip: zip (both sides, Z<n>); Track: canalina (one side, Can<n>) — after Enter the console shows both sides and their difference (Warning > 5 mm)
  Trim — stops this far in from the real edge ends (zip shorter than the line); remembered per type
  Angle — a break larger than this angle = corner (the edge is taken corner to corner; shared with Battute)
  Style — number text style (default PAT 14 mm)
  Undo — take back the last step: while clicking — the last edge, with none picked — the whole previous zip /
         track (its number is reused); at junction clicks — the last junction; at number flipping — the last flip"""
# printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    cm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Centimeters, doc.ModelUnitSystem)  # 1 cm in document units
    ids = rs.GetObjects(u"Select panels and / or curves with zips (Enter — only flip numbers)",
                        rs.filter.curve, preselect=True)
    if not ids:
        flip_stage(doc)
        return
    size = D.pts.get_number(u"Stop length", sc.sticky.get("zip_stop_size", cm), STYLE)
    if not size:
        return
    sc.sticky["zip_stop_size"] = size
    ds = D.pts.label_style(doc, STYLE)
    gap = 0.5 * ds.TextHeight * ds.DimensionScale
    view = doc.Views.ActiveView
    up = view.ActiveViewport.ConstructionPlane().ZAxis if view else Vector3d.ZAxis  # headless: WorldXY
    objs = [(i, rs.coercecurve(i)) for i in ids]
    rs.UnselectAllObjects()
    near = 0.1 * cm  # same edge if its midpoint is within 1 mm
    marked = marked_edges()
    nums = {}  # type → next number in this run
    kind = sc.sticky.get(KIND) if sc.sticky.get(KIND) in TYPES else "Zip"
    steps, history, lines = Steps(doc), [], []  # history: per finished zip (type, its steps, its marked edges)

    while True:
        click, kind, trim = ask_click(kind, nums, len(lines), cm)
        if click == UNDO:
            if lines:
                steps.undo()
                lines.pop()
            elif history:
                k, n, keys = history.pop()
                for _ in range(n):
                    steps.undo()
                nums[k] -= 1
                for key in keys:
                    marked.remove(key)
            else:
                print(u"Nothing to undo")
            continue
        if click is None:
            if not lines:
                break
            prefix, _, _, junctions, _ = TYPES[kind]
            n = nums.get(kind) or next_number(kind)
            name = prefix + str(n)
            notch = junction_stage(doc, name, lines, size, up) if len(lines) >= junctions else set()
            steps.start()
            finish_zip(doc, lines, notch, name, kind, size, ds, gap, up, tol, sc.sticky[ANGLE], steps)
            nums[kind] = n + 1
            keys = [(str(l["id"]), l["mid"]) for l in lines]
            marked.extend(keys)
            history.append((kind, len(lines) + 1, keys))
            print(u"%s: edges %d" % (name, len(lines)))
            if kind == "Zip" and len(lines) > 1:
                import ZipList  # imports ZipStops itself — here, not at the top
                mm = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Millimeters)
                a, b = ZipList.sides([(l["edge"].GetLength() - sum(l["trims"])) * mm for l in lines])
                print(u"%s%s: sides %d / %d mm, diff %d mm" % (u"Warning, " if a - b > ZipList.DIFF_MM else u"",
                                                              name, round(a), round(b), round(a - b)))
            lines = []
            doc.Views.Redraw()
            continue
        oid, obj = min(objs, key=lambda o: o[1].PointAt(o[1].ClosestPoint(click)[1]).DistanceTo(click))
        edge, panel, err = edge_at(obj, click, sc.sticky[ANGLE], tol)
        if edge is None:
            print(u"Skipped: %s" % err)
            continue
        mid = mid_point(edge)
        if is_marked(marked + [(str(l["id"]), l["mid"]) for l in lines], oid, mid, near):
            print(u"Skipped: this edge already has a number")
            continue
        if edge.GetLength() - 2 * trim <= tol:
            print(u"Skipped: edge shorter than 2 × Trim")
            continue
        steps.start()
        attrs = layer_attrs(doc, kind)
        stops = [doc.Objects.AddLine(stop_line(edge, s, size, up), attrs) for s in (trim, edge.GetLength() - trim)]
        lines.append({"id": oid, "edge": edge, "panel": panel, "stops": stops, "trim": trim,
                      "trims": [trim, trim], "mid": mid})
        doc.Views.Redraw()
    flip_stage(doc)


if __name__ == "__main__":
    main()
