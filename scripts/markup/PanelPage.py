# -*- coding: utf-8 -*-
"""Сторінка (Layout) для панелі: вибрати контур(и) панелі → на кожну новий лист A4 з одним detail (Top),
зум на панель, масштаб — найбільший круглий 1:N, що влазить, detail заблоковано.
Ім'я листа — номер панелі: UserText Part (Panels.py), інакше підпис P<n> усередині контуру,
інакше наступний вільний P<n> серед листів. Підписи й шари не чіпає.
"""
import re

SCALES = (1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 200)
A4 = (297.0, 210.0)
MARGIN = 10.0  # мм на папері


def fit(w, h, paper=A4):
    """(ширина листа, висота листа, N для 1:N) — орієнтація за формою панелі, N — найменший, що влазить."""
    pw, ph = paper if w >= h else paper[::-1]
    for n in SCALES:
        if w * 1.05 / n <= pw - 2 * MARGIN and h * 1.05 / n <= ph - 2 * MARGIN:
            return pw, ph, n
    return pw, ph, SCALES[-1]


def next_name(taken):
    nums = [int(m.group(1)) for m in (re.match(r"P(\d+)$", t) for t in taken) if m]
    return "P%d" % (max(nums) + 1 if nums else 1)


def unique(name, taken):
    k, out = 2, name
    while out in taken:
        out, k = "%s (%d)" % (name, k), k + 1
    return out


def panel_name(doc, obj, bb):
    """UserText Part, інакше текст / TextDot P<n> усередині bb (по XY)."""
    import Rhino
    part = obj.Attributes.GetUserString("Part")
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


def make_page(doc, obj, taken):
    """Лист A4 з detail на obj; повертає (ім'я, N). taken — зайняті імена листів (доповнюється)."""
    import Rhino
    from Rhino.Geometry import Point2d
    bb = obj.Geometry.GetBoundingBox(True)
    name = unique(panel_name(doc, obj, bb) or next_name(taken), taken)
    taken.add(name)
    pw, ph, n = fit(bb.Max.X - bb.Min.X, bb.Max.Y - bb.Min.Y)
    page = doc.Views.AddPageView(name, pw, ph)
    det = page.AddDetailView(name, Point2d(MARGIN, MARGIN), Point2d(pw - MARGIN, ph - MARGIN),
                             Rhino.Display.DefinedViewportProjection.Top)
    page.SetActiveDetail(det.Id)
    det.Viewport.ZoomBoundingBox(bb)
    det.DetailGeometry.SetScale(1, doc.ModelUnitSystem, 1.0 / n, doc.PageUnitSystem)
    det.Viewport.SetCameraTarget(bb.Center, True)  # після масштабу — центр знову на панель
    det.CommitViewportChanges()
    det.DetailGeometry.IsProjectionLocked = True
    det.CommitChanges()
    page.SetPageAsActive()
    return name, n


def main():
    import Rhino
    import scriptcontext as sc

    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt(u"Вибери контур(и) панелей — кожна отримає свій лист")
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Curve
    go.EnablePreSelect(True, True)
    if go.GetMultiple(1, 0) != Rhino.Input.GetResult.Object:
        return
    doc = sc.doc
    taken = set(v.PageName for v in doc.Views.GetPageViews())
    made = [u"%s 1:%d" % make_page(doc, go.Object(i).Object(), taken) for i in range(go.ObjectCount)]
    doc.Views.Redraw()
    print(u"Листи: " + u", ".join(made))


if __name__ == "__main__":
    main()
