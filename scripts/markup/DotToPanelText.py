# -*- coding: utf-8 -*-
# Selected TextDots -> text inside the nearest panel (closed curve), in its top-right corner.
# The text style is picked from a list at start. Layer INK, the dot is deleted.
# Compatibility: IronPython 2.7 / CPython 3 (Rhino 8).
import os
import sys
import System
import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import PatternTextStyles as pts

LAYER = "INK"


def spans(poly, y):
    """Intervals [x0, x1] where the horizontal line y is inside the polygon."""
    xs = []
    for i in range(len(poly) - 1):
        a, b = poly[i], poly[i + 1]
        if (a.Y <= y) != (b.Y <= y):
            xs.append(a.X + (y - a.Y) * (b.X - a.X) / (b.Y - a.Y))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def cut(A, B):
    out = []
    for a0, a1 in A:
        for b0, b1 in B:
            lo, hi = max(a0, b0), min(a1, b1)
            if lo < hi:
                out.append((lo, hi))
    return out


def find_spot(poly, tx, ty, width, hgt, row, down, ymin, ymax):
    """A width x hgt rectangle inside the polygon, closest to the desired top-right corner (tx, ty).
    Bands go from ty into the panel (down — downwards, otherwise upwards); in the first band with room,
    the x closest to tx is taken. Returns (x_right, y_top) or None.
    Polygon edges are linear between vertices, so checking the band edges and vertex levels inside it is enough — exact, no brute force."""
    ys = sorted(set(p.Y for p in poly))
    y = min(max(ty, ymin + hgt), ymax)
    while ymin + hgt <= y <= ymax:
        levels = [y, y - hgt] + [v for v in ys if y - hgt < v < y]
        free = None
        for lv in levels:
            eps = 1e-6 * (1 if lv < y else -1)  # not exactly on the vertex
            free = spans(poly, lv + eps) if free is None else cut(free, spans(poly, lv + eps))
            if not free:
                break
        xs = [min(max(tx, x0 + width), x1) for x0, x1 in (free or []) if x1 - x0 >= width]
        if xs:
            return min(xs, key=lambda x: abs(x - tx)), y
        y += -row if down else row
    return None


STICKY = "DotToPanelText.style"


def pick_style(doc, current):
    names = sorted(ds.Name for ds in doc.DimStyles if not ds.IsDeleted and not ds.IsChild)
    return rs.ListBox(names, u"Text style", u"Dot -> text", current) or current


def get_one(doc, name, geom, prompt, closed=False):
    """Pick one object with the Style option. Returns (ObjRef or None, style name)."""
    while True:
        go = Rhino.Input.Custom.GetObject()
        go.GeometryFilter = geom
        if closed:
            go.GeometryAttributeFilter = Rhino.Input.Custom.GeometryAttributeFilter.ClosedCurve
        go.SetCommandPrompt(u"%s (style: %s)" % (prompt, name))
        opt = go.AddOption("Style")
        res = go.Get()
        if res == Rhino.Input.GetResult.Option and go.OptionIndex() == opt:
            name = pick_style(doc, name)
            sc.sticky[STICKY] = name
            continue
        if res != Rhino.Input.GetResult.Object:
            return None, name
        return go.Object(0), name


def get_corner(crv):
    """Click near the panel corner where the text goes. Enter — top-right corner."""
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Click near a panel corner for the text (Enter — top right)")
    gp.AcceptNothing(True)
    res = gp.Get()
    if res == Rhino.Input.GetResult.Point:
        return gp.Point()
    if res == Rhino.Input.GetResult.Nothing:
        return crv.GetBoundingBox(True).Max
    return None


def place_text(doc, text, crv, click, style, attr, tol):
    """Text inside panel crv in the corner closest to click. Returns id or None (does not fit)."""
    h = style.TextHeight * style.DimensionScale
    pb = crv.GetBoundingBox(True)
    c = pb.Center
    right, top = click.X >= c.X, click.Y >= c.Y  # which corner: by the click position relative to the panel centre
    A = Rhino.DocObjects
    te = rg.TextEntity()
    te.PlainText = text
    te.Plane = rg.Plane(rg.Point3d(click.X, click.Y, pb.Min.Z), rg.Vector3d.ZAxis)
    te.DimensionStyleId = style.Id
    te.TextHorizontalAlignment = A.TextHorizontalAlignment.Right if right else A.TextHorizontalAlignment.Left
    te.TextVerticalAlignment = A.TextVerticalAlignment.Top if top else A.TextVerticalAlignment.Bottom
    tid = doc.Objects.AddText(te, attr)
    if tid == System.Guid.Empty:
        return None
    tb = doc.Objects.FindId(tid).Geometry.GetBoundingBox(True)
    w, hg = tb.Max.X - tb.Min.X + 2 * h, tb.Max.Y - tb.Min.Y + 2 * h  # text + margin h on all sides
    pc = crv.ToPolyline(tol * 10, 0.05, 0, 0)  # arc -> polyline with 10*tol accuracy
    ok, poly = pc.TryGetPolyline() if pc else (False, None)
    spot = find_spot(poly, click.X if right else click.X + w, click.Y if top else click.Y + hg,
                     w, hg, h / 4.0, top, pb.Min.Y, pb.Max.Y) if ok else None
    if spot:
        v = rg.Vector3d(spot[0] - h - tb.Max.X, spot[1] - h - tb.Max.Y, 0)
        return doc.Objects.Transform(tid, rg.Transform.Translation(v), True)
    doc.Objects.Delete(tid, True)
    return None


def place(doc, dot_id, crv, click, style, attr, tol):
    text = rs.coercegeometry(dot_id).Text
    tid = place_text(doc, text, crv, click, style, attr, tol)
    if tid:
        doc.Objects.Delete(dot_id, True)
        doc.Views.Redraw()
    else:
        print(u"'%s': text does not fit in the panel, dot kept" % text)
    return tid


HELP = u"""Options:
  Style — text style"""  # printed at start — visible under the option fields


def main():
    print(HELP)
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    pts.ensure_styles(doc)  # so PAT styles are in the list also in files from DXF
    name = sc.sticky.get(STICKY)
    if not name or doc.DimStyles.FindName(name) is None:
        name = doc.DimStyles.Current.Name
    if not rs.IsLayer(LAYER):
        rs.AddLayer(LAYER, (0, 0, 255))
    attr = Rhino.DocObjects.ObjectAttributes()
    attr.LayerIndex = doc.Layers.FindByFullPath(LAYER, -1)
    rs.UnselectAllObjects()
    made = []

    # "dot -> panel -> corner" in a loop, Enter/Esc — exit.
    while True:
        dot, name = get_one(doc, name, Rhino.DocObjects.ObjectType.TextDot, u"Select a dot")
        if dot is None:
            break
        rs.UnselectAllObjects()
        panel, name = get_one(doc, name, Rhino.DocObjects.ObjectType.Curve,
                              u"Select the panel for '%s'" % dot.TextDot().Text, closed=True)
        if panel is None:
            break
        rs.UnselectAllObjects()
        click = get_corner(panel.Curve())
        if click is None:
            break
        sc.sticky[STICKY] = name
        tid = place(doc, dot.ObjectId, panel.Curve(), click, doc.DimStyles.FindName(name), attr, tol)
        if tid:
            made.append(tid)

    if made:
        rs.SelectObjects(made)  # everything created is selected on exit


if __name__ == "__main__":
    main()
