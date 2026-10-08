# -*- coding: utf-8 -*-
"""Corner reinforcement — circle.
Select a boundary: a closed panel or lines forming a corner. Enter the radius R.
Click near the corner on the side to keep. The circle centre is the vertex closest to the click
(curve kink, line end or line intersection). Only the part of the circle between the
sides of the corner is kept. The part lies in place, in layer Parts::Reinforcements, with label "RC<n>  r=…" (r in cm)
in a group. RC numbering continues between runs. The source curves are not changed.
Option Layout (default Yes) — as in all Reinf (add_part): only markup stays on the panel — part lines not lying on the panel
curves, + label; the full part (cut, seam, label) — UP (10000) up along CPlane Y, to be laid out by Layout.
Layout=No — full part in place, no markup.
The reinforcement is sewn on top of the material, so there is no seam allowance.
"""
import os
import re
import sys

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import System
from System.Collections.Generic import List
from Rhino.Geometry import (AreaMassProperties, ArcCurve, Circle, Continuity, Curve, CurveEnd,
                            CurveExtensionStyle, Plane, Point3d, Transform)
from Rhino.Geometry.Intersect import Intersection

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
sys.modules.pop("PatternTextStyles", None)  # Rhino keeps modules from the first run for the session
from PatternTextStyles import cm, label_style, pick_style  # label number in cm; style: option Style, default PAT 14 mm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/: shared click_undo
sys.modules.pop("click_undo", None)
from click_undo import UNDO, Steps  # option Undo: take back the last click

STICKY = "ReinfCircle"
LAYER = "Parts::Reinforcements"
PREFIX = "RC"  # Reinforcement Circle; other shapes have their own prefixes (RS, RT…)
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
    """layout: full part (geometry full + label te) — UP up along CPlane Y, its own group;
    in place — markup (curves markup + the same label), its own group. Returns (full id, markup ids).
    Without layout — full part in place, no markup (markup ids = []).
    The pair is linked by UserText PartLink (common id); the full part has LayoutUp (offset vector), the markup — PartMarkup.
    """
    up = rs.ViewCPlane().YAxis * (sc.sticky.get(UP_KEY, UP) if layout else 0.0)
    xf = Transform.Translation(up)

    def add(geo):
        geo = geo.Duplicate()
        geo.Transform(xf)
        return doc.Objects.Add(geo, attrs)
    ids = [add(c) for c in full] + [add(te)], []
    if layout:
        ids = ids[0], [doc.Objects.AddCurve(c, attrs) for c in markup] + [doc.Objects.AddText(te, attrs)]
    if layout:
        link = str(System.Guid.NewGuid())
        for o in ids[0] + ids[1]:
            rs.SetUserText(o, "PartLink", link)
        for o in ids[0]:
            rs.SetUserText(o, "LayoutUp", "%r,%r,%r" % (up.X, up.Y, up.Z))
        for o in ids[1]:
            rs.SetUserText(o, "PartMarkup", "1")
    for g in ids:
        if g:
            rs.AddObjectsToGroup(g, rs.AddGroup())
    return ids


def corners(curves, tol):
    """Centre candidates: kinks, ends of open curves, curve-curve intersections."""
    pts = []
    for c in curves:
        if not c.IsClosed:
            pts += [c.PointAtStart, c.PointAtEnd]
        t, t1 = c.Domain.T0, c.Domain.T1
        while True:
            ok, t = c.GetNextDiscontinuity(Continuity.G1_locus_continuous, t, t1)
            if not ok:
                break
            pts.append(c.PointAt(t))
    for i in range(len(curves)):
        for j in range(i + 1, len(curves)):
            for e in Intersection.CurveCurve(curves[i], curves[j], tol, tol) or []:
                pts.append(e.PointA)
    # ponytail: a rounded (filleted) corner has no vertex — the centre is taken from the nearest kink;
    # if needed — look for a virtual intersection of the extended sides.
    return pts


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


def next_number(lay, prefix=PREFIX):
    """Next number after the largest <prefix><n> (RC, RD…) already in the layer."""
    nums = [0]
    for o in rs.ObjectsByLayer(lay) or []:
        m = re.match(prefix + r"(\d+)\b", rs.TextObjectText(o) if rs.IsText(o) else "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


HELP = u"""Options:
  R — reinforcement circle radius (centre — panel corner)
  Layout — Yes: only markup on the panel, full part `Up` up; No: full part in place
  Up — how far up (along CPlane Y) the full part goes with Layout=Yes; shared by all part scripts
  Style — label text style (default PAT 14 mm)
  Undo — take back the last click (again — the click before it); its number is reused"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    ids = rs.GetObjects(u"Select a boundary: closed panel or corner lines", rs.filter.curve, preselect=True)
    if not ids:
        return
    r = rs.GetReal(u"Reinforcement circle radius R", sc.sticky.get(STICKY, 40.0), 0.001)
    if r is None:
        return
    sc.sticky[STICKY] = r

    tol = doc.ModelAbsoluteTolerance
    curves = [rs.coercecurve(i) for i in ids]
    cands = corners(curves, tol)
    if not cands:
        print(u"The selected curves have no corners")
        return
    normal = rs.ViewCPlane().ZAxis
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer(), -1)
    n = next_number(LAYER)
    made = 0
    steps = Steps(doc)
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Click near the corner, on the side to keep (Enter — done)")
        gp.AcceptNothing(True)
        lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", True), "No", "Yes")
        i_undo = gp.AddOption("Undo")
        gp.AddOptionToggle("Layout", lay)
        up = up_option(gp)
        i_style = gp.AddOption("Style")
        undo = False
        while gp.Get() == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_style:
                pick_style(doc, STICKY)
            if gp.OptionIndex() == i_undo:
                undo = True
                break
        sc.sticky[STICKY + "_layout"] = lay.CurrentValue
        sc.sticky[UP_KEY] = up.CurrentValue
        if undo:
            if steps.undo():
                n, made = n - 1, made - 1
            continue
        if gp.CommandResult() != Rhino.Commands.Result.Success or gp.Result() != Rhino.Input.GetResult.Point:
            break
        steps.start()
        click = gp.Point()
        center = min(cands, key=lambda p: p.DistanceTo(click))
        if center.DistanceTo(click) > r:
            print(u"Corner farther than R from the click — click closer to the vertex")
            continue
        crv = piece(curves, center, click, r, normal, tol)
        if crv is None:
            print(u"Could not cut the sector (click on the line itself? curves not in the CPlane?)")
            continue
        label = u"%s%d  r=%s" % (PREFIX, n, cm(r))
        amp = AreaMassProperties.Compute(crv)
        tp = Plane(rs.ViewCPlane())
        tp.Origin = amp.Centroid if amp else center
        te = Rhino.Geometry.TextEntity.Create(label, tp, label_style(doc, STICKY), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        add_part(doc, [crv], te, off_panel(crv, curves, tol), attrs, lay.CurrentValue)
        doc.Views.Redraw()
        print(label)
        n += 1
        made += 1
    print(u"Circle reinforcements: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
