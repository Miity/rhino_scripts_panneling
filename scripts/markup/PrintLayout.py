# -*- coding: utf-8 -*-
"""PDF для замовника (чорно-білий, A4, зручно гортати на телефоні). Вибрати контури панелей → Enter.
Сторінки (Layout): 1 «Schema» — усі вибрані панелі разом, видно лише номери P<n>;
2 «Legenda» — італійською, тільки позначки, що є на цих панелях (тексти з Legend.py);
далі одна панель на сторінку (ім'я — її P<n> / TP<n>, за номером), масштаб 1:N сам — найбільший, що влазить.

Підписи (тексти й TextDot) копіюються в простір листа: Arial LABEL_H мм на папері, біла маска під текстом.
Оригінали 1:1 у моделі не змінюються — лише ховаються в цих detail (Hide in detail).
PDF <файл>_cliente.pdf поруч із .3dm. Товщини ліній задаються тільки на час запису PDF (WEIGHTS),
потім шари повертаються як були. Повторний запуск видаляє сторінки попереднього запуску (лише свої).
"""
import os
import re
import sys

SCALES = (1, 2, 5, 10, 15, 20, 25, 50, 100, 200)
A4 = (297.0, 210.0)
MARGIN, TITLE_H = 10.0, 12.0     # мм на папері: поля і смуга шапки зверху
LABEL_H, P_H, HEAD_H = 4.0, 8.0, 5.0  # висота підписів, номерів на Schema, шапки
FONT = "Arial"
LANG = "IT"
KEY = "PrintLayout_pages"        # doc.Strings: id сторінок, створених скриптом
WEIGHTS = ((r"^CUT$", 0.35), (r"zip|canalina", 0.25), (r".", 0.13))  # шар (regex, без регістру) → мм
NAME_RX = r"(P|TP|F)\d+(?=\s|$)"  # підпис, що дає ім'я сторінці панелі (P3, TP1  H=120 → TP1)


def fit(w, h, paper=A4):
    """(ширина листа, висота листа, N для масштабу 1:N) — орієнтація за формою, N — найменший, що влазить."""
    pw, ph = paper if w >= h else paper[::-1]
    aw, ah = pw - 2 * MARGIN, ph - 2 * MARGIN - TITLE_H
    for n in SCALES:
        if w * 1.05 / n <= aw and h * 1.05 / n <= ah:
            return pw, ph, n
    return pw, ph, SCALES[-1]


def page_order(name):
    """P1, P2, P10 … потім TP, F, решта — за номером, а не за алфавітом."""
    m = re.match(r"([A-Z]+)(\d+)$", name)
    return ({"P": 0, "TP": 1, "F": 2}.get(m.group(1), 3), int(m.group(2)), "") if m else (4, 0, name)


def weight(layer):
    return next(w for rx, w in WEIGHTS if re.search(rx, layer, re.I))


def main():
    import Rhino
    import scriptcontext as sc
    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt(u"Вибери контури панелей для PDF (кожна — окрема сторінка)")
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Curve
    go.GeometryAttributeFilter = Rhino.Input.Custom.GeometryAttributeFilter.ClosedCurve
    go.EnablePreSelect(True, True)
    if go.GetMultiple(1, 0) != Rhino.Input.GetResult.Object:
        return
    rec = sc.doc.BeginUndoRecord("PrintLayout")
    try:
        path = build(sc.doc, [go.Object(i).Curve() for i in range(go.ObjectCount)])
    finally:
        sc.doc.EndUndoRecord(rec)
    sc.doc.Views.Redraw()
    print(u"PDF: %s" % path)


