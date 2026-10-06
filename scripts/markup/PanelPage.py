# -*- coding: utf-8 -*-
"""Сторінка (Layout) для панелі: виділити об'єкти (контур панелі або будь-які частини) → один новий лист A4 (вертикальний)
з одним detail (Top), наведеним на всі виділені разом (як Zoom Selected); масштаб — найбільший круглий 1:N,
що влазить; detail не заблоковано (можна поправити). Один запуск — один лист.
Ім'я листа: UserText Part (Panels.py) з виділених, інакше підпис P<n> у межах виділеного,
інакше наступний вільний P<n> серед листів. Підписи й шари не чіпає.
"""
import re

SCALES = (1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 200)
A4 = (210.0, 297.0)  # завжди вертикально: Print на Mac дає одну орієнтацію на всі листи
MARGIN = 10.0  # мм на папері


def fit(w, h, paper=A4):
    """(ширина листа, висота листа, N для 1:N) — N найменший, з яким w × h влазить у лист."""
    pw, ph = paper
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


def panel_name(doc, objs, bb):
    """UserText Part з виділених, інакше текст / TextDot P<n> усередині bb (по XY)."""
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
    """Лист A4 з detail на всі objs разом; повертає (ім'я, N)."""
    import Rhino
    from Rhino.Geometry import BoundingBox, Point2d
    bb = BoundingBox.Empty
    for o in objs:
        bb.Union(o.Geometry.GetBoundingBox(True))
    taken = set(v.PageName for v in doc.Views.GetPageViews())
    name = unique(panel_name(doc, objs, bb) or next_name(taken), taken)
    pw, ph, n = fit(bb.Max.X - bb.Min.X, bb.Max.Y - bb.Min.Y)
    page = doc.Views.AddPageView(name, pw, ph)
    page.SetPageAsActive()
    doc.Views.ActiveView = page
    det = page.AddDetailView(name, Point2d(MARGIN, MARGIN), Point2d(pw - MARGIN, ph - MARGIN),
                             Rhino.Display.DefinedViewportProjection.Top)
    page.SetActiveDetail(det.Id)
    doc.Views.Redraw()
    # порядок важливий: CommitChanges (масштаб) перезаписує камеру, тож центр — після нього, окремим commit
    det.DetailGeometry.SetScale(1, doc.ModelUnitSystem, 1.0 / n, doc.PageUnitSystem)
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
    go.SetCommandPrompt(u"Виділи об'єкти для листа (панель або її частини) — буде один лист на все виділене")
    go.EnablePreSelect(True, True)
    if go.GetMultiple(1, 0) != Rhino.Input.GetResult.Object:
        return
    name, n = make_page(sc.doc, [go.Object(i).Object() for i in range(go.ObjectCount)])
    print(u"Лист %s, масштаб 1:%d" % (name, n))


if __name__ == "__main__":
    main()
