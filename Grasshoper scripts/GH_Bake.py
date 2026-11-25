# -*- coding: utf-8 -*-
"""Bake — GhPython component, the last stage: the virtual results of the workflow into the Rhino document, by the
layers of the cutting file.

    CUT (knife, contour)  : the cut lines of the panels (Seams) and of the pocket parts (TubePockets Cuts);
                            a panel without any seam — its outline
    INT (knife, inside)   : knife V notches; holes of the panels
    INK (pen)             : sew lines of panels and pocket parts, centre ticks, zip stops, pocket markup, SquishTo
                            marks, pen notches (Knife = False), the labels P<n>, Z<n>, T<n> (text — run TextToCurves
                            before cutting)

The parts of a sew line lying on the cut line (an edge without seam) are left out, so the pen does not draw where the
knife cuts. No line is drawn twice: an INK curve lying all along (within DUP_MM) on a CUT or INK curve already taken
in the same group is left out (a mark along a panel edge, the same mark twice). Every panel with all that is on it is one group; every pocket part is one group.

Only a press of Bake changes the document (one Undo). A new press first deletes what the previous one made — the
objects are remembered by their ids in the document, so copies you made of them and everything else stay.

The labels are not wired (a script input cannot take text geometry): they are read from the `Labels` output of the
components that feed Panels, ZipMarks and PocketMarks.

Inputs (trees as the stages give them):
    Panels, Seams, Notches, Ticks, ZipMarks, PocketMarks, PocketParts, PocketCuts, Marks2D
    Knife : bool, the same as ConvertNotches (True — the notches go to INT, False — to INK)
    Bake  : button
Outputs:
    Report : what was baked
"""
import os
import sys

ROOT = u"/Users/dmytro/Documents/Projects/Rhino"  # used when the .gh is not saved next to the project
KEY = u"GHBake_squish"  # document string: ids of the objects of the last bake
LABEL_MM = 28.0  # height of the baked labels: the PAT style of the document
DUP_MM = 1.0  # an INK curve this close all along to a line already taken is its duplicate
ON_MM = 0.5  # a piece of a sew line this close to the cut line all along lies under it


