# -*- coding: utf-8 -*-
"""Seams — GhPython component, stage 3 of the workflow: panels -> seam allowance (cut line) around each panel.

A thin wrapper (scripts/pattern/Seams.py stays as it is): the edges are found the way the button and SplitCrvByAngle
find them (`Seams.edges` — corner to corner, the turn larger than Angle), the cut line is built by `Seams.build`
and cleaned for the plotter knife (`JoinCorner.clean`) — the same code, without the document. Virtual: nothing is
added to the Rhino document. Corners are Extend (the button's default).

Every edge gets Width; other widths — the Overrides list: "P2.3=3" — panel P2, edge 3, 3 cm; "P2=3" — every edge of
P2; several items or several entries in one item, separated by comma / semicolon / new line. Edge numbers are those
printed on the Labels (`3  1 cm` near the middle of edge 3 of the panel); they follow the loop of the panel
(counter-clockwise, from where its curve starts), so they change when the pieces are laid out in another way.

Inputs:
    Panels    : the `Panels` output of stage 2 (tree, branch {i} = panel P<i+1>: outer curve first), Tree access
    Angle     : degrees, a turn sharper than this is a corner (default 20, the usual setting of SplitCrvByAngle)
    Width     : cm, the seam of every edge (default 1)
    Overrides : text, widths of single edges / panels, cm (see above)
Outputs:
    Seams  : tree, branch {i} = the closed cut line of panel P<i+1>
    Edges  : tree, branch {i} = the edges of panel P<i+1>, numbered 1… in the order of Labels
    Labels : the edge number and its width near the middle of each edge (text geometry)
    Report : edges per panel, widths, problems
"""
import os
import re
import sys

ROOT = u"/Users/dmytro/Documents/Projects/Rhino"  # used when the .gh is not saved next to the project
ENTRY = re.compile(r"^\s*P?(\d+)(?:\s*\.\s*(\d+))?\s*=\s*(\d+(?:[.,]\d+)?)\s*(?:cm)?\s*$", re.I)


def parse(texts):
    """['P2.3=3, P4=5'] -> ({(panel, edge): cm}, {panel: cm}, [entries that are not understood]); 1-based numbers."""
    edge, whole, bad = {}, {}, []
    for t in texts:
        for part in re.split(r"[,;\n]+", t or u""):
            if not part.strip():
                continue
            m = ENTRY.match(part)
            if not m:
                bad.append(part.strip())
            elif m.group(2):
                edge[(int(m.group(1)), int(m.group(2)))] = float(m.group(3).replace(",", "."))
            else:
                whole[int(m.group(1))] = float(m.group(3).replace(",", "."))
    return edge, whole, bad


if "ghenv" in globals():
    import Rhino
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path
    from Rhino.Geometry import Curve, Plane, TextEntity, Vector3d
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
    width_cm = float(first("Width", 1.0))
    overrides = [g.ScriptVariable() for g in (data("Overrides").AllData(True) if data("Overrides") else [])]
    per_edge, per_panel, bad = parse([unicode(t) if sys.version_info[0] < 3 else str(t) for t in overrides])
    if bad:
        warn(u"Overrides not understood: %s (use P2.3=3 or P2=3, cm)" % u", ".join(bad))

    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, rdoc.ModelUnitSystem)
    cm = 10.0 * mm
    tol = rdoc.ModelAbsoluteTolerance
    style = PTS.ensure_styles(rdoc)[28.0]

    Seams, Edges, Labels, Report = DataTree[object](), DataTree[object](), [], []
    panels = data("Panels")
    used = set()
    if panels is None or panels.PathCount == 0:
        warn(u"No panels: connect the Panels output of stage 2")
    else:
        for b in range(panels.PathCount):
            n = b + 1  # P<n>, as numbered by stage 2
            outer = panels.Branches[b][0].ScriptVariable()
            plane_ok, plane = outer.TryGetPlane(tol)
            normal = plane.ZAxis if plane_ok else Vector3d.ZAxis
            if normal * Vector3d.ZAxis < 0:
                normal = -normal
            lp = S.loop(outer, normal)
            if lp is None:
                warn(u"P%d: the outline is not closed" % n)
                continue
            es = S.edges(lp, angle, tol)
            widths = []
            for k in range(len(es)):
                w = per_edge.get((n, k + 1), per_panel.get(n, width_cm))
                used.add((n, k + 1))
                widths.append(w * cm)
            path_n = GH_Path(b)
            for k, e in enumerate(es):
                Edges.Add(e, path_n)
                t = e.Domain.Mid
                side = Vector3d.CrossProduct(e.TangentAt(t), normal)  # outside is on the right; the label goes inside
                te = TextEntity()
                te.PlainText = u"%d  %g cm" % (k + 1, widths[k] / cm)
                te.Plane = Plane(S.mid(e) - side * (60.0 * mm), Vector3d.ZAxis)
                te.DimensionStyleId = style.Id
                te.TextHorizontalAlignment = TextHorizontalAlignment.Center
                te.TextVerticalAlignment = TextVerticalAlignment.Middle
                Labels.append(te)
            if max(widths) <= tol:
                Report.append(u"P%d: %d edges, no seam" % (n, len(es)))
                continue
            cut = S.build(es, widths, ["Extend"] * len(es), normal, tol)
            if cut is None:
                warn(u"P%d: the cut line did not close (an edge too short for its seam?)" % n)
                Report.append(u"P%d: %d edges — cut line failed" % (n, len(es)))
                continue
            Seams.Add(S.clean(cut, S.micro(rdoc)), path_n)
            Report.append(u"P%d: %d edges, widths cm %s" % (n, len(es), u" ".join(u"%g" % (w / cm) for w in widths)))
        stray = [u"P%d.%d" % k for k in per_edge if k not in used] + [
            u"P%d" % k for k in per_panel if k > panels.PathCount]
        if stray:
            warn(u"Overrides for edges / panels that do not exist: %s" % u", ".join(stray))
