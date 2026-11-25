# -*- coding: utf-8 -*-
"""TubePockets — GhPython component: tube pockets on chosen edges, markup on the panel and the full part up.

A thin wrapper (scripts/parts/TubePockets.py stays as it is): the geometry is its `pocket` (a segment of the edge of
width W centred on it, offset by H into the panel, the top shorter by Trim at each end, no seam allowance), the label
stands as the button puts it. As with the button's Layout=Yes: on the panel only the ends and the pocket top (without
the edge) and the label T<n>; the full part (contour + centre notch + label) Up above along Y. Virtual — nothing is
added to the Rhino document.

Seam allowance of the full part (the button's Seam step): the bottom of the pocket gets the same seam as its panel edge
has in the Seams component (read off the panel's cut line, `Seams.measured`); the two ends get SeamSides (5 cm); the
top — the side opposite the panel edge — gets none. The cut
line is built as the Seams button builds it (`Seams.build`, corners Extend, cleaned for the knife).

Edges and their numbers come from the Edges component. Press Build — one slider per edge is made below the component
(a column per panel, T2.1 = pocket on edge 2.1), grouped (`Pocket widths`) and wired to Widths in that order. Its value
is the pocket width W in cm: 0 — no pocket, all the way right (the edge length) — the whole edge. Every Build sets all
to 0; an old set is replaced. Pockets are numbered T1, T2… by panel and edge.

Inputs:
    Edges  : the `Edges` output of the Edges component (tree, branch {i} = panel P<i+1>), Tree access
    Seams  : the `Seams` output of the Seams component (cut lines of the panels), Tree access
    SeamSides : cm, the seam of the two ends of the full part (default 5)
    H      : cm, pocket height (default 13)
    Trim   : cm, the top shorter by this at each end (default 5)
    Notch  : bool, centre mark of the pocket (default True)
    Rigid  : bool, the top is a rigid copy of the edge (default False)
    Up     : mm, how far up the full parts go (optional, default 10000, as the part buttons)
    Build  : button, makes the sliders
    Widths : cm, one per edge in the order T1.1, T1.2… T2.1… (the sliders), List access
Outputs:
    Marks  : tree, branch {k} = the markup of pocket T<k+1> on its panel
    Parts  : tree, branch {k} = the full part of pocket T<k+1>: contour, centre mark
    Cuts   : tree, branch {k} = the cut line of the full part
    Labels : T<n> on the panel and on the full part (text geometry)
    Report : pockets and their sizes, problems
"""
import os
import sys

ROOT = u"/Users/dmytro/Documents/Projects/Rhino"  # used when the .gh is not saved next to the project