def build(doc, crvs):
    """Створює сторінки й пише PDF; повертає шлях до PDF."""
    import Rhino
    from Rhino.Geometry import BoundingBox, Point2d, Point3d, Plane, Vector3d, TextEntity, TextJustification
    from Rhino.DocObjects import ActiveSpace, ObjectType
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from Legend import legend_lines

    font = Rhino.DocObjects.Font.FromQuartetProperties(FONT, False, False)
    style = doc.DimStyles.Current

    # 1. прибрати сторінки попереднього запуску і їхні Hide in detail
    old = set((doc.Strings.GetValue(KEY) or "").split())
    old_dets = set()
    for pv in list(doc.Views.GetPageViews()):
        if str(pv.MainViewport.Id) in old:
            old_dets.update(d.Id for d in pv.GetDetailViews())
            for o in list(doc.Objects):
                if o.Attributes.Space == ActiveSpace.PageSpace and o.Attributes.ViewportId == pv.MainViewport.Id:
                    doc.Objects.Delete(o, True)
            pv.Close()

    # 2. підписи моделі: (об'єкт, точка, текст)
    labels = []
    for o in doc.Objects.GetObjectList(ObjectType.Annotation | ObjectType.TextDot):
        if o.Attributes.Space != ActiveSpace.ModelSpace:
            continue
        stale = [d for d in old_dets if o.Attributes.HasHideInDetailOverrideSet(d)]
        if stale:
            oa = o.Attributes.Duplicate()
            for d in stale:
                oa.RemoveHideInDetailOverride(d)
            doc.Objects.ModifyAttributes(o, oa, True)
        g = o.Geometry
        if not o.Visible:
            continue
        if isinstance(g, TextEntity):
            labels.append((o, g.Plane.Origin, g.PlainText.strip()))
        elif isinstance(g, Rhino.Geometry.TextDot):
            labels.append((o, g.Point, g.Text.strip()))

    def add_text(page, txt, plane, height, just, src=None):
        te = TextEntity.Create(txt, plane, style, False, 0, 0)
        te.Font, te.TextHeight, te.Justification = font, height, just
        te.MaskEnabled, te.MaskUsesViewportColor, te.MaskOffset = True, True, 0.5
        a = src.Duplicate() if src else Rhino.DocObjects.ObjectAttributes()
        a.RemoveFromAllGroups()
        a.Space, a.ViewportId = ActiveSpace.PageSpace, page.MainViewport.Id
        doc.Objects.AddText(te, a)

    def head(page, txt, ph):
        add_text(page, txt, Plane(Point3d(MARGIN, ph - MARGIN, 0), Vector3d.ZAxis), HEAD_H, TextJustification.TopLeft)

    def detail_page(name, bb, title, keep, area=None):
        """Сторінка з одним detail на bb; підписи, для яких keep(текст) → висота (None — сховати), у page space.
        area — переносити лише підписи всередині (сусідні панелі, що влізли в detail, без підписів)."""
        pw, ph, n = fit(bb.Max.X - bb.Min.X, bb.Max.Y - bb.Min.Y)
        page = doc.Views.AddPageView(name, pw, ph)
        det = page.AddDetailView(name, Point2d(MARGIN, MARGIN), Point2d(pw - MARGIN, ph - MARGIN - TITLE_H),
                                 Rhino.Display.DefinedViewportProjection.Top)
        det.Viewport.ZoomBoundingBox(bb)
        det.DetailGeometry.SetScale(1, doc.ModelUnitSystem, 1.0 / n, doc.PageUnitSystem)
        det.Viewport.SetCameraTarget(bb.Center, True)
        det.DetailGeometry.IsProjectionLocked = True
        det.CommitViewportChanges()
        det.CommitChanges()
        # модель → лист: центр bb → центр detail, масштаб 1:N (Top, тож без повороту)
        k = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, doc.PageUnitSystem) / n
        pc = Point3d(pw / 2.0, (ph - TITLE_H) / 2.0, 0)
        xf = Rhino.Geometry.Transform.Translation(pc - bb.Center) * Rhino.Geometry.Transform.Scale(bb.Center, k)
        placed, shown = [], []
        for o, p, txt in labels:
            q = Point3d(p)
            q.Transform(xf)
            if not (MARGIN <= q.X <= pw - MARGIN and MARGIN <= q.Y <= ph - MARGIN - TITLE_H):
                continue  # поза цим detail
            oa = o.Attributes.Duplicate()
            oa.AddHideInDetailOverride(det.Id)  # оригінал 1:1 у цьому detail не видно
            doc.Objects.ModifyAttributes(o, oa, True)
            h = keep(txt) if area is None or area.Contains(p) else None
            if not h or any(t == txt and q.DistanceTo(r) < 15 for t, r in placed):
                continue  # не потрібен або той самий підпис поруч (TextDot P1 + текст P1)
            g = o.Geometry
            if isinstance(g, TextEntity):
                pl = Plane(g.Plane)
                pl.Transform(xf)
                just = g.Justification
            else:
                pl, just = Plane(q, Vector3d.ZAxis), TextJustification.MiddleCenter
            add_text(page, txt, pl, h, just, o.Attributes)
            placed.append((txt, q))
            shown.append(txt)
        head(page, u"%s — scala 1:%d — %s" % (title, n, fname), ph)
        return page, shown

    fname = os.path.splitext(os.path.basename(doc.Path or "senza_nome"))[0]
    pages = []
    doc.Views.RedrawEnabled = False
    try:
        # 3. Schema: усе разом, тільки номери панелей
        allbb = BoundingBox.Empty
        for c in crvs:
            allbb.Union(c.GetBoundingBox(True))
        pages.append(detail_page("Schema", allbb, "Schema",
                                 lambda t: P_H if re.match(r"P\d+$", t) else None)[0])

        # 4. сторінки панелей (спершу визначити імена, щоб відсортувати)
        named = []
        for k, c in enumerate(crvs):
            bb = c.GetBoundingBox(True)
            big = BoundingBox(bb.Min, bb.Max)
            big.Inflate((bb.Max.X - bb.Min.X) * 0.05, (bb.Max.Y - bb.Min.Y) * 0.05, 1)  # z: крива на -1e-17, підпис на 0
            nm = [re.match(NAME_RX, t).group(0) for o, p, t in labels if re.match(NAME_RX, t) and big.Contains(p)]
            named.append((nm[0] if nm else u"Pannello %d" % (k + 1), bb, big))
        named.sort(key=lambda x: page_order(x[0]))
        legend_page = doc.Views.AddPageView("Legenda", A4[1], A4[0])  # друга сторінка, заповнюється нижче
        pages.append(legend_page)
        seen = set()
        for nm, bb, big in named:  # номер панелі вже в шапці — P<n> на сторінці не дублюємо
            page, shown = detail_page(nm, bb, nm, lambda t: None if re.match(r"P\d+$", t) else LABEL_H, big)
            pages.append(page)
            seen.update(shown + [nm])

        # 5. легенда: тільки позначки, що є на сторінках панелей
        head(legend_page, u"Legenda — " + fname, A4[0])
        lines = [re.sub(r"\s*\(Parts::\w+\)", "", l) for l in legend_lines(list(seen), LANG)]
        add_text(legend_page, u"\n".join(lines) or u"—",
                 Plane(Point3d(MARGIN, A4[0] - MARGIN - TITLE_H - 5, 0), Vector3d.ZAxis),
                 LABEL_H, TextJustification.TopLeft)
    finally:
        doc.Views.RedrawEnabled = True
    doc.Strings.SetString(KEY, " ".join(str(p.MainViewport.Id) for p in pages))

    # 6. PDF чорно-білий; товщини ліній — лише на час запису
    path = os.path.join(os.path.dirname(doc.Path or os.path.expanduser("~/Desktop/x")), fname + "_cliente.pdf")
    saved = [(l.Index, l.PlotWeight) for l in doc.Layers if not l.IsDeleted]
    try:
        for i, _ in saved:
            doc.Layers[i].PlotWeight = weight(doc.Layers[i].FullPath)
        f = Rhino.FileIO.FilePdf.Create()
        for p in pages:
            s = Rhino.Display.ViewCaptureSettings(p, 300)
            s.OutputColor = Rhino.Display.ViewCaptureSettings.ColorMode.BlackAndWhite
            f.AddPage(s)
        f.Write(path)
    finally:
        for i, w in saved:
            doc.Layers[i].PlotWeight = w
    return path


if __name__ == "__main__":
    main()
