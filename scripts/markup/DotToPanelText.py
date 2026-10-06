# -*- coding: utf-8 -*-
# Вибрані TextDot -> текст всередині найближчої панелі (замкненої кривої), у її правому верхньому куті.
# Стиль тексту вибирається зі списку при запуску. Шар INK, dot видаляється.
# Сумісність: IronPython 2.7 / CPython 3 (Rhino 8).
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
    """Відрізки [x0, x1], де горизонталь y всередині полігону."""
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
    """Прямокутник width x hgt всередині полігону, найближчий до бажаного правого-верхнього кута (tx, ty).
    Смуги йдуть від ty вглиб панелі (down — вниз, інакше вгору); у першій смузі, де є місце,
    береться x, найближчий до tx. Повертає (x_right, y_top) або None.
    Межі полігону між вершинами лінійні, тож досить перевірити краї смуги і рівні вершин у ній — точно, без перебору."""
    ys = sorted(set(p.Y for p in poly))
    y = min(max(ty, ymin + hgt), ymax)
    while ymin + hgt <= y <= ymax:
        levels = [y, y - hgt] + [v for v in ys if y - hgt < v < y]
        free = None
        for lv in levels:
            eps = 1e-6 * (1 if lv < y else -1)  # не на самій вершині
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
    return rs.ListBox(names, u"Стиль тексту", u"Dot -> текст", current) or current


def get_one(doc, name, geom, prompt, closed=False):
    """Вибір одного об'єкта з опцією Style. Повертає (ObjRef або None, назва стилю)."""
    while True:
        go = Rhino.Input.Custom.GetObject()
        go.GeometryFilter = geom
        if closed:
            go.GeometryAttributeFilter = Rhino.Input.Custom.GeometryAttributeFilter.ClosedCurve
        go.SetCommandPrompt(u"%s (стиль: %s)" % (prompt, name))
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
    """Клік біля кута панелі, куди ставити текст. Enter — правий верхній кут."""
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt(u"Клікни біля кута панелі для тексту (Enter — правий верхній)")
    gp.AcceptNothing(True)
    res = gp.Get()
    if res == Rhino.Input.GetResult.Point:
        return gp.Point()
    if res == Rhino.Input.GetResult.Nothing:
        return crv.GetBoundingBox(True).Max
    return None


def place_text(doc, text, crv, click, style, attr, tol):
    """Текст усередині панелі crv у куті, найближчому до click. Повертає id або None (не влазить)."""
    h = style.TextHeight * style.DimensionScale
    pb = crv.GetBoundingBox(True)
    c = pb.Center
    right, top = click.X >= c.X, click.Y >= c.Y  # який кут: за положенням кліку відносно центру панелі
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
    w, hg = tb.Max.X - tb.Min.X + 2 * h, tb.Max.Y - tb.Min.Y + 2 * h  # текст + відступ h з усіх боків
    pc = crv.ToPolyline(tol * 10, 0.05, 0, 0)  # дуга -> ламана з точністю 10*tol
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
        print(u"'%s': текст не влазить у панель, dot залишено" % text)
    return tid


HELP = u"""Опції:
  Style — стиль тексту"""  # друкується на старті — видно під полями опцій


def main():
    print(HELP)
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    pts.ensure_styles(doc)  # щоб PAT-стилі були в списку і у файлах з DXF
    name = sc.sticky.get(STICKY)
    if not name or doc.DimStyles.FindName(name) is None:
        name = doc.DimStyles.Current.Name
    if not rs.IsLayer(LAYER):
        rs.AddLayer(LAYER, (0, 0, 255))
    attr = Rhino.DocObjects.ObjectAttributes()
    attr.LayerIndex = doc.Layers.FindByFullPath(LAYER, -1)
    rs.UnselectAllObjects()
    made = []

    # «dot -> панель -> кут» по колу, Enter/Esc — вихід.
    while True:
        dot, name = get_one(doc, name, Rhino.DocObjects.ObjectType.TextDot, u"Вибери dot")
        if dot is None:
            break
        rs.UnselectAllObjects()
        panel, name = get_one(doc, name, Rhino.DocObjects.ObjectType.Curve,
                              u"Вибери панель для '%s'" % dot.TextDot().Text, closed=True)
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
        rs.SelectObjects(made)  # на виході виділено все створене


if __name__ == "__main__":
    main()
