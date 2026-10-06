# -*- coding: utf-8 -*-
"""Reinforcement strip mark on an existing label — without a part.
Select labels (ZC / SA / RB…, window selection allowed, on different panels): " R<H>" is appended
to the text (an old R mark is replaced, H=0 — removes it). The panel for each label is the nearest (within NEAR_MM) closed
curve outside Parts:: (or in Parts::Panels) that has an edge (corner to corner, ZipCover.pick_edge): marker circles
without corners are skipped; Seam / ZC strips too (wrong edge). No panel nearby — the label is skipped; edge — the one closest to the label — its length is written to UserText ReinfLen (cm), H — to Reinf.
The order table is made by parts/RList.py. Layer, group and label position are not changed.
"""
import os
import re
import sys

try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
except ImportError:  # for tests/test_reinf_list.py outside Rhino
    Rhino = rs = sc = None

STICKY = "MarkReinf"
NEAR_MM = 200  # a panel within this radius of the label wins over a part (the label sits W/2 from the edge)
MARK = re.compile(r"\s+R[\d.]+$")


def relabel(text, h):
    """'ZC 30 R45', 60 → 'ZC 30 R60'; h=0 — remove the mark."""
    text = MARK.sub(u"", text.rstrip())
    return text + (u" R%g" % h if h else u"")


def ask(go):
    """Label picking with options H / Angle → list of ids or None."""
    h = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 60.0), 0.0, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    go.AddOptionDouble("H", h)
    go.AddOptionDouble("Angle", a)
    while True:
        r = go.GetMultiple(1, 0)
        sc.sticky[STICKY], sc.sticky[STICKY + "_angle"] = h.CurrentValue, a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            go.EnablePreSelect(False, True)
            continue
        return [o.ObjectId for o in go.Objects()] if r == Rhino.Input.GetResult.Object else None


def closed_curves(doc):
    """[(curve, groups, part?)] — all closed curves in the document; part = layer Parts::*, except Parts::Panels."""
    out = []
    for o in doc.Objects.GetObjectList(Rhino.DocObjects.ObjectType.Curve):
        if o.Geometry.IsClosed:
            path = doc.Layers[o.Attributes.LayerIndex].FullPath
            part = path.startswith("Parts::") and not path.startswith("Parts::Panels")
            out.append((o.Geometry, set(o.Attributes.GetGroupList() or []), part))
    return out


HELP = u"""Options:
  H — reinforcement strip height (R<H> in the label); 0 — remove the mark
  Angle — a break larger than this angle = panel corner (the edge under the strip — corner to corner)"""


def main():
    print(HELP)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ZipCover import pick_edge
    tol = sc.doc.ModelAbsoluteTolerance
    to_cm = Rhino.RhinoMath.UnitScale(sc.doc.ModelUnitSystem, Rhino.UnitSystem.Centimeters)
    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt(u"Select labels of edges that get a reinforcement strip")
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Annotation
    ids = ask(go)
    if not ids:
        return
    h, angle = sc.sticky[STICKY], sc.sticky[STICKY + "_angle"]
    cands = closed_curves(sc.doc)
    lim = NEAR_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    made = 0
    for tid in ids:
        p = rs.TextObjectPoint(tid)
        d = lambda c: c.PointAt(c.ClosestPoint(p)[1]).DistanceTo(p)
        groups = set(rs.coercerhinoobject(tid).Attributes.GetGroupList() or [])
        # ponytail: sorting all closed curves for every label — ok for hundreds, not for tens of thousands
        # only panels nearby: a Seam / ZC strip is closed too, but its edge is the wrong one; no panel — skip, not a wrong length
        near = sorted((d(c), k) for k, (c, g, part) in enumerate(cands) if not part and not g & groups and d(c) <= lim)
        res = next((r for r in (pick_edge(cands[k][0], p, angle, tol) for _, k in near) if isinstance(r, tuple)),
                   u"no panel (closed curve with corners outside Parts::, or Parts::Panels) closer than %g mm" % NEAR_MM)
        if not isinstance(res, tuple):
            print(u"Skipped %s: %s" % (rs.TextObjectText(tid), res))
            continue
        cm = res[3].GetLength() * to_cm
        rs.TextObjectText(tid, relabel(rs.TextObjectText(tid), h))
        rs.SetUserText(tid, "Reinf", ("%g" % h) if h else None)
        rs.SetUserText(tid, "ReinfLen", ("%.2f" % cm) if h else None)
        made += 1
        print(u"%s: edge %.1f cm" % (rs.TextObjectText(tid), cm))
    sc.doc.Views.Redraw()
    print(u"Labels marked: %d" % made)


if __name__ == "__main__":
    main()
