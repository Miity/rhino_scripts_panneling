# -*- coding: utf-8 -*-
"""Edges — GhPython component, between Panels and everything after it: the one numbering of the panel edges.

Every later stage (Seams, Notches, ConvertNotches, Zip…) takes its edges from here, so an edge has the same number
everywhere: <panel>.<edge> — 1 top (the edge facing +Y most), then clockwise: 2 right, 3 bottom, 4 left. A panel with
another number of edges is numbered the same way (from the top, clockwise). The edges are found the way the Seams
button and SplitCrvByAngle find them (`Seams.edges` — corner to corner, the turn larger than Angle).

Also a module for the other wrappers: `number_edges` (the rule), `is_side` (left / right edges) and `bottom`.

Inputs:
    Panels   : the `Panels` output of the Panels component (tree, branch {i} = panel P<i+1>: outer curve first), Tree access
    Angle    : degrees, a turn sharper than this is a corner (default 20, the usual setting of SplitCrvByAngle)
    ShowText : bool, False — no labels (default True)
Outputs:
    Edges  : tree, branch {i} = the edges of panel P<i+1> in the order of their numbers; each runs counter-clockwise
    Labels : E<panel>.<edge> inside the panel near the middle of each edge (text geometry)
    Report : edges per panel and their lengths, cm
"""
import os
import sys

ROOT = u"/Users/dmytro/Documents/Projects/Rhino"  # used when the .gh is not saved next to the project


def number_edges(chords):
    """chords — (dx, dy) from start to end of every edge, in counter-clockwise loop order. Returns the loop indices in
    the order of the numbers: the top edge first, then clockwise (top, right, bottom, left)."""
    n = len(chords)

    def up(k):  # Y of the outward direction of edge k: outside is on the right of a counter-clockwise loop
        dx, dy = chords[k]
        length = (dx * dx + dy * dy) ** 0.5
        return -dx / length if length else -2.0

    top = max(range(n), key=up)
    return [(top - j) % n for j in range(n)]  # clockwise = against the loop


def chord(edge):
    return edge.PointAtEnd.X - edge.PointAtStart.X, edge.PointAtEnd.Y - edge.PointAtStart.Y


def is_side(j, edges):
    """edges[j] (numbered order) is a left / right edge: 2 and 4 of a four-sided panel, else the ones facing more
    along X than along Y."""
    if len(edges) == 4:
        return j in (1, 3)
    dx, dy = chord(edges[j])
    return abs(dy) > abs(dx)


def bottom(edges):
    """Index (numbered order) of the bottom edge: 3 of a four-sided panel, else the one facing -Y most."""
    if len(edges) == 4:
        return 2

    def down(j):  # edges run counter-clockwise: a bottom edge heads along +X
        dx, dy = chord(edges[j])
        length = (dx * dx + dy * dy) ** 0.5
        return dx / length if length else -2.0

    return max(range(len(edges)), key=down)


if "ghenv" in globals():
    import Rhino
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path
    from Rhino.Geometry import Plane, TextEntity, Vector3d
    from Rhino.DocObjects import TextHorizontalAlignment, TextVerticalAlignment

    comp = ghenv.Component
    rdoc = Rhino.RhinoDoc.ActiveDoc
    warn = lambda text: comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning, text)

    path = comp.OnPingDocument().FilePath
    root = os.path.dirname(os.path.dirname(path)) if path and os.path.isdir(
        os.path.join(os.path.dirname(os.path.dirname(path)), "scripts")) else ROOT
    for p in (os.path.join(root, "scripts", "pattern"), os.path.join(root, "scripts", "parts"),
              os.path.join(root, "scripts", "markup"), os.path.join(root, "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import Seams as S
    import PatternTextStyles as PTS

    def data(name):
        for prm in comp.Params.Input:
            if prm.NickName == name:
                return prm.VolatileData
        return None

    def first(name, default):
        d = data(name)
        for g in (d.AllData(True) if d else []):
            return g.ScriptVariable()
        return default

    angle = float(first("Angle", 20.0))
    show_text = bool(first("ShowText", True))
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, rdoc.ModelUnitSystem)
    tol = rdoc.ModelAbsoluteTolerance
    style = PTS.ensure_styles(rdoc)[28.0]

    Edges, Labels, Report = DataTree[object](), [], []
    panels = data("Panels")
    if panels is None or panels.PathCount == 0:
        warn(u"No panels: connect the Panels output of the Panels component")
    else:
        for b in range(panels.PathCount):
            n = b + 1  # P<n>, as numbered by the Panels component
            outer = panels.Branches[b][0].ScriptVariable()
            normal = Vector3d.ZAxis
            lp = S.loop(outer, normal)
            if lp is None:
                warn(u"P%d: the outline is not closed" % n)
                continue
            found = S.edges(lp, angle, tol)
            edges = [found[k] for k in number_edges([chord(e) for e in found])]
            for j, e in enumerate(edges):
                Edges.Add(e, GH_Path(b))
                if show_text:
                    side = Vector3d.CrossProduct(e.TangentAt(e.Domain.Mid), normal)  # outside; the label goes inside
                    te = TextEntity()
                    te.PlainText = u"E%d.%d" % (n, j + 1)
                    te.Plane = Plane(S.mid(e) - side * (60.0 * mm), Vector3d.ZAxis)
                    te.DimensionStyleId = style.Id
                    te.TextHorizontalAlignment = TextHorizontalAlignment.Center
                    te.TextVerticalAlignment = TextVerticalAlignment.Middle
                    Labels.append(te)
            Report.append(u"P%d: %d edges, cm %s" % (n, len(edges), u" / ".join(
                u"%.1f" % (e.GetLength() / (10.0 * mm)) for e in edges)))
