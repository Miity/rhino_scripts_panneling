# -*- coding: utf-8 -*-
"""Panel number on parts: " P<n>" is appended to the label of each selected part ("R6" → "R6 P4", "B3.5" → "B3.5 P4").
Select parts (window allowed — over the parts up and / or the panels with their markup). Nothing is stored when a part
is made: the panel is found now, from where the part sits on it, so it works on old drawings and after renumbering.
  - a part up (Reinf*, Rinforzo, Bordino — UserText LayoutUp; TubePockets — TP_Up) is moved back down to its place;
    a part made with Layout=No is already in place;
  - the point on the panel: the centroid of the part's outline; Bordino lies outside its panel — a step from its edge
    midpoint (BordEdge on the label in its group) away from the part, into the panel;
  - the panel: the smallest closed curve in Parts::Panels with a number (UserText Part = P<n>, Panels) around the point.
Only the part's own label changes (the copy up or the part in place), not the markup on the panel. A repeated run replaces
the old " P<n>". UserText Panel = P<n> on the label. Skipped with a message: panels themselves, fascia strips
(Parts::Strips — made from curves, no place on a panel), canvas copies (LayoutOf), parts with no numbered panel under them.
"""
import os
import re
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import AreaMassProperties, PointContainment, Vector3d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _m in ("LayoutParts", "ZipStops"):  # Rhino keeps modules from the first run for the session
    sys.modules.pop(_m, None)
from LayoutParts import MARKUP, closed, is_part, parts  # a group = markup on the panel + the part up → two
from ZipStops import BORD_EDGE, stored_point

PANELS = "Parts::Panels"
BORDINO = "Parts::Bordino"
SKIP = ("Parts::Panels", "Parts::Strips")  # panels themselves; fascia strips — no place on a panel
KEY = "Panel"  # UserText on the part label: P<n>
SUFFIX = re.compile(r"\s+P\d+$")
STEP_MM = 10.0  # Bordino: from its edge midpoint this far into the panel


def relabel(text, panel):
    """'R6', 'P4' → 'R6 P4'; an old panel number is replaced."""
    return SUFFIX.sub(u"", text.rstrip()) + u" " + panel


def up_of(objs):
    """Offset of the part from its place on the panel (LayoutUp / TP_Up); none — the part is in place."""
    for o in objs:
        v = o.Attributes.GetUserString("LayoutUp") or o.Attributes.GetUserString("TP_Up")
        if v:
            return Vector3d(*[float(x) for x in v.split(",")])
    return Vector3d.Zero


def probe(doc, objs):
    """A point on the panel the part (objects objs) belongs to, or the reason why there is none."""
    outlines = [o.Geometry for o in objs if closed(o.Geometry) and not o.Geometry.IsCircle()]
    if not outlines:
        return u"no outline"
    c = max(outlines, key=lambda g: g.GetBoundingBox(True).Diagonal.Length)
    amp = AreaMassProperties.Compute(c)
    pt = (amp.Centroid if amp else c.GetBoundingBox(True).Center) - up_of(objs)
    g = rs.ObjectTopGroup(objs[0].Id)
    for i in rs.ObjectsByGroup(g) if g else []:  # Bordino: the part is outside, its label on the panel has the edge
        m = stored_point(i, BORD_EDGE)
        if m is not None:
            v = m - pt
            v.Unitize()
            return m + v * STEP_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    if any(doc.Layers[o.Attributes.LayerIndex].FullPath == BORDINO for o in objs):  # lies on the neighbour panel
        return u"bordino without its label on the panel in the group (made before 8 Oct 2026) — make it again"
    return pt


def panels(doc):
    """[(curve, P<n>)] — numbered closed curves in Parts::Panels."""
    out = []
    for o in (rs.ObjectsByLayer(PANELS) or []) if rs.IsLayer(PANELS) else []:
        n = rs.GetUserText(o, "Part")
        c = rs.coercecurve(o, -1, False)
        if n and c is not None and c.IsClosed:
            out.append((c, n))
    return out


def panel_at(pt, cands, tol):
    """P<n> of the smallest numbered panel around pt (holes carry the same number), or None.
    ponytail: every panel tested for every part — fine for hundreds."""
    hits = []
    for c, n in cands:
        ok, pl = c.TryGetPlane(tol)
        if ok and c.Contains(pt, pl, tol) == PointContainment.Inside:
            amp = AreaMassProperties.Compute(c)
            hits.append((amp.Area if amp else 0.0, n))
    return min(hits)[1] if hits else None


def main():
    doc = sc.doc
    ids = rs.GetObjects(u"Select parts (window over the parts up and / or the panels with their markup)", preselect=True)
    if not ids:
        return
    tol = doc.ModelAbsoluteTolerance
    cands = panels(doc)
    if not cands:
        print(u"No numbered panels in %s — run Panels first" % PANELS)
        return
    made = 0
    for members in parts(ids):
        objs = [doc.Objects.FindId(i) for i in members]
        objs = [o for o in objs if o is not None]
        if not objs or not is_part(doc, objs) or any(o.Attributes.GetUserString("LayoutOf") for o in objs):
            continue
        if any(doc.Layers[o.Attributes.LayerIndex].FullPath.startswith(SKIP) for o in objs):
            continue
        texts = [o for o in objs if isinstance(o.Geometry, Rhino.Geometry.TextEntity)
                 and not any(o.Attributes.GetUserString(k) for k in MARKUP)]
        name = u", ".join(t.Geometry.PlainText for t in texts) or u"part without a label"
        pt = probe(doc, objs)
        n = panel_at(pt, cands, tol) if not isinstance(pt, type(u"")) else None
        if n is None or not texts:
            why = pt if isinstance(pt, type(u"")) else (u"no label" if n else u"no numbered panel under it")
            print(u"Skipped %s: %s" % (name, why))
            continue
        for t in texts:
            rs.TextObjectText(t.Id, relabel(t.Geometry.PlainText, n))
            rs.SetUserText(t.Id, KEY, n)
        print(u"%s → %s" % (name, n))
        made += 1
    doc.Views.Redraw()
    print(u"Parts with the panel number: %d" % made)


if __name__ == "__main__":
    main()
