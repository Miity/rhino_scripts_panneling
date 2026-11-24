# -*- coding: utf-8 -*-
"""Seams — GhPython component, stage 3 of the workflow: panels -> seam allowance (cut line) around each panel.

A thin wrapper (scripts/pattern/Seams.py stays as it is): the edges are found the way the button and SplitCrvByAngle
find them (`Seams.edges` — corner to corner, the turn larger than Angle), the cut line is built by `Seams.build`
and cleaned for the plotter knife (`JoinCorner.clean`) — the same code, without the document. Virtual: nothing is
added to the Rhino document. Corners are Extend (the button's default).

Every edge gets Width. Other widths — by sliders: press the Build button — one Number Slider per edge is made next to
the component (a column per panel, named S1.1, S1.2… = seam of panel, edge; the tooltip has the edge length; the old ones are
replaced, their values kept by name) and wired to Widths in that order. The Labels print `S2.3  1 cm` near the middle of
edge 3 of panel P2; 0 — no seam on that edge; edges without a value keep Width. Press Build again after the panels
change (another model, Angle). Or by text — the Overrides list: "P2.3=3" — panel P2, edge 3, 3 cm; "P2=3" — every edge
of P2; several items or entries separated by comma / semicolon / new line; the text wins over the slider. Edge numbers
follow the loop of the panel (counter-clockwise, from where its curve starts), so they change when the pieces are laid
out in another way.

Inputs:
    Panels    : the `Panels` output of stage 2 (tree, branch {i} = panel P<i+1>: outer curve first), Tree access
    Angle     : degrees, a turn sharper than this is a corner (default 20, the usual setting of SplitCrvByAngle)
    Width     : cm, the seam of every edge (default 1)
    Build     : button, makes the sliders (see above)
    Widths    : cm, one value per edge in the order S1.1, S1.2… S2.1… (the sliders), List access
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
ENTRY = re.compile(r"^\s*[PS]?(\d+)(?:\s*\.\s*(\d+))?\s*=\s*(\d+(?:[.,]\d+)?)\s*(?:cm)?\s*$", re.I)


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
    import System
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
    slid = [float(g.ScriptVariable()) for g in (data("Widths").AllData(True) if data("Widths") else [])]
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
    taken = 0  # sliders used so far, in the order of the edges
    found = []  # (name, edge length) of every edge — for the Build button
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
                w = per_edge.get((n, k + 1), per_panel.get(n, slid[taken] if taken < len(slid) else width_cm))
                taken += 1
                used.add((n, k + 1))
                widths.append(w * cm)
            path_n = GH_Path(b)
            for k, e in enumerate(es):
                Edges.Add(e, path_n)
                found.append((u"S%d.%d" % (n, k + 1), e.GetLength() / mm, n, k))
                t = e.Domain.Mid
                side = Vector3d.CrossProduct(e.TangentAt(t), normal)  # outside is on the right; the label goes inside
                te = TextEntity()
                te.PlainText = u"S%d.%d  %g cm" % (n, k + 1, widths[k] / cm)
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

        if first("Build", False) is True:
            from System.Drawing import PointF
            from Grasshopper.Kernel import GH_Document
            from Grasshopper.Kernel.Special import GH_NumberSlider
            doc = comp.OnPingDocument()
            wparam = [q for q in comp.Params.Input if q.NickName == "Widths"][0]
            TAG = u"SeamsEdge"

            def make(d):
                kept = {}
                for o in list(d.Objects):
                    if isinstance(o, GH_NumberSlider) and (o.Description or u"").startswith(TAG):
                        kept[u"S" + o.NickName[1:]] = o.CurrentValue  # P1.1 of an older build is S1.1 now
                        d.RemoveObject(o, False)
                wparam.RemoveAllSources()
                x0, y0 = comp.Attributes.Pivot.X + 330, comp.Attributes.Pivot.Y - 120
                for name, length, n, k in found:
                    sl = GH_NumberSlider()
                    sl.CreateAttributes()
                    sl.Attributes.Pivot = PointF(x0 + (n - 1) * 230, y0 + k * 26)
                    sl.Slider.Minimum = System.Decimal(0)
                    sl.Slider.Maximum = System.Decimal(10)
                    sl.Slider.DecimalPlaces = 1
                    sl.SetSliderValue(kept.get(name, System.Decimal(width_cm)))
                    sl.NickName = name
                    sl.Description = u"%s edge %s, length %.0f mm; cm, 0 — no seam" % (TAG, name, length)
                    d.AddObject(sl, False)
                    wparam.AddSource(sl)
                comp.ExpireSolution(False)

            doc.ScheduleSolution(5, GH_Document.GH_ScheduleDelegate(make))
        if slid and len(slid) != taken:
            warn(u"Widths has %d values, the panels have %d edges (Count of the Gene Pool)" % (len(slid), taken))
        stray = [u"P%d.%d" % k for k in per_edge if k not in used] + [
            u"P%d" % k for k in per_panel if k > panels.PathCount]
        if stray:
            warn(u"Overrides for edges / panels that do not exist: %s" % u", ".join(stray))
