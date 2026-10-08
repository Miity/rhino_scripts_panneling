# -*- coding: utf-8 -*-
""""D" reinforcement at the end of a tube pocket.
First point — top corner of the pocket (centre of the D half-circle), second — bottom corner (where the D starts).
Part: a rectangle of width W from the second point to the first + an end extending past the first point by R
(W = 2R — half-circle; otherwise a half-ellipse W/2 × R, smooth, not wider than W). While picking the second point the D is shown live.
Loop: several D in a row (both ends of each pocket), Enter — done. The part lies in place,
layer Parts::Reinforcements, label "RD<n>" in a group; RD numbering continues between runs.
Options W, R and Style (label text style, default PAT 14 mm) — in the first point prompt, remembered.
Option Layout (default Yes): on the panel — D markup without the bottom (the bottom lies on the edge), full part — 10000 up
(ReinfCircle.add_part); No — full part in place.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Arc, ArcCurve, Curve, Plane, Polyline, PolylineCurve, Transform, Vector3d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("ReinfCircle", None)  # Rhino keeps modules from the first run for the session
from ReinfCircle import LAYER, UP_KEY, add_part, up_option, layer, next_number, off_panel, label_style, pick_style  # layer, numbering, style

STICKY = "ReinfD"
PREFIX = "RD"  # Reinforcement D


def d_shape(top, bottom, w, r, normal, tol):
    """Closed D curve: a rectangle of width w from bottom to top + an end r past top
    (half-circle when w = 2r, otherwise half-ellipse w/2 × r). None — points coincide."""
    u = top - bottom
    if u.Length <= tol:
        return None
    u.Unitize()
    v = Vector3d.CrossProduct(normal, u)
    v.Unitize()
    hw = w / 2.0
    rect = PolylineCurve(Polyline([top + v * hw, bottom + v * hw, bottom - v * hw, top - v * hw]))
    cap = ArcCurve(Arc(top - v * hw, top + u * hw, top + v * hw)).ToNurbsCurve()
    cap.Transform(Transform.Scale(Plane(top, u, v), r / hw, 1, 1))  # half-circle → half-ellipse along the axis
    joined = Curve.JoinCurves([rect, cap], tol)
    return joined[0] if len(joined) == 1 and joined[0].IsClosed else None


def get_top():
    """First point with options W, R, Layout, Style. (point, w, r) or None."""
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Top corner of the pocket — centre of the D (Enter — done)")
    gp.AcceptNothing(True)
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_w", 100.0), 0.001, 1e6)
    r = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 50.0), 0.001, 1e6)
    gp.AddOptionDouble("W", w)
    gp.AddOptionDouble("R", r)
    lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", True), "No", "Yes")
    gp.AddOptionToggle("Layout", lay)
    up = up_option(gp)
    i_style = gp.AddOption("Style")
    while True:
        res = gp.Get()
        sc.sticky[STICKY + "_w"] = w.CurrentValue
        sc.sticky[STICKY] = r.CurrentValue
        sc.sticky[STICKY + "_layout"] = lay.CurrentValue
        sc.sticky[UP_KEY] = up.CurrentValue
        if res == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == i_style:
                pick_style(sc.doc, STICKY)
            continue
        return (gp.Point(), w.CurrentValue, r.CurrentValue) if res == Rhino.Input.GetResult.Point else None


def get_bottom(top, w, r, normal, tol):
    """Second point with a live D. Point or None."""
    def draw(sender, e):
        c = d_shape(top, e.CurrentPoint, w, r, normal, tol)
        if c:
            e.Display.DrawCurve(c, sc.doc.Layers.CurrentLayer.Color, 2)
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Bottom corner of the pocket — where the D starts")
    gp.SetBasePoint(top, True)
    gp.DrawLineFromPoint(top, True)
    gp.DynamicDraw += draw
    try:
        return gp.Point() if gp.Get() == Rhino.Input.GetResult.Point else None
    finally:
        gp.DynamicDraw -= draw


HELP = u"""Options:
  W — D width (rectangular part)
  R — how far the D end extends past the top corner (W = 2R — half-circle)
  Layout — Yes: only markup on the panel, full part `Up` up; No: full part in place
  Up — how far up (along CPlane Y) the full part goes with Layout=Yes; shared by all part scripts
  Style — label text style (default PAT 14 mm)"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    normal = rs.ViewCPlane().ZAxis
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer(), -1)
    n = next_number(LAYER, PREFIX)
    made = 0
    while True:
        got = get_top()
        if got is None:
            break
        top, w, r = got
        bottom = get_bottom(top, w, r, normal, tol)
        if bottom is None:
            break
        crv = d_shape(top, bottom, w, r, normal, tol)
        if crv is None:
            print(u"Points coincide — skipped")
            continue
        label = u"%s%d" % (PREFIX, n)
        tp = Plane(rs.ViewCPlane())
        tp.Origin = (top + bottom) / 2.0
        te = Rhino.Geometry.TextEntity.Create(label, tp, label_style(doc, STICKY), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        base = min(crv.DuplicateSegments(), key=lambda g: g.PointAtNormalizedLength(0.5).DistanceTo(bottom))  # bottom of the D
        add_part(doc, [crv], te, off_panel(crv, [base], tol), attrs, sc.sticky[STICKY + "_layout"])
        doc.Views.Redraw()
        print(label)
        n += 1
        made += 1
    print(u"D reinforcements: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
