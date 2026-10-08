# -*- coding: utf-8 -*-
# Text styles for patterns going to the plotter / cutting at 1:1 scale.
# Architectural ISO 3098 height series (step x1.41), single-stroke font SLF-RHN Architect,
# model scale 1 — style height = real mm on the fabric, no hidden x10 multiplier.
# 1) Creates / updates styles "PAT 2.5 mm" ... "PAT 40 mm" in the current document
#    (also works in files opened from DXF, which have no template).
# 2) Picks a style for the selected texts by the width of the panel they are in.
# Compatibility: IronPython 2.7 / CPython 3 (Rhino 8).
import System
import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc

FONT = "SLF-RHN Architect"  # single-stroke: the plotter pen writes a letter in one pass
SERIES = (2.5, 3.5, 5, 7, 10, 14, 20, 28, 40)  # mm, ISO 3098 series from architectural drawings
RATIO = 15  # height ~ panel width / 15 (your 30 mm on ~430 mm strips)
DEFAULT = 14  # mm — default label style of all scripts (option Style changes it per script)


def style_name(h):
    # Leading zero: Rhino sorts styles alphabetically, otherwise "PAT 10" comes before "PAT 2.5".
    return "PAT %s%g mm" % ("0" if h < 10 else "", h)


def height_for(width):
    """The largest height in the series not exceeding width / RATIO."""
    fit = [h for h in SERIES if h <= width / float(RATIO)]
    return fit[-1] if fit else SERIES[0]


def ensure_styles(doc):
    """Creates or updates the series styles. Returns {height: DimensionStyle}."""
    font = Rhino.DocObjects.Font.FromQuartetProperties(FONT, False, False)
    base = doc.DimStyles.FindName("Millimeter Architectural") or doc.DimStyles.Current
    styles = {}
    for h in SERIES:
        name = style_name(h)
        old = doc.DimStyles.FindName(name) or doc.DimStyles.FindName("PAT %g mm" % h)  # old name without the zero
        ds = old.Duplicate() if old else base.Duplicate(name, System.Guid.NewGuid(), System.Guid.Empty)
        ds.Name = name
        ds.Font = font
        ds.TextHeight = h
        ds.DimensionScale = 1.0  # 1:1
        ds.DrawTextMask = False  # the mask is not plotted, and in PDF it hides lines
        if old:
            doc.DimStyles.Modify(ds, old.Index, True)
        else:
            doc.DimStyles.Add(ds, False)
        styles[h] = doc.DimStyles.FindName(name)
    return styles


def label_style(doc, key):
    """Label style of a script: the one picked with option Style (sticky key + ".style"), else PAT 14 mm."""
    ensure_styles(doc)  # so PAT styles exist also in files from DXF
    name = sc.sticky.get(key + ".style")
    return (name and doc.DimStyles.FindName(name)) or doc.DimStyles.FindName(style_name(DEFAULT))


def pick_style(doc, key):
    """Option Style: pick a document text style from a list, remembered for the script (key)."""
    names = sorted(ds.Name for ds in doc.DimStyles if not ds.IsDeleted and not ds.IsChild)
    cur = label_style(doc, key).Name
    sc.sticky[key + ".style"] = rs.ListBox(names, u"Text style", u"Text style", cur) or cur


def cm(x, doc=None):
    """Length in document units → number for a label, in cm (labels are read by the seamstresses): 35 mm → "3.5"."""
    k = Rhino.RhinoMath.UnitScale((doc or sc.doc).ModelUnitSystem, Rhino.UnitSystem.Centimeters)
    return "%g" % round(x * k, 1)


def get_number(prompt, default, key, lower=0.0):
    """rs.GetReal with option Style (label style of the script key). Number or None."""
    while True:
        gn = Rhino.Input.Custom.GetNumber()
        gn.SetCommandPrompt(u"%s (text style: %s)" % (prompt, label_style(sc.doc, key).Name))
        gn.SetDefaultNumber(default)
        gn.SetLowerLimit(lower, False)
        opt = gn.AddOption("Style")
        res = gn.Get()
        if res == Rhino.Input.GetResult.Option and gn.OptionIndex() == opt:
            pick_style(sc.doc, key)
            continue
        return gn.Number() if res == Rhino.Input.GetResult.Number else None


def closed_curves(doc):
    tol = doc.ModelAbsoluteTolerance
    out = []
    for obj in doc.Objects.FindByObjectType(Rhino.DocObjects.ObjectType.Curve):
        crv = obj.Geometry
        if crv.IsClosed and crv.IsPlanar(tol):
            out.append((crv, crv.GetBoundingBox(True)))
    return out


def panel_width(text_bb, curves, tol):
    """Smaller extent of the smallest closed curve around the text centre (None — text outside panels)."""
    c = text_bb.Center
    t = text_bb.Diagonal
    best = None
    for crv, bb in curves:
        d = bb.Diagonal
        if d.X < t.X or d.Y < t.Y:
            continue  # smaller than the text itself: an arrow or a frame, not a panel
        if not (bb.Min.X <= c.X <= bb.Max.X and bb.Min.Y <= c.Y <= bb.Max.Y):
            continue
        if crv.Contains(rg.Point3d(c.X, c.Y, bb.Min.Z), rg.Plane.WorldXY, tol) != rg.PointContainment.Inside:
            continue
        if best is None or d.X * d.Y < best[0]:
            best = (d.X * d.Y, min(d.X, d.Y))
    # ponytail: width = smaller bbox extent; overestimated for diagonal strips — then use the inscribed circle.
    return best[1] if best else None


def auto_size(doc, ids, styles):
    """Assigns a style to texts by panel width. Returns report lines."""
    curves = closed_curves(doc)
    tol = doc.ModelAbsoluteTolerance
    report = []
    for oid in ids:
        obj = doc.Objects.FindId(oid)
        if obj is None or not isinstance(obj.Geometry, rg.TextEntity):
            continue
        te = obj.Geometry.Duplicate()
        w = panel_width(obj.Geometry.GetBoundingBox(True), curves, tol)
        if w is None:
            report.append(u"'%s': not inside a panel — unchanged" % te.PlainText)
            continue
        h = height_for(w)
        align = (te.TextHorizontalAlignment, te.TextVerticalAlignment)
        te.DimensionStyleId = styles[h].Id
        te.ClearPropertyOverrides()  # height, font and scale — only from the style
        te.TextHorizontalAlignment, te.TextVerticalAlignment = align  # the insertion point does not move
        doc.Objects.Replace(oid, te)
        report.append(u"'%s' -> %s (panel %d mm)" % (te.PlainText, style_name(h), w))
    return report


def main():
    doc = sc.doc
    styles = ensure_styles(doc)
    ids = rs.GetObjects(u"Texts to auto-size by panel (Enter — only create styles)",
                        rs.filter.annotation, preselect=True)
    for line in auto_size(doc, ids or [], styles):
        print(line)
    doc.Views.Redraw()
    print(u"PAT %g-%g mm styles ready. Rule: height ~ panel width / %d." % (SERIES[0], SERIES[-1], RATIO))


if __name__ == "__main__":
    main()
