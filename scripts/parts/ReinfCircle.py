# -*- coding: utf-8 -*-
"""Shared helpers of the part scripts (Reinf D / O, Rinforzo, Bordino, TubePockets, ZipCover) — no button of its own
(the corner circle RC<n> was dropped; RC labels in older drawings are still read by Legend / Layout).
add_part — the full part UP (10000) up along CPlane Y + markup on the panel, one group; option Up; layer
Parts::Reinforcements; numbering <prefix><n>; off_panel — markup lines not lying on the panel; piece — circle sector
between curves. Label style — PatternTextStyles.
"""
import os
import re
import sys

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import System
from System.Collections.Generic import List
from Rhino.Geometry import ArcCurve, Circle, Curve, CurveEnd, CurveExtensionStyle, Plane, Point3d, Transform

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
sys.modules.pop("PatternTextStyles", None)  # Rhino keeps modules from the first run for the session
from PatternTextStyles import by_layer, label_attrs, label_style, pick_style  # re-exported for Reinf D / O, Rinforzo

LAYER = "Parts::Reinforcements"
UP = 10000.0  # default: the full part is this far up along CPlane Y from the markup (option Up)
UP_KEY = "Parts_up"  # sticky: option Up, shared by all part scripts (Reinf*, TubePockets)


def up_option(gp):
    """Option Up — how far up the full part goes. Store CurrentValue in sc.sticky[UP_KEY] after each Get."""
    o = Rhino.Input.Custom.OptionDouble(sc.sticky.get(UP_KEY, UP), 0.0, 1e7)
    gp.AddOptionDouble("Up", o)
    return o


def off_panel(crv, curves, tol):
    """Markup: segments of crv not lying on curves (panel lines are not duplicated), joined."""
    def on(p):
        return any(c.PointAt(c.ClosestPoint(p)[1]).DistanceTo(p) <= tol for c in curves)
    keep = [s for s in crv.DuplicateSegments() or [crv]
            if not all(on(s.PointAtNormalizedLength(t)) for t in (0.25, 0.5, 0.75))]
    return list(Curve.JoinCurves(keep, tol)) if keep else []


def add_part(doc, full, te, markup, attrs, layout=True):
    """layout: full part (geometry full + label te) — UP up along CPlane Y; in place — markup (curves markup + the same
    label); both in one group (selected / moved / deleted together). Returns (full ids, markup ids).
    Without layout — full part in place, no markup (markup ids = []).
    The pair is linked by UserText PartLink (common id); the full part has LayoutUp (offset vector), the markup — PartMarkup.
    """
    up = rs.ViewCPlane().YAxis * (sc.sticky.get(UP_KEY, UP) if layout else 0.0)
    xf = Transform.Translation(up)

    def add(geo, a=attrs):
        geo = geo.Duplicate()
        geo.Transform(xf)
        return doc.Objects.Add(geo, a)
    text = label_attrs(doc, attrs)  # labels — Labels::<Name>
    ids = [add(c) for c in full] + [add(te, text)], []
    if layout:
        ids = ids[0], [doc.Objects.AddCurve(c, attrs) for c in markup] + [doc.Objects.AddText(te, text)]
    if layout:
        link = str(System.Guid.NewGuid())
        for o in ids[0] + ids[1]:
            rs.SetUserText(o, "PartLink", link)
        for o in ids[0]:
            rs.SetUserText(o, "LayoutUp", "%r,%r,%r" % (up.X, up.Y, up.Z))
        for o in ids[1]:
            rs.SetUserText(o, "PartMarkup", "1")
    rs.AddObjectsToGroup(ids[0] + ids[1], rs.AddGroup())
    return ids


def piece(curves, center, toward, r, normal, tol):
    """Part of the circle (centre center, radius r) lying between curves on the side of point toward. None — failed."""
    plane = Plane(center, normal)
    d = plane.ClosestPoint(toward) - center
    if not d.Unitize():
        return None
    bounds = List[Curve]()
    bounds.Add(ArcCurve(Circle(plane, r)))
    for c in curves:
        # open lines are extended past the corner and past the circle: a short side still closes the region
        ext = None if c.IsClosed else c.Extend(CurveEnd.Both, 2 * r, CurveExtensionStyle.Line)
        bounds.Add(ext or c)
    pts = List[Point3d]()
    pts.Add(center + d * (r * 0.5))  # point inside the wedge: the click may be farther than R
    res = Curve.CreateBooleanRegions(bounds, plane, pts, False, tol)
    if res is None or res.RegionCount == 0:
        return None
    region = res.RegionCurves(0)
    return region[0] if region and region[0].IsClosed else None


def layer():
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Reinforcements", parent="Parts")
    return LAYER


def next_number(lay, prefix):
    """Next number after the largest <prefix><n> (RC, RD…) already in the layer (or its Labels twin)."""
    nums = [0]
    for o in by_layer(lay):
        m = re.match(prefix + r"(\d+)\b", rs.TextObjectText(o) if rs.IsText(o) else "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1
