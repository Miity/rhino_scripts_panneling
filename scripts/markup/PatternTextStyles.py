# -*- coding: utf-8 -*-
# Стилі тексту для лекал, що йдуть на плотер / розкрій у масштабі 1:1.
# Архітектурний ряд висот ISO 3098 (крок x1.41), одноштриховий шрифт SLF-RHN Architect,
# масштаб моделі 1 — висота стилю = реальні мм на тканині, без прихованого множника x10.
# 1) Створює / оновлює стилі "PAT 2.5 mm" ... "PAT 40 mm" у поточному документі
#    (працює і у файлах, відкритих з DXF, де шаблону немає).
# 2) Вибраним текстам підбирає стиль за шириною панелі, в якій вони стоять.
# Сумісність: IronPython 2.7 / CPython 3 (Rhino 8).
import System
import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc

FONT = "SLF-RHN Architect"  # одноштриховий: перо плотера пише літеру одним проходом
SERIES = (2.5, 3.5, 5, 7, 10, 14, 20, 28, 40)  # мм, ряд ISO 3098 з архітектурних креслень
RATIO = 15  # висота ~ ширина панелі / 15 (твої 30 мм на смугах ~430 мм)


def style_name(h):
    # Нуль попереду: Rhino сортує стилі за алфавітом, інакше "PAT 10" стоїть перед "PAT 2.5".
    return "PAT %s%g mm" % ("0" if h < 10 else "", h)


def height_for(width):
    """Найбільша висота з ряду, що не перевищує width / RATIO."""
    fit = [h for h in SERIES if h <= width / float(RATIO)]
    return fit[-1] if fit else SERIES[0]


def ensure_styles(doc):
    """Створює або оновлює стилі ряду. Повертає {висота: DimensionStyle}."""
    font = Rhino.DocObjects.Font.FromQuartetProperties(FONT, False, False)
    base = doc.DimStyles.FindName("Millimeter Architectural") or doc.DimStyles.Current
    styles = {}
    for h in SERIES:
        name = style_name(h)
        old = doc.DimStyles.FindName(name) or doc.DimStyles.FindName("PAT %g mm" % h)  # стара назва без нуля
        ds = old.Duplicate() if old else base.Duplicate(name, System.Guid.NewGuid(), System.Guid.Empty)
        ds.Name = name
        ds.Font = font
        ds.TextHeight = h
        ds.DimensionScale = 1.0  # 1:1
        ds.DrawTextMask = False  # маска не плотериться, а в PDF ховає лінії
        if old:
            doc.DimStyles.Modify(ds, old.Index, True)
        else:
            doc.DimStyles.Add(ds, False)
        styles[h] = doc.DimStyles.FindName(name)
    return styles


def closed_curves(doc):
    tol = doc.ModelAbsoluteTolerance
    out = []
    for obj in doc.Objects.FindByObjectType(Rhino.DocObjects.ObjectType.Curve):
        crv = obj.Geometry
        if crv.IsClosed and crv.IsPlanar(tol):
            out.append((crv, crv.GetBoundingBox(True)))
    return out


def panel_width(text_bb, curves, tol):
    """Менший габарит найменшої замкненої кривої навколо центру тексту (None — текст поза панелями)."""
    c = text_bb.Center
    t = text_bb.Diagonal
    best = None
    for crv, bb in curves:
        d = bb.Diagonal
        if d.X < t.X or d.Y < t.Y:
            continue  # менша за сам текст: стрілка чи рамка, а не панель
        if not (bb.Min.X <= c.X <= bb.Max.X and bb.Min.Y <= c.Y <= bb.Max.Y):
            continue
        if crv.Contains(rg.Point3d(c.X, c.Y, bb.Min.Z), rg.Plane.WorldXY, tol) != rg.PointContainment.Inside:
            continue
        if best is None or d.X * d.Y < best[0]:
            best = (d.X * d.Y, min(d.X, d.Y))
    # ponytail: ширина = менший габарит bbox; для діагональних смуг завищена — тоді рахувати вписане коло.
    return best[1] if best else None


def auto_size(doc, ids, styles):
    """Призначає текстам стиль за шириною панелі. Повертає рядки звіту."""
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
            report.append(u"'%s': не всередині панелі — без змін" % te.PlainText)
            continue
        h = height_for(w)
        align = (te.TextHorizontalAlignment, te.TextVerticalAlignment)
        te.DimensionStyleId = styles[h].Id
        te.ClearPropertyOverrides()  # висота, шрифт і масштаб — тільки зі стилю
        te.TextHorizontalAlignment, te.TextVerticalAlignment = align  # точка вставки не зсувається
        doc.Objects.Replace(oid, te)
        report.append(u"'%s' -> %s (панель %d мм)" % (te.PlainText, style_name(h), w))
    return report


def main():
    doc = sc.doc
    styles = ensure_styles(doc)
    ids = rs.GetObjects(u"Тексти для авто-розміру за панеллю (Enter — лише створити стилі)",
                        rs.filter.annotation, preselect=True)
    for line in auto_size(doc, ids or [], styles):
        print(line)
    doc.Views.Redraw()
    print(u"Стилі PAT %g-%g mm готові. Правило: висота ~ ширина панелі / %d." % (SERIES[0], SERIES[-1], RATIO))


if __name__ == "__main__":
    main()
