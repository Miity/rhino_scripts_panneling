# -*- coding: utf-8 -*-
"""Page (Layout) for a panel: select objects (panel contour or any parts) → one new A4 sheet (portrait)
with one detail (Top) aimed at all selected objects together (like Zoom Selected); scale as in Zoom Selected (the selection fills the frame),
not rounded; the detail is not locked (can be adjusted). One run — one sheet.
Sheet name: UserText Part (Panels.py) from the selection, otherwise a P<n> label within the selection,
otherwise the next free P<n> among sheets. Labels and layers are not touched.
"""
import re

A4 = (210.0, 297.0)  # always portrait: Print on Mac uses one orientation for all sheets
MARGIN = 10.0  # mm on paper


def fit(w, h, paper=A4):
    """(sheet width, sheet height, N for 1:N) — like Zoom Selected: w × h (mm) fills the frame with a 5 % margin."""
    pw, ph = paper
    return pw, ph, max(w / (pw - 2 * MARGIN), h / (ph - 2 * MARGIN)) * 1.05


def next_name(taken):
    nums = [int(m.group(1)) for m in (re.match(r"P(\d+)$", t) for t in taken) if m]
    return "P%d" % (max(nums) + 1 if nums else 1)


def unique(name, taken):
    k, out = 2, name
    while out in taken:
        out, k = "%s (%d)" % (name, k), k + 1
    return out


def panel_name(doc, objs, bb):
    """UserText Part from the selection, otherwise a text / TextDot P<n> inside bb (by XY)."""
    import Rhino
    for o in objs:
        part = o.Attributes.GetUserString("Part")
        if part:
            return part
    for o in doc.Objects.GetObjectList(Rhino.DocObjects.ObjectType.Annotation | Rhino.DocObjects.ObjectType.TextDot):
        g = o.Geometry
        if isinstance(g, Rhino.Geometry.TextEntity):
            t, p = g.PlainText.strip(), g.Plane.Origin
        elif isinstance(g, Rhino.Geometry.TextDot):
            t, p = g.Text.strip(), g.Point
        else:
            continue
        if re.match(r"P\d+$", t) and bb.Min.X <= p.X <= bb.Max.X and bb.Min.Y <= p.Y <= bb.Max.Y:
            return t
    return None


def make_page(doc, objs):
    """A4 sheet with a detail on all objs together; returns (name, N)."""
    import Rhino
    from Rhino.Geometry import BoundingBox, Point2d
    bb = BoundingBox.Empty
    for o in objs:
        bb.Union(o.Geometry.GetBoundingBox(True))
    taken = set(v.PageName for v in doc.Views.GetPageViews())
    name = unique(panel_name(doc, objs, bb) or next_name(taken), taken)
    k = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Millimeters)
    pw, ph, n = fit((bb.Max.X - bb.Min.X) * k, (bb.Max.Y - bb.Min.Y) * k)
    page = doc.Views.AddPageView(name, pw, ph)
    page.SetPageAsActive()
    doc.Views.ActiveView = page
    det = page.AddDetailView(name, Point2d(MARGIN, MARGIN), Point2d(pw - MARGIN, ph - MARGIN),
                             Rhino.Display.DefinedViewportProjection.Top)
    page.SetActiveDetail(det.Id)
    doc.Views.Redraw()
    # order matters: CommitChanges (scale) overwrites the camera, so the centre goes after it, in a separate commit
    det.DetailGeometry.SetScale(n, Rhino.UnitSystem.Millimeters, 1, Rhino.UnitSystem.Millimeters)
    det.CommitChanges()
    det = [d for d in page.GetDetailViews() if d.Id == det.Id][0]
    det.Viewport.SetCameraTarget(bb.Center, True)
    det.CommitViewportChanges()
    page.SetPageAsActive()
    doc.Views.Redraw()
    return name, n


def main():
    import Rhino
    import scriptcontext as sc

    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt(u"Select objects for the sheet (a panel or its parts) — one sheet for the whole selection")
    go.EnablePreSelect(True, True)
    if go.GetMultiple(1, 0) != Rhino.Input.GetResult.Object:
        return
    name, n = make_page(sc.doc, [go.Object(i).Object() for i in range(go.ObjectCount)])
    print(u"Sheet %s, scale 1:%.2f" % (name, n))


if __name__ == "__main__":
    main()