if "ghenv" in globals():
    import System
    import System.Drawing
    import Rhino
    import Grasshopper
    from Rhino.Geometry import (Curve, GeometryBase, Plane, Point, Point3d, PointContainment, TextDot, TextEntity,
                                Vector3d)

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

    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, rdoc.ModelUnitSystem)
    tol = rdoc.ModelAbsoluteTolerance

    def data(name):
        for prm in comp.Params.Input:
            if prm.NickName == name:
                return prm.VolatileData
        return None

    def geometry(goo):
        g = goo.ScriptVariable() if goo is not None else None
        if isinstance(g, Point3d):
            return Point(g)
        return g if isinstance(g, GeometryBase) else None

    def items(name):
        d = data(name)
        return [g for g in (geometry(x) for x in (d.AllData(True) if d else [])) if g is not None]

    def labels():
        """the texts P<n>, Z<n>, T<n>: the Labels output of the components feeding Panels, ZipMarks, PocketMarks"""
        out, seen = [], []
        for name in ("Panels", "ZipMarks", "PocketMarks"):
            for prm in comp.Params.Input:
                if prm.NickName != name:
                    continue
                for src in prm.Sources:
                    owner_comp = src.Attributes.GetTopLevel.DocObject
                    if owner_comp.InstanceGuid in seen:
                        continue
                    seen.append(owner_comp.InstanceGuid)
                    for o in owner_comp.Params.Output:
                        if o.NickName == "Labels":
                            out.extend(g for g in (geometry(x) for x in o.VolatileData.AllData(True)) if g is not None)
        return out

    def branches(name):
        """{last index of the path: [geometry]} of a tree input"""
        d, out = data(name), {}
        if d is not None:
            for b in range(d.PathCount):
                got = [g for g in (geometry(x) for x in d.Branches[b]) if g is not None]
                out.setdefault(d.Paths[b].Indices[d.Paths[b].Length - 1], []).extend(got)
        return out

    def distance(crv, p):
        return crv.PointAt(crv.ClosestPoint(p)[1]).DistanceTo(p)

    def off_cut(sew, cut):
        """the sew line without its pieces (corner to corner) that lie on the cut line"""
        lp = S.loop(sew, Vector3d.ZAxis)
        pieces = S.edges(lp, 20.0, tol) if lp is not None else []

        def under(e):
            return all(distance(cut, e.PointAt(t)) <= ON_MM * mm for t in e.DivideByCount(40, True))

        keep = [e for e in pieces if not under(e)]
        if len(keep) == len(pieces):
            return [sew]
        return list(Curve.JoinCurves(keep, 10 * tol)) if keep else []

    def spot(g):
        """a point standing for the object — which panel it belongs to"""
        if isinstance(g, Curve):
            return g.PointAtNormalizedLength(0.5)
        if isinstance(g, Point):
            return g.Location
        if isinstance(g, TextEntity):
            return g.Plane.Origin
        if isinstance(g, TextDot):
            return g.Point
        return g.GetBoundingBox(True).Center

    def away(outline, p):
        """0 inside the closed curve, else the distance to it"""
        return 0.0 if outline.Contains(p, Plane.WorldXY, tol) == PointContainment.Inside else distance(outline, p)

    def plan():
        """[(layer, geometry, group key)] of everything to bake"""
        out = []
        panels, seams = branches("Panels"), branches("Seams")
        outlines = {}
        for i, curves in panels.items():
            outline, holes = curves[0], curves[1:]
            outlines[i] = outline
            group = ("panel", i)
            cut = (seams.get(i) or [None])[0]
            if cut is None:
                out.append(("CUT", outline, group))
            else:
                out.append(("CUT", cut, group))
                out.extend(("INK", c, group) for c in off_cut(outline, cut))
            out.extend(("INT", h, group) for h in holes)
        parts, part_cuts = branches("PocketParts"), branches("PocketCuts")
        pockets = {}  # pocket index -> its sew contour
        for k, geos in parts.items():
            contour = max(geos, key=lambda g: g.GetLength())
            pockets[k] = contour
            group = ("pocket", k)
            cut = (part_cuts.get(k) or [None])[0]
            if cut is None:
                out.append(("CUT", contour, group))
            else:
                out.append(("CUT", cut, group))
                out.extend(("INK", c, group) for c in off_cut(contour, cut))
            out.extend(("INK", g, group) for g in geos if g is not contour)

        def owner(g):
            p = spot(g)
            for k, contour in pockets.items():  # the label of a pocket part lies inside it
                if away(contour, p) == 0.0:
                    return ("pocket", k)
            return ("panel", min(outlines, key=lambda i: away(outlines[i], p))) if outlines else None

        knife_in = items_raw("Knife")
        knife = bool(knife_in[0]) if knife_in else True
        for name, layer in (("Notches", "INT" if knife else "INK"), ("Ticks", "INK"), ("ZipMarks", "INK"),
                            ("PocketMarks", "INK"), ("Marks2D", "INK")):
            out.extend((layer, g, owner(g)) for g in items(name))
        out.extend(("INK", g, owner(g)) for g in labels())
        return no_doubles(out)

    def no_doubles(todo):
        """todo without the INK curves lying all along on a CUT / INK curve before them in the same group (the lines of
        the panels come first, so a mark gives way to them)"""
        out, taken = [], {}
        del doubles[:]
        for layer, g, group in todo:
            if isinstance(g, Curve) and layer in ("CUT", "INK"):
                lines = taken.setdefault(group, [])
                if layer == "INK":
                    pts = [g.PointAt(t) for t in g.DivideByCount(max(40, int(g.GetLength() / (10.0 * mm))), True)]
                    if any(all(distance(c, p) <= DUP_MM * mm for p in pts) for c in lines):
                        doubles.append(g)
                        continue
                lines.append(g)
            out.append((layer, g, group))
        return out

    def items_raw(name):
        d = data(name)
        return [x.ScriptVariable() for x in (d.AllData(True) if d else [])]

    def add(geo, attrs, style):
        """into the document; a text is made anew with the document style — one passed through Grasshopper keeps its
        height only as a local override and would be baked 1 mm high"""
        if not isinstance(geo, TextEntity):
            return rdoc.Objects.Add(geo, attrs)
        te = TextEntity()
        te.Plane = geo.Plane
        te.DimensionStyleId = style.Id
        te.PlainText = geo.PlainText
        te.TextHorizontalAlignment = geo.TextHorizontalAlignment
        te.TextVerticalAlignment = geo.TextVerticalAlignment
        return rdoc.Objects.AddText(te, attrs)

    def layer_index(name):
        i = rdoc.Layers.FindByFullPath(name, -1)
        if i < 0:
            colour = {"CUT": System.Drawing.Color.Red, "INT": System.Drawing.Color.Orange,
                      "INK": System.Drawing.Color.Blue}[name]
            i = rdoc.Layers.Add(name, colour)
        return i

    def remove_previous():
        gone, stuck, groups = 0, 0, set()
        for text in (rdoc.Strings.GetValue(KEY) or u"").split(u","):
            if not text:
                continue
            obj = rdoc.Objects.FindId(System.Guid(text))
            if obj is None or obj.IsDeleted:
                continue
            groups.update(obj.Attributes.GetGroupList() or [])
            if rdoc.Objects.Delete(obj.Id, True):
                gone += 1
            else:
                stuck += 1
        for g in groups:
            if not rdoc.Groups.GroupMembers(g):
                rdoc.Groups.Delete(g)
        return gone, stuck

    Report, doubles = [], []
    press = any(bool(v) for v in items_raw("Bake"))
    if not press:
        n = len([t for t in (rdoc.Strings.GetValue(KEY) or u"").split(u",") if t and
                 rdoc.Objects.FindId(System.Guid(t)) is not None])
        Report.append(u"Press Bake to put the results into the document (%d baked objects there now)" % n)
    elif not branches("Panels"):
        warn(u"No panels: switch Run on and connect the stages")
    else:
        todo = plan()  # worked out before anything is deleted
        style = PTS.ensure_styles(rdoc)[LABEL_MM]
        undo = rdoc.BeginUndoRecord(u"GH Bake")
        try:
            gone, stuck = remove_previous()
            made, groups, count, failed = [], {}, {}, 0
            for layer, geo, group in todo:
                attrs = rdoc.CreateDefaultAttributes()
                attrs.LayerIndex = layer_index(layer)
                if group is not None:
                    if group not in groups:
                        groups[group] = rdoc.Groups.Add()
                    attrs.AddToGroup(groups[group])
                oid = add(geo, attrs, style)
                if oid == System.Guid.Empty:
                    failed += 1
                    continue
                made.append(str(oid))
                count[layer] = count.get(layer, 0) + 1
            rdoc.Strings.SetString(KEY, u",".join(made))
        finally:
            rdoc.EndUndoRecord(undo)
        rdoc.Views.Redraw()
        if failed:
            warn(u"%d objects could not be added" % failed)
        if stuck:
            warn(u"%d objects of the previous bake could not be deleted (locked or hidden layer?)" % stuck)
        Report.append(u"Baked %d objects: %s" % (len(made), u", ".join(u"%s %d" % (k, count[k]) for k in sorted(count))))
        if doubles:
            Report.append(u"Left out as doubles (lying on another line): %d" % len(doubles))
        Report.append(u"Groups: %d panels, %d pocket parts; previous bake removed: %d" % (
            len([g for g in groups if g[0] == "panel"]), len([g for g in groups if g[0] == "pocket"]), gone))
