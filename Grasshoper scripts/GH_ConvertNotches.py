# -*- coding: utf-8 -*-
"""ConvertNotches — GhPython component, stage 5 of the workflow: notch points -> real notches on the cut line.

A thin wrapper (scripts/pattern/ConvertNotches.py stays as it is): the shapes are its `spec` / `shapes` (knife V for
the circular blade, or the pen slit / V), the seam width of an edge is read off its cut line by `Seams.measured`.
As the button: each notch goes square to its edge, onto the cut line (on the sew line if the edge has no seam).
Virtual: nothing is added to the Rhino document (the layers INT / INK are given when the result is baked, later).

Knife = True (default) — the knife V with the plotter standard (Depth 2, Overcut 1, Move 3 mm); False — pen marks
with the button's defaults (Slit, In, Depth 5 mm). The other inputs are optional, unwired — those values.

Inputs:
    Points    : the `Points` output of the Notches component (tree, branch {i} = panel P<i+1>), Tree access
    Edges     : the `Edges` output of the Edges component, Tree access
    Seams     : the `Seams` output of the Seams component (cut lines), Tree access
    Knife     : bool, True — knife V, False — pen mark (default True)
    Depth     : mm (default: knife 2, pen 5)
    Overcut   : mm, knife (default 1)
    Move      : mm, knife (default 3)
    Style     : pen: Slit / V (default Slit)
    Width     : mm, pen V opening (default 6)
    Placement : pen: In / Out / Center (default In)
Outputs:
    Notches : tree, branch {i} = the notch lines of panel P<i+1>
    Report  : what was made
"""
import os
import sys

ROOT = u"/Users/dmytro/Documents/Projects/Rhino"  # used when the .gh is not saved next to the project


if "ghenv" in globals():
    import Rhino
    import Grasshopper
    from Grasshopper import DataTree
    from Rhino.Geometry import Vector3d

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
    import ConvertNotches as C
    import Seams as S

    def data(name):
        for prm in comp.Params.Input:
            if prm.NickName == name:
                return prm.VolatileData
        return None

    def first(name, default=None):
        d = data(name)
        for g in (d.AllData(True) if d else []):
            return g.ScriptVariable()
        return default

    def branches(name):
        """{panel index: [geometry]} of a tree input; the panel is the last index of the path"""
        d, out = data(name), {}
        if d is not None:
            for b in range(d.PathCount):
                out[d.Paths[b].Indices[d.Paths[b].Length - 1]] = [g.ScriptVariable() for g in d.Branches[b]]
        return out

    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, rdoc.ModelUnitSystem)
    tol = rdoc.ModelAbsoluteTolerance
    knife = bool(first("Knife", True))
    o = dict(C.DEFAULTS)
    o.update(C.STANDARD)  # the plotter standard of the knife notches
    o["tool"] = C.TOOLS.index("Cut" if knife else "Mark")
    for name, key in (("Depth", "kdepth" if knife else "depth"), ("Overcut", "over"), ("Move", "move"),
                      ("Width", "width")):
        if first(name) is not None:
            o[key] = float(first(name))
    for name, key, choices in (("Style", "style", C.STYLES), ("Placement", "place", C.PLACES)):
        v = first(name)
        if v is not None:
            match = [i for i, c in enumerate(choices) if c.lower() == str(v).strip().lower()]
            if match:
                o[key] = match[0]
            else:
                warn(u"%s: %s — one of %s" % (name, v, u" / ".join(choices)))
    for key in C.MM_KEYS:
        o[key] *= mm
    spec = C.spec(o)

    Notches, Report = DataTree[object](), []
    points, edges, cuts = branches("Points"), branches("Edges"), branches("Seams")
    if not points or not edges:
        warn(u"Connect Points (Notches), Edges (Edges component) and Seams (Seams component)")
    else:
        made, narrow, bare = 0, [], []
        for index in sorted(points):
            es = edges.get(index) or []
            cut = (cuts.get(index) or [None])[0]
            if not es:
                continue
            normal = Vector3d.ZAxis
            widths = [S.measured(e, cut, normal, tol) if cut is not None else 0.0 for e in es]
            if cut is None:
                bare.append(index + 1)
            for pt in points[index]:
                q = getattr(pt, "Location", pt)
                k = min(range(len(es)), key=lambda i: es[i].PointAt(es[i].ClosestPoint(q)[1]).DistanceTo(q))
                e = es[k]
                out = Vector3d.CrossProduct(e.TangentAt(e.ClosestPoint(q)[1]), normal)  # outside: edges run ccw
                out.Unitize()
                for curve in C.shapes(q + out * widths[k], out, normal, spec):
                    Notches.Add(curve, Grasshopper.Kernel.Data.GH_Path(index))
                made += 1
                if widths[k] > tol:
                    narrow.append(widths[k])
        if bare:
            warn(u"No cut line for %s: the notches are on the sew line" % u", ".join(u"P%d" % n for n in bare))
        if spec["tool"] == "Cut":
            Report.append(u"Knife V (INT): width %g, depth %g mm; each leg %g along it from the edge, moves %g" % (
                round(spec["width"] / mm, 2), spec["depth"] / mm, spec["over"] / mm, round(spec["move"] / mm, 2)))
        else:
            Report.append(u"Pen mark (INK): %s %s, depth %g mm" % (spec["style"], spec["place"], spec["depth"] / mm))
        inward = {"In": spec["depth"], "Center": spec["depth"] / 2.0}.get(spec["place"], 0.0)
        if narrow and inward >= min(narrow) - tol:
            warn(u"Depth reaches the sew line (the narrowest seam with notches is %g mm)" % round(min(narrow) / mm, 1))
        Report.append(u"Notches: %d" % made)