if "ghenv" in globals():
    import System
    import Rhino
    import Grasshopper
    from Grasshopper import DataTree
    from Grasshopper.Kernel.Data import GH_Path
    from Rhino.Geometry import Curve, TextEntity, Transform, Vector3d
    from Rhino.DocObjects import TextHorizontalAlignment, TextVerticalAlignment

    comp = ghenv.Component
    rdoc = Rhino.RhinoDoc.ActiveDoc
    warn = lambda text: comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning, text)

    path = comp.OnPingDocument().FilePath
    root = os.path.dirname(os.path.dirname(path)) if path and os.path.isdir(
        os.path.join(os.path.dirname(os.path.dirname(path)), "scripts")) else ROOT
    for p in (os.path.join(root, "scripts", "pattern"), os.path.join(root, "scripts", "parts"), os.path.join(root, "scripts", "markup"),
              os.path.join(root, "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import TubePockets as T
    import Seams as S

    def data(name):
        for prm in comp.Params.Input:
            if prm.NickName == name:
                return prm.VolatileData
        return None

    def values(name):
        d = data(name)
        return [g.ScriptVariable() for g in (d.AllData(True) if d else [])]

    def first(name, default):
        v = values(name)
        return v[0] if v else default

    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, rdoc.ModelUnitSystem)
    cm = 10.0 * mm
    tol = rdoc.ModelAbsoluteTolerance
    h = float(first("H", 13.0)) * cm
    trim = float(first("Trim", 5.0)) * cm
    notch = bool(first("Notch", True))
    rigid = bool(first("Rigid", False))
    ends_seam = float(first("SeamSides", 5.0)) * cm  # the two ends of the full part; the top has none
    up = Vector3d(0, float(first("Up", T.UP)) * mm, 0)
    widths = [float(v) for v in values("Widths")]

    Marks, Parts, Cuts, Labels, Report = DataTree[object](), DataTree[object](), DataTree[object](), [], []
    panel_cuts = {}  # panel index -> its cut line (Seams component)
    seams_in = data("Seams")
    if seams_in is not None:
        for b in range(seams_in.PathCount):
            for g in seams_in.Branches[b]:
                panel_cuts[seams_in.Paths[b].Indices[seams_in.Paths[b].Length - 1]] = g.ScriptVariable()
    found = []  # (name, panel, edge index, edge length cm) of every edge — for the Build button
    taken = number = 0
    tree = data("Edges")
    if tree is None or tree.PathCount == 0:
        warn(u"No edges: connect the Edges output of the Edges component")
    else:
        style = T.label_style(rdoc, T.STICKY)
        normal = Vector3d.ZAxis
        for b in range(tree.PathCount):
            index = tree.Paths[b].Indices[tree.Paths[b].Length - 1]
            n = index + 1  # P<n>
            edges = [g.ScriptVariable() for g in tree.Branches[b]]
            outline = Curve.JoinCurves(edges, 10 * tol)  # the panel is its edges joined back
            outline = outline[0] if len(outline) == 1 and outline[0].IsClosed else None
            if outline is None:
                warn(u"P%d: the edges do not close into one outline" % n)
            for j, edge in enumerate(edges):
                length = edge.GetLength() / cm
                found.append((u"T%d.%d" % (n, j + 1), n, j, length))
                w = widths[taken] if taken < len(widths) else 0.0
                taken += 1
                if w <= 0 or outline is None:
                    continue
                where = u"%d.%d" % (n, j + 1)
                whole = w >= length - 0.1  # the slider all the way right
                toward = T.inward(outline, edge, normal)
                res = T.pocket(edge, toward, 0.0 if whole else w * cm, h, trim, notch, normal, tol, rigid)
                if not isinstance(res, tuple):
                    warn(u"Pocket on %s: %s" % (where, res))
                    continue
                contour, seg, mark, markup = res
                name = T.label(number + 1, h)
                top = T.pocket_side(seg, toward, h, normal, tol, rigid)
                te = TextEntity.Create(name, T.label_frame(seg, top, normal), style, False, 0, 0)
                te.TextHorizontalAlignment = TextHorizontalAlignment.Center
                te.TextVerticalAlignment = TextVerticalAlignment.Middle
                branch = GH_Path(number)
                Marks.Add(markup, branch)
                Labels.append(te)
                for geo in [contour] + ([mark] if mark else []):
                    g = geo.Duplicate()
                    g.Transform(Transform.Translation(up))
                    Parts.Add(g, branch)
                panel_cut = panel_cuts.get(index)
                seam = S.measured(edge, panel_cut, normal, tol) if panel_cut is not None else 0.0
                if max(seam, ends_seam) > tol:
                    lp = S.loop(contour, normal)
                    es = S.edges(lp, 20.0, tol) if lp is not None else []
                    corners = (seg.PointAtStart, seg.PointAtEnd)

                    def width(e):  # bottom (on the segment of the panel edge) / an end (starts at its corner) / the top
                        if max(seg.PointAt(seg.ClosestPoint(q)[1]).DistanceTo(q) for q in
                               (e.PointAtStart, S.mid(e), e.PointAtEnd)) <= 100 * tol:
                            return seam
                        touches = min(q.DistanceTo(c) for q in (e.PointAtStart, e.PointAtEnd) for c in corners)
                        return ends_seam if touches <= 100 * tol else 0.0

                    own = [width(e) for e in es]
                    cut = S.build(es, own, ["Extend"] * len(es), normal, tol) if max(own or [0]) > 0 else None
                    if cut is None:
                        warn(u"%s: the cut line of the full part did not close" % name)
                    else:
                        cut = S.clean(cut, S.micro(rdoc))
                        cut.Transform(Transform.Translation(up))
                        Cuts.Add(cut, branch)
                above = te.Duplicate()
                above.Transform(Transform.Translation(up))
                Labels.append(above)
                number += 1
                Report.append(u"%s: E%s, W %s, H %g, Trim %g cm, seam bottom %g / ends %g / top 0 cm" % (
                    name, where, u"whole edge %.1f" % length if whole else u"%.1f" % w, h / cm, trim / cm,
                    round(seam / cm, 2), ends_seam / cm))
        if number and not panel_cuts:
            warn(u"Connect Seams (Seams component): the full parts have no seam allowance")
        if not number:
            Report.append(u"No pockets: give an edge a width (Build makes the sliders)")

        if first("Build", False) is True:
            from System.Drawing import PointF, Color
            from Grasshopper.Kernel import GH_Document
            from Grasshopper.Kernel.Special import GH_NumberSlider, GH_Group
            doc = comp.OnPingDocument()
            wparam = [q for q in comp.Params.Input if q.NickName == "Widths"][0]
            TAG = u"PocketEdge"

            def make(d):
                gone = set()
                for o in list(d.Objects):
                    if isinstance(o, GH_NumberSlider) and (o.Description or u"").startswith(TAG):
                        gone.add(o.InstanceGuid)
                        d.RemoveObject(o, False)
                for o in list(d.Objects):  # the groups of the old sliders go with them
                    if isinstance(o, GH_Group) and (o.Description == TAG or gone.intersection(o.ObjectIDs)):
                        d.RemoveObject(o, False)
                wparam.RemoveAllSources()
                x0, y0 = comp.Attributes.Pivot.X - 350, comp.Attributes.Pivot.Y + 180  # below, a column per panel
                group = GH_Group()
                group.NickName = u"Pocket widths"
                group.Description = TAG
                group.Colour = Color.FromArgb(120, 200, 160, 230)
                for name, n, j, length in found:
                    sl = GH_NumberSlider()
                    sl.CreateAttributes()
                    sl.Attributes.Pivot = PointF(x0 + (n - 1) * 230, y0 + j * 26)
                    sl.Slider.Minimum = System.Decimal(0)
                    sl.Slider.DecimalPlaces = 1
                    sl.Slider.Maximum = System.Decimal(round(length, 1))
                    sl.SetSliderValue(System.Decimal(0))
                    sl.NickName = name
                    sl.Description = u"%s %s: pocket width cm on edge E%d.%d (%.1f cm); 0 — none, full right — whole edge" % (
                        TAG, name, n, j + 1, length)
                    d.AddObject(sl, False)
                    wparam.AddSource(sl)
                    group.AddObject(sl.InstanceGuid)
                d.AddObject(group, False)
                group.ExpireCaches()
                comp.ExpireSolution(False)

            doc.ScheduleSolution(5, GH_Document.GH_ScheduleDelegate(make))
        if widths and len(widths) != taken:
            warn(u"Widths has %d values, the panels have %d edges (press Build)" % (len(widths), taken))
